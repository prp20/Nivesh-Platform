"""
seed_benchmarks.py — Seeds benchmark_master from data/indices.csv.

The indices.csv file uses the same format as stocks.csv (symbol, company_name,
yf_symbol, is_index=true). We treat each entry as a benchmark.

Benchmark codes are the symbol field (e.g. NIFTY50, SENSEX, NIFTYBANK).
Tickers are the yf_symbol field (e.g. ^NSEI, ^BSESN).

Usage:
  export DATABASE_URL="postgresql://postgres.[ref]:[pwd]@..."
  python scripts/seed/seed_benchmarks.py [--dry-run]
"""
import os
import sys
import csv
import argparse
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
INDICES_CSV = DATA_DIR / "indices.csv"


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL environment variable not set.")
        sys.exit(1)
    return psycopg2.connect(url.replace("postgresql+asyncpg://", "postgresql://"))


def seed(dry_run: bool = False):
    if not INDICES_CSV.exists():
        print(f"ERROR: {INDICES_CSV} not found.")
        sys.exit(1)

    records = []
    with open(INDICES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row.get("symbol", "").strip()
            name = row.get("company_name", "").strip()
            ticker = row.get("yf_symbol", "").strip()
            if not symbol or not ticker:
                continue
            records.append((
                symbol,                    # benchmark_code
                name or symbol,            # benchmark_name
                ticker,                    # ticker (yfinance symbol)
                "Equity Index",            # benchmark_type
                "Equity",                  # asset_class
            ))

    print(f"  Loaded {len(records)} benchmarks")

    sql = """
        INSERT INTO benchmark_master
            (benchmark_code, benchmark_name, ticker, benchmark_type, asset_class)
        VALUES %s
        ON CONFLICT (benchmark_code) DO UPDATE SET
            benchmark_name = EXCLUDED.benchmark_name,
            ticker         = EXCLUDED.ticker,
            updated_at     = NOW()
    """

    if dry_run:
        print(f"  [DRY RUN] Would upsert {len(records)} benchmarks")
        for r in records:
            print(f"    {r[0]} | {r[1]} | {r[2]}")
        return

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                execute_values(cur, sql, records)
                print(f"  Upserted {len(records)} benchmarks")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed benchmark_master from indices.csv")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Seeding benchmark_master ===")
    seed(dry_run=args.dry_run)
    print("Done.")
