import asyncio
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.database import raw_connection, init_db_pool

async def check():
    await init_db_pool()
    async with raw_connection() as conn:
        rows = await conn.fetch('SELECT benchmark_code, benchmark_name FROM benchmark_master')
        for r in rows:
            print(f"{r['benchmark_code']}: {r['benchmark_name']}")

if __name__ == "__main__":
    asyncio.run(check())
