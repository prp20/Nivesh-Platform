import asyncio
import asyncpg
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.config import settings

async def verify():
    url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    
    symbol = 'ABB'
    print(f"--- Checking metadata for {symbol} ---")
    row = await conn.fetchrow("SELECT symbol, industry, LEFT(summary, 100) as summary_preview FROM stocks WHERE symbol = $1", symbol)
    if row:
        print(f"Symbol: {row['symbol']}")
        print(f"Industry: {row['industry']}")
        print(f"Summary Preview: {row['summary_preview']}...")
    else:
        print(f"Stock {symbol} not found!")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(verify())
