import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv('.env')

from app.database import raw_connection, init_db_pool

async def check():
    await init_db_pool()
    async with raw_connection() as conn:
        rows = await conn.fetch('SELECT symbol, yf_symbol FROM stocks WHERE is_index = FALSE LIMIT 10')
        for r in rows:
            print(f"{r['symbol']} -> {r['yf_symbol']}")

if __name__ == "__main__":
    asyncio.run(check())
