"""
seed_funds.py — Seeds fund_master from scheme_master_with_benchmark.csv.

CSV columns:
  scheme_code, scheme_name, amc_name, plan_type, risk_profile, created_at,
  inception_date, scheme_category, scheme_subcategory, benchmark_index_code

Skips rows with missing scheme_code, scheme_name, or amc_name.

Usage:
  export DATABASE_URL="postgresql://postgres.[ref]:[pwd]@..."
  python scripts/seed/seed_funds.py [--dry-run]
"""
import os
import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
FUNDS_CSV = DATA_DIR / "scheme_master_with_benchmark.csv"


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL environment variable not set.")
        sys.exit(1)
    return psycopg2.connect(url.replace("postgresql+asyncpg://", "postgresql://"))


def parse_date(val: str):
    """Parse date from multiple formats: YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY."""
    val = val.strip()
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z"):
        try:
            return datetime.strptime(val[:10], fmt[:8]).date()
        except ValueError:
            continue
    return None


def seed(dry_run: bool = False):
    if not FUNDS_CSV.exists():
        print(f"ERROR: {FUNDS_CSV} not found.")
        sys.exit(1)

    records = []
    skipped = 0
    with open(FUNDS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sc = str(row.get("scheme_code", "")).strip()
            sn = str(row.get("scheme_name", "")).strip()
            amc = str(row.get("amc_name", "")).strip()
            if not sc or not sn or not amc:
                skipped += 1
                continue

            inception_raw = row.get("inception_date", "").strip()
            inception = parse_date(inception_raw) if inception_raw else None
            if inception is None:
                inception = datetime(2000, 1, 1).date()  # fallback for missing dates

            records.append((
                sc,
                sn,
                amc,
                inception,
                str(row.get("plan_type", "Unknown")).strip(),
                str(row.get("scheme_category", "Unknown")).strip(),
                str(row.get("scheme_subcategory", "")).strip() or None,
                str(row.get("benchmark_index_code", "")).strip() or None,
            ))

    print(f"  Loaded {len(records)} valid funds ({skipped} skipped — missing required fields)")

    sql = """
        INSERT INTO fund_master
            (scheme_code, scheme_name, amc_name, inception_date, plan_type,
             scheme_category, scheme_subcategory, benchmark_index_code)
        VALUES %s
        ON CONFLICT (scheme_code) DO UPDATE SET
            scheme_name          = EXCLUDED.scheme_name,
            amc_name             = EXCLUDED.amc_name,
            inception_date       = EXCLUDED.inception_date,
            plan_type            = EXCLUDED.plan_type,
            scheme_category      = EXCLUDED.scheme_category,
            scheme_subcategory   = EXCLUDED.scheme_subcategory,
            benchmark_index_code = EXCLUDED.benchmark_index_code,
            updated_at           = NOW()
    """

    if dry_run:
        print(f"  [DRY RUN] Would upsert {len(records)} funds")
        for r in records[:5]:
            print(f"    {r[0]} | {r[1][:60]} | {r[2]}")
        return

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                execute_values(cur, sql, records, page_size=500)
                print(f"  Upserted {len(records)} funds")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed fund_master from CSV")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=== Seeding fund_master ===")
    seed(dry_run=args.dry_run)
    print("Done.")
