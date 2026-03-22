from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .config import settings
from .routers import funds, benchmarks, navs, benchmark_navs, metrics, sync, auth
from .database import engine, Base

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("SELECT create_hypertable('fund_nav_history', 'nav_date', if_not_exists => TRUE);"))
            await conn.execute(text("SELECT create_hypertable('benchmark_nav_history', 'nav_date', if_not_exists => TRUE);"))
            await conn.commit()
        except Exception as e:
            print(f"Hypertable creation skipped or failed: {e}")

@app.get("/", tags=["root"])
async def root():
    return {
        "message": "Nivesh Platform API",
        "status": "running",
        "documentation": "/docs"
    }
