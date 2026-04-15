import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.database import engine, Base
from app.models import (
    SyncJob, FundMaster, BenchmarkMaster,
    FundNavHistory, BenchmarkNavHistory,
    BenchmarkMetrics, FundMetrics
)

async def init_db():
    print("Connecting to database and ensuring table structures exist...")
    async with engine.begin() as conn:
        # pg_trgm is required for GIN trigram indexes on fund_master and stocks.
        # Must be created before create_all, otherwise index creation fails.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        # Import all models to ensure they are registered with the Base
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialization complete.")

if __name__ == "__main__":
    asyncio.run(init_db())
