from contextlib import asynccontextmanager
from pathlib import Path
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from jose import jwt, JWTError


from .config import settings
from .database import engine, init_db_pool, close_db_pool
from .db_compat import is_sqlite
from .routers import funds, benchmarks, navs, benchmark_navs, metrics, sync, auth, stocks, screener, pipeline, agents

from .database import engine, Base
from .rate_limiting import get_rate_limiter
from pipeline.scheduler import configure_scheduler, scheduler

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

    # Startup logic
    async with engine.begin() as conn:
        # Mutate DB state: create extensions, tables, and audit logs.
        if not is_sqlite():
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        await conn.run_sync(Base.metadata.create_all)

        # Create legacy audit_log table if it doesn't exist
        if not is_sqlite():
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id BIGSERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    action VARCHAR(100) NOT NULL,
                    user_account VARCHAR(100) NOT NULL,
                    resource VARCHAR(500) NOT NULL,
                    details JSONB,
                    status VARCHAR(20) NOT NULL,
                    error_message TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
        else:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    action VARCHAR(100) NOT NULL,
                    user_account VARCHAR(100) NOT NULL,
                    resource VARCHAR(500) NOT NULL,
                    details TEXT,
                    status VARCHAR(20) NOT NULL,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_audit_log_user_timestamp
                ON audit_log(user_account, created_at DESC);
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_audit_log_action
                ON audit_log(action, created_at DESC);
        """))

    # Configure and start scheduler
    configure_scheduler()
    scheduler.start()
    logger.info("Scheduler started successfully")

    yield
    # Shutdown logic
    scheduler.shutdown(wait=False)
    await close_db_pool()

    logger.info("Scheduler shut down")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
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
app.include_router(agents.router, prefix=settings.API_V1_STR)

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
            "version": "1.0.0",
            "status": "running",
            "environment": "development" if not settings.ENABLE_AUTH else "production",
        },
        "database": {
            "status": db_status,
            "name": db_name,
            "latency_ms": round((time.time() - start_time) * 1000, 2)
        },
        "documentation": "/docs"
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
