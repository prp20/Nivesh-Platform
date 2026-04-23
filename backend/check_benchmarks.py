import asyncio
from app.database import raw_connection

async def check():
    async with raw_connection() as conn:
        print("Benchmark Master:")
        bm = await conn.fetch("SELECT * FROM benchmark_master")
        for r in bm:
            print(dict(r))
        
        print("\nBenchmark Nav History Sample:")
        bn = await conn.fetch("SELECT * FROM benchmark_nav_history LIMIT 5")
        for r in bn:
            print(dict(r))

if __name__ == "__main__":
    asyncio.run(check())
