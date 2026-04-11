"""
Seed the stocks table with NSE-listed companies.

Data source: backend/data/stocks.csv (CSV-driven, no hardcoding)
This script reads from stocks.csv and upserts each row into the database.

Run once: python scripts/seed/seed_stock_master.py
"""
import asyncio
import asyncpg
import csv
from pathlib import Path
from typing import List, Dict
import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.config import settings

# Path to the CSV file (relative to this script)
CSV_PATH = Path(__file__).parent.parent.parent / "data" / "stocks.csv"


def load_stocks_from_csv() -> List[Dict]:
    """Load stocks from CSV file and return list of stock dictionaries."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Stocks CSV not found at {CSV_PATH}")

    stocks = []
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Ensure empty string becomes None for optional fields
            stocks.append({
                "symbol": row["symbol"],
                "company_name": row["company_name"],
                "sector": row.get("sector") or None,
                "market_cap_cat": row.get("market_cap_category") or None,
                "yf_symbol": row["yf_symbol"],
                "is_index": row["is_index"].lower() == "true",
            })
    return stocks

INSERT_SQL = """
    INSERT INTO stocks (symbol, nse_symbol, yf_symbol, screener_slug, company_name, sector, market_cap_cat, is_index, is_active)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE)
    ON CONFLICT (symbol) DO UPDATE SET
        company_name   = EXCLUDED.company_name,
        sector         = EXCLUDED.sector,
        market_cap_cat = EXCLUDED.market_cap_cat,
        updated_at     = NOW()
"""


async def seed():
    # Load stocks from CSV
    stocks = load_stocks_from_csv()

    # Convert async URL to sync URL for asyncpg
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    try:
        for s in stocks:
            await conn.execute(
                INSERT_SQL,
                s["symbol"],
                s.get("nse_symbol", s["symbol"]),
                s["yf_symbol"],
                s.get("screener_slug", s["symbol"]),
                s["company_name"],
                s.get("sector"),
                s.get("market_cap_cat"),
                s.get("is_index", False),
            )
            print(f"  ✓ {s['symbol']}")
        print(f"\nSeeded {len(stocks)} records from {CSV_PATH}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
