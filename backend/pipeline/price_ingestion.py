# backend/pipeline/price_ingestion.py
"""
Price data ingestion pipeline.

Fetches OHLCV data from yfinance and stores in price_data table.
Supports both daily incremental ingestion and full historical backfills.
"""

import asyncio
import logging
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from pipeline.audit import audit_job
from app.config import settings
from app.database import raw_connection
from app.constants import (
    PRICE_INGESTION_CHUNK_SIZE,
    PRICE_INGESTION_LOOKBACK_DAYS,
    MAX_API_RETRIES,
    EXPONENTIAL_BACKOFF_BASE,
    API_CALL_TIMEOUT_SECS,
)

logger = logging.getLogger(__name__)


# ─── Main entry point (called by APScheduler) ────────────────────────────────

async def run_daily_price_ingestion():
    """
    Fetch last 5 trading days for all active stocks.

    Runs daily after market close. Uses chunking to avoid rate limits.
    Safe to re-run multiple times (ON CONFLICT DO UPDATE).
    """
    stocks = await _fetch_active_stocks()
    async with audit_job("price_daily_ingestion", records_in=len(stocks)) as audit:
        chunks = [
            stocks[i : i + PRICE_INGESTION_CHUNK_SIZE]
            for i in range(0, len(stocks), PRICE_INGESTION_CHUNK_SIZE)
        ]
        total_upserted = 0
        stocks_processed = 0
        for chunk in chunks:
            count = await _ingest_chunk(chunk, period=f"{PRICE_INGESTION_LOOKBACK_DAYS}d")
            total_upserted += count
            stocks_processed += len(chunk)
            await audit.update_progress(stocks_processed)
            await asyncio.sleep(1)  # Brief pause between chunks to avoid overwhelming database

        audit.records_out = total_upserted
        logger.info(
            f"price_daily_ingestion complete: {total_upserted} rows upserted across {stocks_processed} stocks"
        )


async def run_index_ingestion():
    """Fetches last 5 trading days for all indices."""
    indices = await _fetch_active_stocks(indices_only=True)
    async with audit_job("index_daily_ingestion", records_in=len(indices)) as audit:
        count = await _ingest_chunk(indices, period="5d")
        audit.records_out = count
        await audit.update_progress(len(indices))


# ─── Backfill (run once from seed script) ────────────────────────────────────

async def run_backfill(period: str = "5y"):
    """
    Fetch full price history for all stocks.

    Run once during initial setup or after adding new stocks.
    Uses chunking to avoid rate limits and memory exhaustion.
    Long-running operation (10–30 minutes for 500 stocks).

    Args:
        period: Time period to backfill ("1y", "2y", "3y", "5y", etc.)
    """
    stocks = await _fetch_active_stocks()
    async with audit_job("price_backfill", records_in=len(stocks)) as audit:
        chunks = [
            stocks[i : i + PRICE_INGESTION_CHUNK_SIZE]
            for i in range(0, len(stocks), PRICE_INGESTION_CHUNK_SIZE)
        ]
        total_upserted = 0
        stocks_processed = 0
        for i, chunk in enumerate(chunks):
            count = await _ingest_chunk(chunk, period=period)
            total_upserted += count
            stocks_processed += len(chunk)
            await audit.update_progress(stocks_processed)
            logger.info(
                f"Backfill chunk {i+1}/{len(chunks)} ({stocks_processed}/{len(stocks)} stocks): {count} rows"
            )
            # Polite delay for backfill to avoid overwhelming external API
            await asyncio.sleep(2)
async def run_price_sync_one(symbol: str, period: str = "1y") -> int:
    """Fetches full price history for a single stock to correct data errors."""
    async with raw_connection() as conn:
        row = await conn.fetchrow("SELECT id, symbol, yf_symbol FROM stocks WHERE symbol = $1", symbol.upper())
        if not row:
            logger.error(f"Stock {symbol} not found for sync")
            return 0
        
    stock = dict(row)
    async with audit_job("price_single_refresh", stock_id=stock["id"]) as audit:
        count = await _ingest_chunk([stock], period=period)
        audit.records_out = count
        return count


# ─── Core ingestion logic ─────────────────────────────────────────────────────

async def _ingest_chunk(stocks: list, period: str) -> int:
    """
    Download prices for a batch of stocks and upsert to DB.

    Uses per-stock error tracking so failures don't block other stocks.
    Returns total rows upserted; errors are logged with stock symbol for debugging.
    """
    if not stocks:
        return 0

    tickers_str = " ".join(s["yf_symbol"] for s in stocks)
    df = None

    # Download with exponential backoff retry
    for attempt in range(MAX_API_RETRIES):
        try:
            df = yf.download(
                tickers_str,
                period=period,
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=False,  # Sequential is safer against IP blocks
                timeout=API_CALL_TIMEOUT_SECS,
            )
            if df is not None and not df.empty:
                break
        except Exception as e:
            logger.warning(
                f"yfinance download attempt {attempt+1}/{MAX_API_RETRIES} failed for chunk: {e}"
            )
            if attempt < MAX_API_RETRIES - 1:
                wait_time = EXPONENTIAL_BACKOFF_BASE ** (attempt + 1)
                await asyncio.sleep(wait_time)
            continue

    if df is None or df.empty:
        logger.error(
            f"yfinance failed to download data for {len(stocks)} stocks after {MAX_API_RETRIES} attempts"
        )
        return 0

    # Process each stock, tracking errors per-stock
    total = 0
    errors = []

    for stock in stocks:
        stock_symbol = stock["symbol"]
        try:
            stock_df = _extract_ticker_df(df, stock["yf_symbol"], len(stocks))
            if stock_df is None or stock_df.empty:
                logger.warning(f"No price data from yfinance for {stock_symbol}")
                continue

            # Upsert this stock's prices (wrapped in transaction via ON CONFLICT)
            count = await _upsert_price_rows(stock["id"], stock_df)
            total += count
            logger.info(f"Ingested {count} price rows for {stock_symbol}")

        except Exception as e:
            error_msg = f"Failed to ingest {stock_symbol}: {type(e).__name__}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            # Continue with next stock instead of failing entire chunk
            continue

    if errors:
        logger.warning(
            f"Chunk completed with {len(errors)} errors: {'; '.join(errors)}"
        )

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
            float(row.get("Adj Close", row["Close"])),       # capture nominal vs adjusted
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
