import asyncio
import sys
import os

# Load .env file explicitly so environment variables are available
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

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
    from app.db_compat import is_sqlite
    async with engine.begin() as conn:
        if not is_sqlite():
            # pg_trgm is required for GIN trigram indexes on fund_master and stocks.
            # Must be created before create_all, otherwise index creation fails.
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        # Import all models to ensure they are registered with the Base
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialization complete.")

if __name__ == "__main__":
    asyncio.run(init_db())
