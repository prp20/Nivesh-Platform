"""
Seed the stocks table with NSE-listed companies.

Data source: backend/data/stocks.csv (CSV-driven, no hardcoding)
This script reads from stocks.csv and upserts each row into the database.

Run once: python scripts/seed/seed_stock_master.py
"""
import asyncio
import csv
from pathlib import Path
from typing import List, Dict
import sys
import os

# Load .env file explicitly so environment variables are available
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.db_compat import raw_connection, db_execute

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
                "industry": row.get("industry") or None,
                "summary": row.get("summary") or None,
                "market_cap_cat": row.get("market_cap_category") or None,
                "yf_symbol": row["yf_symbol"],
                "is_index": row["is_index"].lower() == "true",
            })
    return stocks

INSERT_STOCK_SQL = """
    INSERT INTO stocks (symbol, nse_symbol, yf_symbol, screener_slug, company_name, sector, industry, summary, market_cap_cat, is_index, is_active)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, FALSE, TRUE)
    ON CONFLICT (symbol) DO UPDATE SET
        company_name   = EXCLUDED.company_name,
        sector         = EXCLUDED.sector,
        industry       = EXCLUDED.industry,
        summary        = EXCLUDED.summary,
        market_cap_cat = EXCLUDED.market_cap_cat,
        is_index       = FALSE,
        updated_at     = CURRENT_TIMESTAMP
"""

INSERT_BENCHMARK_SQL = """
    INSERT INTO benchmark_master (benchmark_code, benchmark_name, ticker, benchmark_type, asset_class, is_active)
    VALUES ($1, $2, $3, 'Market Index', 'Equity', TRUE)
    ON CONFLICT (benchmark_code) DO UPDATE SET
        benchmark_name = EXCLUDED.benchmark_name,
        ticker = EXCLUDED.ticker,
        updated_at = CURRENT_TIMESTAMP
"""

DELETE_INDEX_FROM_STOCKS_SQL = """
    DELETE FROM stocks WHERE symbol = $1 AND is_index = TRUE
"""


async def seed():
    # Load records from CSV
    records = load_stocks_from_csv()

    async with raw_connection() as conn:
        stocks_count = 0
        indices_count = 0

        for r in records:
            if r["is_index"]:
                # 1. Upsert into benchmark_master
                await db_execute(
                    conn,
                    INSERT_BENCHMARK_SQL,
                    (
                        r["symbol"],
                        r["company_name"],
                        r["yf_symbol"],
                    )
                )

                # 2. Cleanup: Remove from stocks table if it was previously seeded there
                await db_execute(conn, DELETE_INDEX_FROM_STOCKS_SQL, (r["symbol"],))

                indices_count += 1
                print(f"  Index ✓ {r['symbol']}")
            else:
                # Upsert into stocks
                await db_execute(
                    conn,
                    INSERT_STOCK_SQL,
                    (
                        r["symbol"],
                        r.get("nse_symbol", r["symbol"]),
                        r["yf_symbol"],
                        r.get("screener_slug", r["symbol"]),
                        r["company_name"],
                        r.get("sector"),
                        r.get("industry"),
                        r.get("summary"),
                        r.get("market_cap_cat"),
                    )
                )
                stocks_count += 1
                if stocks_count % 50 == 0:
                    print(f"  Stock ✓ {r['symbol']} ({stocks_count} processed)")

        print(f"\nSeeding complete from {CSV_PATH}")
        print(f"  - Stocks seeded/updated: {stocks_count}")
        print(f"  - Indices seeded/updated in benchmarks: {indices_count}")


if __name__ == "__main__":
    asyncio.run(seed())
