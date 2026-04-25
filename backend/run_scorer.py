import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.database import AsyncSessionLocal, raw_connection
from fundamental_scorer.graph import run_fundamental_scorer

async def main(symbol):
    async with AsyncSessionLocal() as session:
        # Get stock_id
        async with raw_connection() as conn:
            row = await conn.fetchrow("SELECT id FROM stocks WHERE symbol=$1", symbol.upper())
            if not row:
                print(f"Stock {symbol} not found")
                return
            stock_id = row['id']
        
        print(f"Running scorer for {symbol} (ID: {stock_id})")
        result = await run_fundamental_scorer(stock_id=stock_id, symbol=symbol.upper(), db=session)
        print("Finishing status:", result.get("status"))
        if result.get("error"):
            print("Error:", result.get("error"))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_scorer.py SYMBOL")
    else:
        asyncio.run(main(sys.argv[1]))
