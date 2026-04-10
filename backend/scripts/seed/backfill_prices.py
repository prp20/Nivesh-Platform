"""
One-time script: fetch 5 years of daily OHLCV for all stocks.
Run from backend/ directory: python scripts/seed/backfill_prices.py [period]

Expected runtime: 20–40 minutes for ~200 stocks (network-dependent).
"""
import asyncio
import sys
sys.path.insert(0, ".")

from pipeline.price_ingestion import run_backfill

if __name__ == "__main__":
    period = sys.argv[1] if len(sys.argv) > 1 else "5y"
    print(f"Starting price backfill (period={period})...")
    asyncio.run(run_backfill(period=period))
    print("Backfill complete.")
