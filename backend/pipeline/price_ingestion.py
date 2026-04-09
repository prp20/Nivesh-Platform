# backend/pipeline/price_ingestion.py
import asyncio
import logging
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from pipeline.audit import audit_job
from app.config import settings
from app.database import raw_connection

logger = logging.getLogger(__name__)

CHUNK_SIZE = 50   # max symbols per yfinance batch call


# ─── Main entry point (called by APScheduler) ────────────────────────────────

async def run_daily_price_ingestion():
    """Fetches last 5 trading days for all active stocks."""
    async with audit_job("price_daily_ingestion") as audit:
        stocks = await _fetch_active_stocks()
        chunks = [stocks[i:i+CHUNK_SIZE] for i in range(0, len(stocks), CHUNK_SIZE)]
        total = 0
        for chunk in chunks:
            count = await _ingest_chunk(chunk, period="5d")
            total += count
            await asyncio.sleep(1)  # brief pause between chunks
        audit.records_out = total
        logger.info(f"price_daily_ingestion complete: {total} rows upserted")


async def run_index_ingestion():
    """Fetches last 5 trading days for all indices."""
    async with audit_job("index_daily_ingestion") as audit:
        indices = await _fetch_active_stocks(indices_only=True)
        count = await _ingest_chunk(indices, period="5d")
        audit.records_out = count


# ─── Backfill (run once from seed script) ────────────────────────────────────

async def run_backfill(period: str = "5y"):
    """Fetches full price history. Run once from scripts/seed/backfill_prices.py."""
    async with audit_job("price_backfill") as audit:
        stocks = await _fetch_active_stocks()
        chunks = [stocks[i:i+CHUNK_SIZE] for i in range(0, len(stocks), CHUNK_SIZE)]
        total = 0
        for i, chunk in enumerate(chunks):
            count = await _ingest_chunk(chunk, period=period)
            total += count
            logger.info(f"Backfill chunk {i+1}/{len(chunks)}: {count} rows")
            await asyncio.sleep(2)  # polite delay for backfill
        audit.records_out = total


# ─── Core ingestion logic ─────────────────────────────────────────────────────

async def _ingest_chunk(stocks: list, period: str) -> int:
    """Download prices for a batch of stocks and upsert to DB."""
    if not stocks:
        return 0

    tickers_str = " ".join(s["yf_symbol"] for s in stocks)
    try:
        df = yf.download(
            tickers_str,
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,    # adjusts for splits and dividends
            progress=False,
            threads=True,
        )
    except Exception as e:
        logger.error(f"yfinance download failed for chunk: {e}")
        return 0

    total = 0
    for stock in stocks:
        try:
            stock_df = _extract_ticker_df(df, stock["yf_symbol"], len(stocks))
            if stock_df is None or stock_df.empty:
                logger.warning(f"No data for {stock['yf_symbol']}")
                continue
            count = await _upsert_price_rows(stock["id"], stock_df)
            total += count
        except Exception as e:
            logger.error(f"Failed to upsert {stock['symbol']}: {e}")

    return total


def _extract_ticker_df(df: pd.DataFrame, yf_symbol: str, num_tickers: int) -> pd.DataFrame:
    """Extract a single ticker's data from a (possibly multi-ticker) DataFrame."""
    if num_tickers == 1:
        # Single ticker: df columns are ['Open', 'High', 'Low', 'Close', 'Volume']
        return df
    try:
        # Multi-ticker: df has MultiIndex columns (ticker, field)
        ticker_df = df[yf_symbol]
        if ticker_df.empty:
            return None
        return ticker_df
    except KeyError:
        return None


async def _upsert_price_rows(stock_id: int, df: pd.DataFrame) -> int:
    """Upsert rows into price_data. Uses ON CONFLICT to handle re-runs safely."""
    rows = []
    for idx, row in df.iterrows():
        if pd.isna(row.get("Close")):
            continue
        rows.append((
            stock_id,
            idx.date() if hasattr(idx, "date") else idx,
            _safe_float(row.get("Open")),
            _safe_float(row.get("High")),
            _safe_float(row.get("Low")),
            float(row["Close"]),
            float(row["Close"]),       # adj_close = close (auto_adjust=True handles this)
            int(row.get("Volume") or 0),
        ))

    if not rows:
        return 0

    sql = """
        INSERT INTO price_data (stock_id, price_date, open, high, low, close, adj_close, volume)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (stock_id, price_date) DO UPDATE SET
            open      = EXCLUDED.open,
            high      = EXCLUDED.high,
            low       = EXCLUDED.low,
            close     = EXCLUDED.close,
            adj_close = EXCLUDED.adj_close,
            volume    = EXCLUDED.volume
    """
    async with raw_connection() as conn:
        await conn.executemany(sql, rows)

    return len(rows)


# ─── DB helpers ──────────────────────────────────────────────────────────────

async def _fetch_active_stocks(indices_only: bool = False) -> list:
    sql = """
        SELECT id, symbol, yf_symbol
        FROM stocks
        WHERE is_active = TRUE
          AND is_index = $1
        ORDER BY id
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql, indices_only)
        return [dict(r) for r in rows]


def _safe_float(v) -> float | None:
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None
