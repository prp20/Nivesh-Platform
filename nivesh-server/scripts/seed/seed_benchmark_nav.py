"""
seed_benchmark_nav.py — Fetches historical index closing prices from Yahoo Finance
and seeds them into benchmark_nav_history.

Reads benchmark_master (already seeded) to get (benchmark_code, ticker) pairs,
then downloads historical OHLCV via yf.download() and upserts the Close column as
index_value into benchmark_nav_history.

Prerequisites:
  - benchmark_master must be seeded first (run seed_benchmarks.py)
  - pip install "yfinance>=0.2.40" psycopg2-binary

Usage:
  export DATABASE_URL="postgresql://postgres.[ref]:[pwd]@..."
  python scripts/seed/seed_benchmark_nav.py [--dry-run] [--period 5y]
"""
import os
import sys
import time
import argparse

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
        cur.execute(
            "SELECT benchmark_code, ticker FROM benchmark_master "
            "WHERE is_active = TRUE ORDER BY benchmark_code"
        )
        return cur.fetchall()


def download_history(ticker: str, period: str) -> list[tuple]:
    """
    Download historical closing prices from Yahoo Finance.
    Returns list of (date, close_price) tuples sorted ascending.
    Returns empty list on any failure.
    """
    try:
        df = yf.download(
            ticker,
            period=period,
            auto_adjust=True,
            progress=False,
            show_errors=False,
        )
    except Exception as e:
        print(f"\n    yf.download error for {ticker}: {e}")
        return []

    if df is None or df.empty:
        return []

    # yfinance may return MultiIndex columns when downloading a single ticker
    if isinstance(df.columns, __import__("pandas").MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if "Close" not in df.columns:
        print(f"\n    No 'Close' column for {ticker}. Columns: {list(df.columns)}")
        return []

    rows = []
    for ts, close in df["Close"].items():
        if close != close:  # NaN check
            continue
        # ts may be a Timestamp (timezone-aware or naive) — normalise to date
        try:
            nav_date = ts.date()
        except AttributeError:
            nav_date = ts
        rows.append((nav_date, round(float(close), 4)))

    return rows


def seed(dry_run: bool = False, period: str = "max"):
    conn = get_conn()
    benchmarks = fetch_benchmarks(conn)
    # keep connection open — reuse for all inserts
    conn.autocommit = False

    if not benchmarks:
        print("  No benchmarks found in benchmark_master. Run seed_benchmarks.py first.")
        conn.close()
        return

    print(f"  Found {len(benchmarks)} benchmarks — fetching '{period}' history from Yahoo Finance\n")

    total_rows = 0
    failed = []

    for benchmark_code, ticker in benchmarks:
        print(f"  [{benchmark_code}]  ticker={ticker!r:25s}", end="", flush=True)

        rows = download_history(ticker, period)

        if not rows:
            print("  ← no data from Yahoo Finance")
            failed.append((benchmark_code, ticker))
            time.sleep(0.3)
            continue

        date_range = f"{rows[0][0]} → {rows[-1][0]}"
        print(f"  {len(rows):>5d} rows  ({date_range})", end="", flush=True)

        if dry_run:
            print("  [DRY RUN — skipping insert]")
            time.sleep(0.3)
            continue

        records = [(benchmark_code, d, v) for d, v in rows]
        sql = """
            INSERT INTO benchmark_nav_history (benchmark_code, nav_date, index_value)
            VALUES %s
            ON CONFLICT (benchmark_code, nav_date) DO UPDATE
                SET index_value = EXCLUDED.index_value
        """
        try:
            with conn.cursor() as cur:
                execute_values(cur, sql, records)
            conn.commit()
            total_rows += len(records)
            print("  ✓")
        except Exception as e:
            conn.rollback()
            print(f"  ✗ DB ERROR: {e}")
            failed.append((benchmark_code, ticker))

        time.sleep(0.3)

    conn.close()

    print()
    if dry_run:
        print(f"  DRY RUN — would have inserted rows for {len(benchmarks) - len(failed)} benchmarks")
    else:
        print(f"  Total rows upserted : {total_rows}")
        if failed:
            print(f"  Failed / no data    : {len(failed)}")
            for code, tk in failed:
                print(f"    - {code} ({tk})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed benchmark_nav_history from Yahoo Finance")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument(
        "--period", default="max",
        help="yfinance period: 1y, 5y, 10y, max (default: max)"
    )
    args = parser.parse_args()

    print("=== Seeding benchmark_nav_history ===\n")
    seed(dry_run=args.dry_run, period=args.period)
    print("\nDone.")
