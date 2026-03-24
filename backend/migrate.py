import asyncio
from app.database import engine, Base
# Import all models to ensure metadata has them registered
from app.models import FundMaster, BenchmarkMaster, FundNavHistory, BenchmarkNavHistory, FundMetrics, BenchmarkMetrics

async def run_migrations():
    async with engine.begin() as conn:
        print("Provisioning BenchmarkMetrics table if it doesn't exist...")
        # create_all will only create tables that don't exist
        await conn.run_sync(Base.metadata.create_all)
        
        print("Flushing corrupt/unnormalized BenchmarkNavHistory rows...")
        await conn.execute(BenchmarkNavHistory.__table__.delete())
        
        print("Flushing out any BenchmarkMetrics rows...")
        await conn.execute(BenchmarkMetrics.__table__.delete())
        
        print("Database wipe and provision successful.")

if __name__ == "__main__":
    asyncio.run(run_migrations())
