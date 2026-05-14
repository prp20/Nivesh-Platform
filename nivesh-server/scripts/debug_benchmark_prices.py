import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import init_db_pool, raw_connection, get_db
from app import crud

async def test():
    await init_db_pool()
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        items, total = await crud.get_all_benchmark_masters(session, limit=100)
        print(f"Total benchmarks: {total}")
        
        codes = [item.benchmark_code for item in items]
        print(f"Codes: {codes}")
        
        prices = await crud.get_benchmarks_latest_prices(session, codes)
        print(f"Prices found for codes: {list(prices.keys())}")
        
        for item in items:
            p_data = prices.get(item.benchmark_code, {})
            print(f"Code: {item.benchmark_code}, Price Data: {p_data}")

if __name__ == "__main__":
    asyncio.run(test())
