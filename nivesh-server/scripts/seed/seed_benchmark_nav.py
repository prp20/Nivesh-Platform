"""
seed_benchmark_nav.py — Fetches historical index closing prices from Yahoo Finance
and seeds them into benchmark_nav_history.

Reads benchmark_master (already seeded) to get (benchmark_code, ticker) pairs,
then downloads historical OHLCV via yfinance and upserts the Close column as
index_value into benchmark_nav_history.

Prerequisites:
  - benchmark_master must be seeded first (run seed_benchmarks.py)
  - pip install yfinance psycopg2-binary

Usage:
  export DATABASE_URL="postgresql://postgres.[ref]:[pwd]@..."
  python scripts/seed/seed_benchmark_nav.py [--dry-run] [--period 5y]
"""
import os
import sys
import time
import argparse
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

try:
    import yfinance as yf
except ImportError:
    print("yfinance not installed. Run: pip install yfinance")
    sys.exit(1)


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL environment variable not set.")
        sys.exit(1)
    return psycopg2.connect(url.replace("postgresql+asyncpg://", "postgresql://"))


def fetch_benchmarks(conn) -> list[tuple[str, str]]:
    """Return list of (benchmark_code, ticker) from benchmark_master."""
    with conn.cursor() as cur:
        cur.execute("SELECT benchmark_code, ticker FROM benchmark_master WHERE is_active = true ORDER BY benchmark_code")
        return cur.fetchall()


def fetch_nav_history(ticker: str, period: str) -> list[tuple]:
    """
    Download closing price history from Yahoo Finance.
    Returns list of (date, close_price) tuples, sorted ascending.
    """
    try:
        data = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    except Exception as e:
        print(f"    ERROR fetching {ticker}: {e}")
        return []

    if data.empty:
        return []

    rows = []
    for idx, row in data.iterrows():
        close = row.get("Close")
        if close is None or close != close:  # skip NaN
            continue
        rows.append((idx.date(), round(float(close), 4)))

    return rows


def seed(dry_run: bool = False, period: str = "max"):
    conn = get_conn()
    try:
        benchmarks = fetch_benchmarks(conn)
    finally:
        conn.close()

    if not benchmarks:
        print("  No benchmarks found in benchmark_master. Run seed_benchmarks.py first.")
        return

    print(f"  Found {len(benchmarks)} benchmarks — fetching {period} history from Yahoo Finance")

    total_inserted = 0

    for benchmark_code, ticker in benchmarks:
        print(f"  [{benchmark_code}] ticker={ticker} ... ", end="", flush=True)

        rows = fetch_nav_history(ticker, period)
        if not rows:
            print("no data")
            continue

        print(f"{len(rows)} rows", end="")

        if dry_run:
            if rows:
                print(f"  [DRY RUN] {benchmark_code}: would upsert {len(rows)} rows"
                      f" ({rows[0][0]} → {rows[-1][0]})")
            else:
                print(f"  [DRY RUN] {benchmark_code}: no data from Yahoo Finance")
            continue

        records = [(benchmark_code, nav_date, index_value) for nav_date, index_value in rows]

        sql = """
            INSERT INTO benchmark_nav_history (benchmark_code, nav_date, index_value)
            VALUES %s
            ON CONFLICT (benchmark_code, nav_date) DO UPDATE SET
                index_value = EXCLUDED.index_value
        """

        conn = get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    execute_values(cur, sql, records)
            total_inserted += len(records)
            print(f" — upserted")
        except Exception as e:
            print(f" — ERROR: {e}")
        finally:
            conn.close()

        # brief pause to avoid hammering Yahoo Finance
        time.sleep(0.5)

    if not dry_run:
        print(f"\n  Total rows upserted: {total_inserted}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed benchmark_nav_history from Yahoo Finance")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--period", default="max",
                        help="yfinance period: 1y, 5y, 10y, max (default: max)")
    args = parser.parse_args()

    print("=== Seeding benchmark_nav_history ===")
    seed(dry_run=args.dry_run, period=args.period)
    print("Done.")
