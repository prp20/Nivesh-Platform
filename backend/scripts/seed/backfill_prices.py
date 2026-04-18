"""
One-time script: fetch 5 years of daily OHLCV for all stocks.
Run from backend/ directory: python scripts/seed/backfill_prices.py [period]

Expected runtime: 20–40 minutes for ~200 stocks (network-dependent).
"""
import asyncio
import sys
sys.path.insert(0, ".")

from pipeline.price_ingestion import run_backfill
from tqdm import tqdm

async def main(period: str):
    print(f"Starting price backfill (period={period})...")
    
    pbar = None
    
    async def progress_callback(increment, processed, total):
        nonlocal pbar
        if pbar is None:
            pbar = tqdm(total=total, desc="Backfilling stocks")
        pbar.update(increment)

    try:
        await run_backfill(period=period, progress_callback=progress_callback)
    finally:
        if pbar:
            pbar.close()
    
    print("\nBackfill complete.")

if __name__ == "__main__":
    period = sys.argv[1] if len(sys.argv) > 1 else "5y"
    asyncio.run(main(period))
