from contextlib import asynccontextmanager
from pathlib import Path
import logging

# Attach a handler to the root logger so app-level log calls appear in the
# uvicorn console. Uvicorn only configures handlers for its own loggers;
# without this, all logging.getLogger(__name__) calls are silently dropped.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Request, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from .config import settings
from .database import engine, get_db, init_db_pool, close_db_pool
from .routers import funds, benchmarks, navs, benchmark_navs, metrics, sync, auth, stocks, screener, pipeline
from . import crud as _crud, security
from .database import engine, Base
from .rate_limiting import get_rate_limiter

try:
    from pipeline.scheduler import configure_scheduler, scheduler as _scheduler
    _HAS_SCHEDULER = True
except ModuleNotFoundError:
    _HAS_SCHEDULER = False
    configure_scheduler = lambda: None  # noqa: E731
    _scheduler = None

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic for the FastAPI application."""
    # Export LangSmith and Groq variables to environment for underlying libraries
    import os
    if settings.LANGSMITH_TRACING:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        trace_key = settings.LANGSMITH_API_KEY.get_secret_value()
        if trace_key:
            os.environ["LANGCHAIN_API_KEY"] = trace_key
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    
    groq_key = settings.GROQ_API_KEY.get_secret_value()
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key

    # Startup: verify DB connectivity — fail fast if Supabase is unreachable.
    # Table schema is managed by Alembic migrations (alembic upgrade head).
    # Do NOT call Base.metadata.create_all here.
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info(f"[startup] Supabase connection OK — env={settings.ENVIRONMENT}")
    except Exception as e:
        logger.warning(f"[startup] DB connection failed on startup: {e}")

    # Configure and start scheduler (Phase 3 — skipped if pipeline module absent)
    if _HAS_SCHEDULER:
        configure_scheduler()
        _scheduler.start()
        logger.info("Scheduler started successfully")
    else:
        logger.info("Scheduler skipped — pipeline module not yet available (Phase 3)")

    # Export OpenAPI spec to docs/ in development mode
    if settings.ENVIRONMENT == "development":
        try:
            import json
            from pathlib import Path
            spec = app.openapi()
            out = Path(__file__).parent.parent.parent / "docs" / "api-contract.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(spec, indent=2))
            logger.info(f"OpenAPI spec written to {out}")
        except Exception as e:
            logger.warning(f"OpenAPI export failed: {e}")

    yield
    # Shutdown logic
    if _HAS_SCHEDULER and _scheduler is not None:
        _scheduler.shutdown(wait=False)
    await close_db_pool()

    logger.info("Scheduler shut down")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.APP_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    # Hide interactive docs in production
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    Apply rate limiting to incoming requests.

    Uses user identifier from JWT token if available, falls back to IP address.
    Enforces per-endpoint rate limits defined in rate_limiting.py.
    """
    # Get user identifier (prefer JWT sub, fall back to IP)
    user_id = request.client.host if request.client else "unknown"
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, settings.SECRET_KEY.get_secret_value() if hasattr(settings.SECRET_KEY, "get_secret_value") else settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("sub", user_id)
        except (JWTError, Exception):
            pass  # Fall back to IP on invalid tokens


    # Get endpoint path for rate limit lookup
    endpoint = request.url.path
    rate_limiter = get_rate_limiter()

    # Check rate limit
    if not rate_limiter.is_allowed(user_id, endpoint):
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded",
                "retry_after": 60,
            },
            headers={"Retry-After": "60"},
        )

    # Continue with request
    response = await call_next(request)
    return response

# Include Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(funds.router, prefix=settings.API_V1_STR)
app.include_router(benchmarks.router, prefix=settings.API_V1_STR)
app.include_router(navs.router, prefix=settings.API_V1_STR)
app.include_router(benchmark_navs.router, prefix=settings.API_V1_STR)
app.include_router(metrics.router, prefix=settings.API_V1_STR)
app.include_router(sync.router, prefix=settings.API_V1_STR)
app.include_router(stocks.router, prefix=settings.API_V1_STR)
app.include_router(screener.router, prefix=settings.API_V1_STR)
app.include_router(pipeline.router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["system"], include_in_schema=False)
async def health_render():
    """
    Lightweight health check used by Render and UptimeRobot.
    Always returns HTTP 200 (status field shows degraded if DB is down).
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/api/health", tags=["root"])
async def root():
    """
    System health check.
    Verifies API status and database connectivity.
    """
    from sqlalchemy import text
    import time

    start_time = time.time()
    db_status = "unknown"
    db_name = "unknown"
    
    try:
        # Check database connectivity
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "connected"
            # Extract DB name from engine URL
            db_name = engine.url.database
    except Exception as e:
        logger.error(f"Health check database error: {e}")
        db_status = "error"

    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api": {
            "name": settings.PROJECT_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "environment": settings.ENVIRONMENT,
        },
        "database": {
            "status": db_status,
            "name": db_name,
            "latency_ms": round((time.time() - start_time) * 1000, 2)
        },
        "documentation": "/docs" if settings.ENVIRONMENT != "production" else None,
    }


@app.get("/api/v1/sync/status", tags=["system"])
async def sync_status(
    pipeline_name: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _user=Depends(security.get_current_user),
):
    """Recent ETL run records, optionally filtered by pipeline_name."""
    from . import schemas as _schemas
    runs = await _crud.get_etl_run_summary(db, pipeline_name, limit)
    return {
        "runs": [_schemas.EtlRunRead.model_validate(r) for r in runs],
        "total": len(runs),
    }

# SPA Fallback routing for production deployment
dist_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"

if dist_dir.exists() and dist_dir.is_dir():
    # Mount /assets (JS/CSS chunks)
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Let API and docs routes fall through to their own handlers
        if full_path.startswith("api/") or full_path in ("docs", "redoc", "openapi.json"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")

        # Serve the exact file if it exists in dist (favicon, robots.txt, etc.)
        requested = dist_dir / full_path
        if requested.exists() and requested.is_file():
            return FileResponse(requested)

        # Fall back to index.html for all SPA client-side routes
        index_file = dist_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)

        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Frontend build not found")
else:
    @app.get("/", tags=["root"])
    async def fallback_root():
        return {
            "message": f"{settings.PROJECT_NAME} API",
            "status": "running",
            "warning": "Frontend not built. Run 'npm run build' in frontend directory to serve SPA.",
        }
