from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .config import settings
from .routers import funds, benchmarks, navs, benchmark_navs, metrics, sync, auth
from .database import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            # TimescaleDB hypertable setup
            await conn.execute(text("SELECT create_hypertable('fund_nav_history', 'nav_date', if_not_exists => TRUE);"))
            await conn.execute(text("SELECT create_hypertable('benchmark_nav_history', 'nav_date', if_not_exists => TRUE);"))
            await conn.commit()
        except Exception as e:
            # Skip if already a hypertable or outside TimescaleDB context
            print(f"Hypertable creation skipped or failed: {e}")
    yield
    # Shutdown logic (none needed for now)

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
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(funds.router, prefix=settings.API_V1_STR)
app.include_router(benchmarks.router, prefix=settings.API_V1_STR)
app.include_router(navs.router, prefix=settings.API_V1_STR)
app.include_router(benchmark_navs.router, prefix=settings.API_V1_STR)
app.include_router(metrics.router, prefix=settings.API_V1_STR)
app.include_router(sync.router, prefix=settings.API_V1_STR)

@app.get("/", tags=["root"])
async def root():
    return {
        "message": f"{settings.PROJECT_NAME} API",
        "status": "running",
        "auth_enabled": settings.ENABLE_AUTH,
        "documentation": "/docs"
    }
