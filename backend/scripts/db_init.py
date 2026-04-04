import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import engine, Base
from app.models import (
    SyncJob, FundMaster, BenchmarkMaster, 
    FundNavHistory, BenchmarkNavHistory, 
    BenchmarkMetrics, FundMetrics
)

async def init_db():
    print("Connecting to database and ensuring table structures exist...")
    async with engine.begin() as conn:
        # Import all models to ensure they are registered with the Base
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialization complete.")

if __name__ == "__main__":
    asyncio.run(init_db())
