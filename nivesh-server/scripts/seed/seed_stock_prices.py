"""
seed_stock_prices.py — Backfill historical OHLCV price data for all stocks.

Reads the stocks table, downloads closing prices from Yahoo Finance (yfinance),
and upserts into price_data. Processes stocks in batches to avoid rate limits.

Prerequisites:
  - stocks table must be seeded first (run seed_stocks.py)
  - pip install "yfinance>=0.2.40" psycopg2-binary tqdm

Usage:
  export DATABASE_URL="postgresql://postgres.[ref]:[pwd]@..."
  python scripts/seed/seed_stock_prices.py [--period 5y] [--dry-run] [--batch-size 20]

Period options: 1y, 2y, 3y, 5y, 10y, max  (default: 5y)

Expected runtime: 20–40 minutes for ~500 stocks (network-dependent).
"""
import os
import sys
import time
import argparse
import logging

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

try:
    import yfinance as yf
except ImportError:
    print("yfinance not installed. Run: pip install 'yfinance>=0.2.40'")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    # tqdm is optional — fall back to plain print
    tqdm = None

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BATCH_DELAY_SECS = 1.5   # pause between batches (be polite to Yahoo Finance)
MAX_RETRIES      = 3


def get_db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL is not set.")
        sys.exit(1)
    # psycopg2 uses postgresql://, not postgresql+asyncpg://
    return url.replace("+asyncpg", "")


def fetch_active_stocks(conn) -> list[dict]:
    """Return all active, non-index stocks with their yf_symbol."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, symbol, yf_symbol
            FROM   stocks
            WHERE  is_active = TRUE
              AND  is_index  = FALSE
              AND  yf_symbol IS NOT NULL
              AND  yf_symbol <> ''
            ORDER  BY symbol
        """)
        rows = cur.fetchall()
    return [{"id": r[0], "symbol": r[1], "yf_symbol": r[2]} for r in rows]


def download_batch(tickers: list[str], period: str) -> dict:
    """
    Download OHLCV for a list of yf_symbols in one yfinance call.
    Returns {yf_symbol: DataFrame} mapping (only non-empty DataFrames).
    """
    if not tickers:
        return {}

    for attempt in range(MAX_RETRIES):
        try:
            raw = yf.download(
                tickers,
                period=period,
                auto_adjust=False,
                progress=False,
                threads=True,
            )
            break
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                logger.warning(f"Batch download failed after {MAX_RETRIES} attempts: {e}")
                return {}
            wait = 2 ** attempt
            logger.warning(f"Attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)

    result = {}
    if raw.empty:
        return result

    # Single ticker: yf.download returns a flat DataFrame
    if len(tickers) == 1:
        ticker = tickers[0]
        if not raw.empty:
            result[ticker] = raw
        return result

    # Multiple tickers: columns are MultiIndex (metric, ticker)
    for ticker in tickers:
        try:
            df = raw.xs(ticker, axis=1, level=1).dropna(subset=["Close"])
            if not df.empty:
                result[ticker] = df
        except (KeyError, TypeError):
            continue

    return result


def upsert_rows(conn, rows: list[dict], dry_run: bool) -> int:
    """Bulk-upsert price_data rows. Returns count inserted/updated."""
    if not rows or dry_run:
        return len(rows) if dry_run else 0

    sql = """
        INSERT INTO price_data (stock_id, price_date, open, high, low, close, adj_close, volume)
        VALUES %s
        ON CONFLICT (stock_id, price_date)
        DO UPDATE SET
            open      = EXCLUDED.open,
            high      = EXCLUDED.high,
            low       = EXCLUDED.low,
            close     = EXCLUDED.close,
            adj_close = EXCLUDED.adj_close,
            volume    = EXCLUDED.volume
    """
    values = [
        (
            r["stock_id"],
            r["price_date"],
            r["open"],
            r["high"],
            r["low"],
            r["close"],
            r["adj_close"],
            r["volume"],
        )
        for r in rows
    ]
    with conn.cursor() as cur:
        execute_values(cur, sql, values, page_size=500)
    conn.commit()
    return len(rows)


def safe_float(val) -> float | None:
    """Convert a value to float, returning None on NaN/None."""
    try:
        import math
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def safe_int(val) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def build_rows(stock_id: int, df) -> list[dict]:
    """Convert a yfinance DataFrame into price_data row dicts."""
    rows = []
    for ts, row in df.iterrows():
        close = safe_float(row.get("Close") or row.get("Adj Close"))
        if close is None:
            continue
        rows.append({
            "stock_id":   stock_id,
            "price_date": ts.date(),
            "open":       safe_float(row.get("Open")),
            "high":       safe_float(row.get("High")),
            "low":        safe_float(row.get("Low")),
            "close":      close,
            "adj_close":  safe_float(row.get("Adj Close")),
            "volume":     safe_int(row.get("Volume")),
        })
    return rows


def seed(period: str = "5y", dry_run: bool = False, batch_size: int = 20):
    conn = psycopg2.connect(get_db_url())
    conn.autocommit = False

    stocks = fetch_active_stocks(conn)
    if not stocks:
        print("No active stocks found. Run seed_stocks.py first.")
        conn.close()
        return

    print(f"Fetching {period} price history for {len(stocks)} stocks "
          f"(batch_size={batch_size}){'  [DRY RUN]' if dry_run else ''}...")

    # Build {yf_symbol: stock_id} lookup
    yf_to_id = {s["yf_symbol"]: s["id"] for s in stocks}
    yf_symbols = list(yf_to_id.keys())

    batches = [yf_symbols[i:i + batch_size] for i in range(0, len(yf_symbols), batch_size)]

    total_rows   = 0
    failed_syms  = []

    iter_batches = (
        tqdm(batches, desc="Batches", unit="batch") if tqdm else batches
    )

    for batch in iter_batches:
        data = download_batch(batch, period)

        batch_rows = []
        for yf_sym in batch:
            if yf_sym not in data:
                failed_syms.append(yf_sym)
                continue
            df = data[yf_sym]
            stock_id = yf_to_id[yf_sym]
            rows = build_rows(stock_id, df)
            if rows:
                batch_rows.extend(rows)
            else:
                failed_syms.append(yf_sym)

        n = upsert_rows(conn, batch_rows, dry_run)
        total_rows += n

        time.sleep(BATCH_DELAY_SECS)

    conn.close()

    print(f"\n{'[DRY RUN] Would upsert' if dry_run else 'Upserted'} {total_rows} rows "
          f"across {len(stocks) - len(failed_syms)} stocks.")
    if failed_syms:
        print(f"No data for {len(failed_syms)} symbols: {', '.join(failed_syms[:20])}"
              + (" ..." if len(failed_syms) > 20 else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed stock price history from Yahoo Finance")
    parser.add_argument("--period",     default="5y",
                        choices=["1y", "2y", "3y", "5y", "10y", "max"],
                        help="History window (default: 5y)")
    parser.add_argument("--dry-run",    action="store_true",
                        help="Preview row counts without writing")
    parser.add_argument("--batch-size", type=int, default=20,
                        help="Stocks per yfinance batch call (default: 20)")
    args = parser.parse_args()

    seed(period=args.period, dry_run=args.dry_run, batch_size=args.batch_size)
