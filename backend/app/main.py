from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import funds, benchmarks, navs, benchmark_navs, metrics, sync, auth, stocks, screener, pipeline
from .database import engine, Base
from pipeline.scheduler import configure_scheduler, scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Configure and start scheduler
    configure_scheduler()
    scheduler.start()

    yield
    # Shutdown logic
    scheduler.shutdown(wait=False)

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

@app.get("/api/health", tags=["root"])
async def root():
    return {
        "message": f"{settings.PROJECT_NAME} API",
        "status": "running",
        "documentation": "/docs",
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
