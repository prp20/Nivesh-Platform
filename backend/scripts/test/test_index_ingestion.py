import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from pipeline.price_ingestion import run_index_ingestion
from app.database import init_db_pool, close_db_pool

async def test():
    print("Testing index ingestion...")
    await init_db_pool()
    try:
        await run_index_ingestion()
        print("Index ingestion completed.")
    finally:
        await close_db_pool()

if __name__ == "__main__":
    asyncio.run(test())
