"""
One-time script: fetch 5 years of daily OHLCV for all stocks.
Run from backend/ directory: python scripts/seed/backfill_prices.py [period]

Expected runtime: 20–40 minutes for ~200 stocks (network-dependent).
"""
import asyncio
import sys
import os

# Load .env file explicitly so environment variables are available
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Add backend to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from pipeline.price_ingestion import run_backfill, run_index_backfill
from tqdm import tqdm

async def main(period: str):
    print(f"Starting price backfill (period={period})...")
    
    pbar_stocks = None
    pbar_indices = None
    
    async def stock_callback(increment, processed, total):
        nonlocal pbar_stocks
        if pbar_stocks is None:
            pbar_stocks = tqdm(total=total, desc="Backfilling stocks")
        pbar_stocks.update(increment)

    async def index_callback(increment, processed, total):
        nonlocal pbar_indices
        if pbar_indices is None:
            pbar_indices = tqdm(total=total, desc="Backfilling indices")
        pbar_indices.update(increment)

    try:
        # 1. Backfill Indices
        await run_index_backfill(period=period, progress_callback=index_callback)
        
        # 2. Backfill Stocks
        await run_backfill(period=period, progress_callback=stock_callback)
    finally:
        if pbar_stocks:
            pbar_stocks.close()
        if pbar_indices:
            pbar_indices.close()
    
    print("\nBackfill complete.")

if __name__ == "__main__":
    period = sys.argv[1] if len(sys.argv) > 1 else "max"
    asyncio.run(main(period))
