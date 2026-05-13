"""
seed_stocks.py — Seeds stocks and indices into the `stocks` table.

Sources:
  - data/stocks.csv       → equity stocks (is_index=False)
  - data/indices.csv      → benchmark indices (is_index=True)

CSV columns (stocks.csv):
  symbol, company_name, sector, industry, summary, market_cap_category, yf_symbol, is_index

CSV columns (indices.csv):
  symbol, company_name, sector, industry, summary, market_cap_category, yf_symbol, is_index

Usage:
  export DATABASE_URL="postgresql://postgres.[ref]:[pwd]@..."
  python scripts/seed/seed_stocks.py [--dry-run]
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
STOCKS_CSV = DATA_DIR / "stocks.csv"
INDICES_CSV = DATA_DIR / "indices.csv"


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL environment variable not set.")
        sys.exit(1)
    # Ensure sync driver
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return psycopg2.connect(url)


def load_stocks_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def seed(dry_run: bool = False):
    all_rows = []

    # Load equity stocks
    if STOCKS_CSV.exists():
        stocks = load_stocks_csv(STOCKS_CSV)
        print(f"  Loaded {len(stocks)} rows from {STOCKS_CSV.name}")
        all_rows.extend(stocks)
    else:
        print(f"  WARNING: {STOCKS_CSV} not found — skipping")

    # Load indices
    if INDICES_CSV.exists():
        indices = load_stocks_csv(INDICES_CSV)
        print(f"  Loaded {len(indices)} rows from {INDICES_CSV.name}")
        all_rows.extend(indices)
    else:
        print(f"  WARNING: {INDICES_CSV} not found — skipping")

    if not all_rows:
        print("Nothing to seed.")
        return

    records = []
    for row in all_rows:
        is_index_raw = str(row.get("is_index", "false")).strip().lower()
        is_index = is_index_raw in ("true", "1", "yes")
        records.append((
            row.get("symbol", "").strip(),
            row.get("yf_symbol", "").strip(),
            row.get("company_name", "").strip(),
            row.get("sector", "").strip() or None,
            row.get("industry", "").strip() or None,
            row.get("summary", "").strip() or None,
            row.get("market_cap_category", "").strip() or None,
            is_index,
        ))

    sql = """
        INSERT INTO stocks (symbol, yf_symbol, company_name, sector, industry,
                            summary, market_cap_cat, is_index)
        VALUES %s
        ON CONFLICT (symbol) DO UPDATE SET
            yf_symbol    = EXCLUDED.yf_symbol,
            company_name = EXCLUDED.company_name,
            sector       = EXCLUDED.sector,
            industry     = EXCLUDED.industry,
            summary      = EXCLUDED.summary,
            market_cap_cat = EXCLUDED.market_cap_cat,
            updated_at   = NOW()
    """

    if dry_run:
        print(f"  [DRY RUN] Would upsert {len(records)} stocks/indices")
        for r in records[:5]:
            print(f"    {r[0]} | {r[2]} | index={r[7]}")
        return

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                execute_values(cur, sql, records)
                print(f"  Upserted {len(records)} stocks/indices")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed stocks and indices")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be inserted without writing")
    args = parser.parse_args()

    print("=== Seeding stocks ===")
    seed(dry_run=args.dry_run)
    print("Done.")
