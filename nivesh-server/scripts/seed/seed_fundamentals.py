"""
Seed fundamental data by scraping screener.in for all active non-index stocks.

Prerequisites: Stock master must be seeded first (seed_stock_master.py).
Requires internet access to screener.in.
Estimated time: 5-15 minutes (2-5 seconds per stock with polite delays).

Usage:
    cd backend
    source venv/bin/activate
    python3 scripts/seed/seed_fundamentals.py
"""
import asyncio
import sys
import os

# Resolve backend root so pipeline imports work when called from any directory
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _BACKEND_ROOT)

# Load backend .env so DATABASE_URL etc. are available
from dotenv import load_dotenv
load_dotenv(os.path.join(_BACKEND_ROOT, ".env"))


async def main():
    from pipeline.fundamental_scraper import run_fundamental_scrape_all
    from pipeline.ratio_engine import run_ratio_compute_all

    print("[INFO]  Starting fundamentals scrape from screener.in ...")
    print("[INFO]  This may take 5-15 minutes with polite delays between requests.")
    print()

    await run_fundamental_scrape_all()

    print()
    print("[INFO]  Scrape complete. Running ratio recompute ...")
    await run_ratio_compute_all()

    print()
    print("[OK]    Fundamentals seeding complete.")


if __name__ == "__main__":
    asyncio.run(main())
