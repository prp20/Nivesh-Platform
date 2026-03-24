import asyncio
from backend.app.database import session_factory
from backend.app.models import FundMaster, BenchmarkMaster
from sqlalchemy import select, func

async def verify():
    async with session_factory() as s:
        f_count = await s.execute(select(func.count()).select_from(FundMaster))
        print(f"Total Funds: {f_count.scalar()}")
        
        b_count = await s.execute(select(func.count()).select_from(BenchmarkMaster))
        print(f"Total Benchmarks: {b_count.scalar()}")
        
        # Check a few random funds that were in the CSV
        res = await s.execute(select(FundMaster).where(FundMaster.scheme_code.in_(['119716', '120505', '120158'])).limit(3))
        funds = res.scalars().all()
        for f in funds:
            print(f"Fund: {f.scheme_code}, Name: {f.scheme_name}, Benchmark: {f.benchmark_index_code}")

if __name__ == "__main__":
    asyncio.run(verify())
