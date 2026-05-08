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
    """Fetches last 5 trading days for all indices in benchmark_master."""
    indices = await _fetch_benchmark_indices()
    if not indices:
        logger.info("No indices found in benchmark_master to ingest.")
        return

    async with audit_job("index_daily_ingestion", records_in=len(indices)) as audit:
        # Ingest benchmark indices into benchmark_nav_history
        count = await _ingest_benchmarks_chunk(indices, period="5d")
        audit.records_out = count
        await audit.update_progress(len(indices))


# ─── Backfill (run once from seed script) ────────────────────────────────────

async def run_backfill(period: str = "5y", progress_callback=None):
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
            
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(len(chunk), stocks_processed, len(stocks))
                else:
                    progress_callback(len(chunk), stocks_processed, len(stocks))

            logger.info(
                f"Backfill chunk {i+1}/{len(chunks)} ({stocks_processed}/{len(stocks)} stocks): {count} rows"
            )
            # Polite delay for backfill to avoid overwhelming external API
            await asyncio.sleep(2)
async def run_index_backfill(period: str = "5y", progress_callback=None):
    """
    Fetch full price history for all indices in benchmark_master.
    
    Args:
        period: Time period to backfill ("1y", "2y", "3y", "5y", etc.)
    """
    indices = await _fetch_benchmark_indices()
    if not indices:
        logger.info("No indices found in benchmark_master to backfill.")
        return

    async with audit_job("index_backfill", records_in=len(indices)) as audit:
        # For indices, we usually have few (10-20), so we can do them in one batch
        # but for safety against timeout, we use the same chunking if needed.
        count = await _ingest_benchmarks_chunk(indices, period=period)
        audit.records_out = count
        await audit.update_progress(len(indices))
        
        if progress_callback:
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(len(indices), len(indices), len(indices))
            else:
                progress_callback(len(indices), len(indices), len(indices))

        logger.info(f"Index backfill complete: {count} rows for {len(indices)} indices")


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
    """
    if not stocks:
        return 0

    tickers_str = " ".join(s["yf_symbol"] for s in stocks)

    # Fallback logic: if requested period fails/empty, try shorter periods
    periods_to_try = [period]
    if period == "max":
        periods_to_try.extend(["10y", "5y", "2y", "1y"])
    elif period == "10y":
        periods_to_try.extend(["5y", "2y", "1y"])
    elif period == "5y":
        periods_to_try.extend(["2y", "1y"])
    elif period == "2y":
        periods_to_try.append("1y")

    df = None
    actual_period = period

    for p in periods_to_try:
        # Download with exponential backoff retry for current period
        for attempt in range(MAX_API_RETRIES):
            try:
                # yfinance is blocking, run in thread to keep event loop free
                df = await asyncio.to_thread(
                    yf.download,
                    tickers_str,
                    period=p,
                    interval="1d",
                    group_by="ticker",
                    auto_adjust=False,
                    progress=False,
                    threads=False,  # Sequential is safer against IP blocks
                    timeout=API_CALL_TIMEOUT_SECS,
                )
                if df is not None and not df.empty:
                    actual_period = p
                    break
            except Exception as e:
                logger.warning(
                    f"yfinance download attempt {attempt+1}/{MAX_API_RETRIES} failed for chunk (period={p}): {e}"
                )
                if attempt < MAX_API_RETRIES - 1:
                    wait_time = EXPONENTIAL_BACKOFF_BASE ** (attempt + 1)
                    await asyncio.sleep(wait_time)
                continue
        
        if df is not None and not df.empty:
            if p != period:
                logger.info(f"Fallback triggered: data for '{period}' not found, obtained data for '{p}' instead.")
            break

    if df is None or df.empty:
        logger.error(
            f"yfinance failed to download data for {len(stocks)} stocks after trying fallback periods: {periods_to_try}"
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
                logger.warning(f"No price data from yfinance for {stock_symbol} in period {actual_period}")
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
    try:
        # Try direct access (standard case)
        if yf_symbol in df.columns.levels[0]:
            return df[yf_symbol]
        
        # Fallback: exact match in columns regardless of levels
        if yf_symbol in df.columns:
            return df[yf_symbol]
            
        # Case-insensitive level 0 check
        for level_val in df.columns.levels[0]:
            if str(level_val).upper() == yf_symbol.upper():
                return df[level_val]
                
    except (KeyError, AttributeError, IndexError) as e:
        logger.warning(f"Ticker extraction failed for {yf_symbol}: {e}")
        
    return None


async def _ingest_benchmarks_chunk(benchmarks: list, period: str) -> int:
    """Download index values for a batch of benchmarks and upsert to benchmark_nav_history."""
    if not benchmarks:
        return 0

    tickers_str = " ".join(b["yf_symbol"] for b in benchmarks)
    
    # Fallback logic for benchmarks
    periods_to_try = [period]
    if period == "max":
        periods_to_try.extend(["10y", "5y", "2y", "1y"])
    elif period == "10y":
        periods_to_try.extend(["5y", "2y", "1y"])
    elif period == "5y":
        periods_to_try.extend(["2y", "1y"])
    elif period == "2y":
        periods_to_try.append("1y")

    df = None
    for p in periods_to_try:
        for attempt in range(MAX_API_RETRIES):
            try:
                df = await asyncio.to_thread(
                    yf.download,
                    tickers_str,
                    period=p,
                    interval="1d",
                    group_by="ticker",
                    auto_adjust=False,
                    progress=False,
                    threads=False,
                    timeout=API_CALL_TIMEOUT_SECS,
                )
                if df is not None and not df.empty:
                    break
            except Exception as e:
                logger.warning(f"yfinance benchmark download attempt {attempt+1} (period={p}) failed: {e}")
                if attempt < MAX_API_RETRIES - 1:
                    await asyncio.sleep(EXPONENTIAL_BACKOFF_BASE ** (attempt + 1))
                continue
        
        if df is not None and not df.empty:
            break

    if df is None or df.empty:
        logger.error(f"yfinance returned no data for benchmark chunk after trying: {periods_to_try}")
        return 0

    total = 0
    for b in benchmarks:
        symbol = b["yf_symbol"]
        try:
            b_df = _extract_ticker_df(df, symbol, len(benchmarks))
            if b_df is None or b_df.empty:
                logger.warning(f"Could not extract data for benchmark {symbol} from yfinance response")
                continue
            
            count = await _upsert_benchmark_nav_rows(b["benchmark_code"], b_df)
            total += count
            logger.info(f"Ingested {count} index rows for {b['benchmark_code']}")
        except Exception as e:
            logger.error(f"Failed to ingest benchmark {b['benchmark_code']}: {str(e)}")
            continue

    return total


async def _upsert_benchmark_nav_rows(benchmark_code: str, df: pd.DataFrame) -> int:
    """Upsert rows into benchmark_nav_history."""
    rows = []
    skipped = 0
    for idx, row in df.iterrows():
        # Check for both "Close" and "Adj Close" (some indices use one or other)
        close_val = row.get("Close")
        if pd.isna(close_val):
            close_val = row.get("Adj Close")
            
        if pd.isna(close_val):
            skipped += 1
            continue
            
        rows.append((
            benchmark_code,
            idx.date() if hasattr(idx, "date") else idx,
            float(close_val),
        ))

    if skipped > 0:
        logger.debug(f"Skipped {skipped} rows for {benchmark_code} due to missing 'Close' data")

    if not rows:
        return 0

    sql = """
        INSERT INTO benchmark_nav_history (benchmark_code, nav_date, index_value)
        VALUES ($1, $2, $3)
        ON CONFLICT (benchmark_code, nav_date) DO UPDATE SET
            index_value = EXCLUDED.index_value
    """
    async with raw_connection() as conn:
        await conn.executemany(sql, rows)

    return len(rows)


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


async def _fetch_benchmark_indices() -> list:
    """Fetch all active indices from benchmark_master."""
    sql = """
        SELECT benchmark_code, ticker as yf_symbol
        FROM benchmark_master
        WHERE is_active = TRUE
          AND benchmark_type = 'Market Index'
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql)
        return [dict(r) for r in rows]


def _safe_float(v) -> float | None:
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None
