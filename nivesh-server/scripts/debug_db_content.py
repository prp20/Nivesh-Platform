import asyncio
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.database import init_db_pool, raw_connection

async def check():
    await init_db_pool()
    async with raw_connection() as conn:
        count = await conn.fetchval('SELECT COUNT(*) FROM benchmark_nav_history')
        print(f"Total rows in benchmark_nav_history: {count}")
        if count > 0:
            rows = await conn.fetch('SELECT * FROM benchmark_nav_history LIMIT 5')
            for r in rows:
                print(r)
        
        # Also check benchmark_master
        bm_rows = await conn.fetch('SELECT benchmark_code, ticker FROM benchmark_master')
        print("\nBenchmark Master Content:")
        for r in bm_rows:
            print(r)

if __name__ == "__main__":
    asyncio.run(check())
