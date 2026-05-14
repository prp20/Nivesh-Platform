"""
pipeline/price_ingestion.py — Yahoo Finance OHLCV ingestion + AMFI NAV sync.

Public interface (called by app/routers/pipeline.py):
    run_daily_price_ingestion()          — last 5 trading days for all non-index stocks
    run_index_ingestion()                — last 5 trading days for is_index=True stocks
    run_backfill(period: str)            — full history backfill for all non-index stocks
    run_price_sync_one(symbol, period)   — sync single stock, returns upserted count

Internal (called by pipeline/scheduler.py):
    _run_benchmark_nav_pipeline(db)      — daily benchmark NAV from yfinance
    _sync_amfi_navs(db)                  — daily AMFI mutual fund NAV sync

Strategy:
    Watermark-based delta: per stock, fetch max(price_date) then download
    only new rows.  Falls back to `period` argument for backfill jobs.

    yfinance calls are wrapped in asyncio.to_thread() so they don't block
    the async event loop.
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import (
    get_active_stocks,
    upsert_price_data,
    start_etl_run,
    finish_etl_run,
)
from app.models import PriceData, Stock, BenchmarkMaster, BenchmarkNavHistory
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Number of stocks to process before a brief yield to the event loop
_BATCH_YIELD_EVERY = 20


# ── Public interface ─────────────────────────────────────────────────────────


async def run_daily_price_ingestion() -> dict:
    """
    Ingest last 5 trading days of OHLCV for all active non-index stocks.

    Creates its own DB session; safe to call from the scheduler or HTTP trigger.
    """
    async with AsyncSessionLocal() as db:
        run, created = await start_etl_run(db, pipeline_name="yf_price", triggered_by="scheduler")
        if not created:
            logger.warning("[yf_price] already RUNNING — skipping")
            return {"skipped": True}
        try:
            stocks = await get_active_stocks(db, is_index=False)
            total_upserted = await _ingest_stocks(db, stocks, period="5d")
            await finish_etl_run(db, run.id, "COMPLETED", records_out=total_upserted)
            return {"upserted": total_upserted, "stocks": len(stocks)}
        except Exception as exc:
            logger.exception("[yf_price] failed")
            await finish_etl_run(db, run.id, "FAILED", error_msg=str(exc)[:1000])
            raise


async def run_index_ingestion() -> dict:
    """Ingest last 5 trading days of OHLCV for all active index stocks."""
    async with AsyncSessionLocal() as db:
        run, created = await start_etl_run(db, pipeline_name="yf_index", triggered_by="scheduler")
        if not created:
            logger.warning("[yf_index] already RUNNING — skipping")
            return {"skipped": True}
        try:
            stocks = await get_active_stocks(db, is_index=True)
            total_upserted = await _ingest_stocks(db, stocks, period="5d")
            await finish_etl_run(db, run.id, "COMPLETED", records_out=total_upserted)
            return {"upserted": total_upserted, "stocks": len(stocks)}
        except Exception as exc:
            logger.exception("[yf_index] failed")
            await finish_etl_run(db, run.id, "FAILED", error_msg=str(exc)[:1000])
            raise


async def run_backfill(period: str = "5y") -> dict:
    """
    Full history backfill for all active non-index stocks.

    period: yfinance period string — '1y', '2y', '5y', 'max'
    """
    async with AsyncSessionLocal() as db:
        run, created = await start_etl_run(db, pipeline_name="yf_backfill", triggered_by="manual")
        if not created:
            logger.warning("[yf_backfill] already RUNNING — skipping")
            return {"skipped": True}
        try:
            stocks = await get_active_stocks(db, is_index=False)
            total_upserted = await _ingest_stocks(db, stocks, period=period, force=True)
            await finish_etl_run(db, run.id, "COMPLETED", records_out=total_upserted)
            return {"upserted": total_upserted, "stocks": len(stocks)}
        except Exception as exc:
            logger.exception("[yf_backfill] failed")
            await finish_etl_run(db, run.id, "FAILED", error_msg=str(exc)[:1000])
            raise


async def run_price_sync_one(symbol: str, period: str = "1mo") -> int:
    """
    Sync a single stock by symbol.  Returns the number of rows upserted.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Stock).where(Stock.symbol == symbol, Stock.is_active.is_(True))
        )
        stock = result.scalar_one_or_none()
        if stock is None:
            raise ValueError(f"Active stock not found: {symbol}")
        return await _sync_one_stock(db, stock, period=period, force=True)


# ── Internal helpers ─────────────────────────────────────────────────────────


async def _ingest_stocks(
    db: AsyncSession,
    stocks: list,
    period: str,
    force: bool = False,
) -> int:
    """Download and upsert OHLCV for a list of Stock ORM objects."""
    total = 0
    for i, stock in enumerate(stocks):
        try:
            n = await _sync_one_stock(db, stock, period=period, force=force)
            total += n
        except Exception as exc:
            logger.warning(f"[yf_price] {stock.symbol} failed — {exc}")
        # Yield to event loop every _BATCH_YIELD_EVERY stocks
        if i % _BATCH_YIELD_EVERY == 0 and i > 0:
            await asyncio.sleep(0)
    return total


async def _sync_one_stock(
    db: AsyncSession,
    stock,
    period: str,
    force: bool = False,
) -> int:
    """
    Download yfinance history for one stock and upsert into price_data.

    If force=False, uses watermark: fetches only rows after max(price_date).
    Returns number of rows upserted.
    """
    import pandas as pd

    yf_symbol = stock.yf_symbol

    # Determine download range
    start_date: Optional[date] = None
    if not force:
        wm_result = await db.execute(
            select(sa_func.max(PriceData.price_date)).where(
                PriceData.stock_id == stock.id
            )
        )
        watermark: Optional[date] = wm_result.scalar_one_or_none()
        if watermark is not None:
            start_date = watermark + timedelta(days=1)
            if start_date > date.today():
                return 0  # already up to date

    # Download in a thread to avoid blocking the event loop
    df = await asyncio.to_thread(_yf_download, yf_symbol, period, start_date)

    if df is None or df.empty:
        return 0

    rows = _df_to_price_rows(df, stock.id)
    if not rows:
        return 0

    return await upsert_price_data(db, rows)


def _yf_download(yf_symbol: str, period: str, start_date: Optional[date]):
    """Blocking yfinance download — run inside asyncio.to_thread()."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(yf_symbol)
        if start_date is not None:
            df = ticker.history(start=start_date.isoformat(), auto_adjust=True)
        else:
            df = ticker.history(period=period, auto_adjust=True)
        return df
    except Exception as exc:
        logger.warning(f"[yf_download] {yf_symbol} → {exc}")
        return None


def _df_to_price_rows(df, stock_id: int) -> list:
    """Convert a yfinance DataFrame to list[dict] for upsert_price_data."""
    import pandas as pd

    rows = []
    df.index = pd.to_datetime(df.index).normalize()
    for ts, row in df.iterrows():
        rows.append(
            {
                "stock_id":   stock_id,
                "price_date": ts.date(),
                "open":       float(row["Open"])   if not _is_nan(row.get("Open"))   else None,
                "high":       float(row["High"])   if not _is_nan(row.get("High"))   else None,
                "low":        float(row["Low"])    if not _is_nan(row.get("Low"))    else None,
                "close":      float(row["Close"])  if not _is_nan(row.get("Close"))  else None,
                "adj_close":  float(row["Close"])  if not _is_nan(row.get("Close"))  else None,
                "volume":     int(row["Volume"])   if not _is_nan(row.get("Volume")) else None,
            }
        )
    return [r for r in rows if r["close"] is not None]


def _is_nan(val) -> bool:
    import math
    try:
        return val is None or math.isnan(float(val))
    except (TypeError, ValueError):
        return True


# ── Benchmark NAV pipeline (called by scheduler._run_benchmark_nav) ──────────


async def _run_benchmark_nav_pipeline(db: AsyncSession) -> None:
    """
    Fetch latest NAV for all benchmark indices and upsert into benchmark_nav_history.

    Called by scheduler._run_benchmark_nav() which handles EtlRun lifecycle.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    benchmarks_result = await db.execute(select(BenchmarkMaster))
    benchmarks = list(benchmarks_result.scalars().all())
    if not benchmarks:
        logger.info("[benchmark_nav] no benchmarks in DB — skipping")
        return

    upserted = 0
    for bm in benchmarks:
        if not bm.yf_symbol:
            continue
        df = await asyncio.to_thread(_yf_download, bm.yf_symbol, "5d", None)
        if df is None or df.empty:
            continue

        import pandas as pd
        df.index = pd.to_datetime(df.index).normalize()
        for ts, row in df.iterrows():
            close_val = row.get("Close")
            if _is_nan(close_val):
                continue
            stmt = pg_insert(BenchmarkNavHistory).values(
                benchmark_code=bm.benchmark_code,
                nav_date=ts.date(),
                index_value=float(close_val),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["benchmark_code", "nav_date"],
                set_={"index_value": stmt.excluded.index_value},
            )
            await db.execute(stmt)
            upserted += 1

    await db.commit()
    logger.info(f"[benchmark_nav] upserted {upserted} rows for {len(benchmarks)} benchmarks")


# ── AMFI NAV sync (called by scheduler._run_amfi_nav) ───────────────────────


async def _sync_amfi_navs(db: AsyncSession) -> int:
    """
    Delegate to existing app/sync.py bulk AMFI sync logic.

    sync_all_funds() handles per-fund EtlRun tracking internally.
    Returns 0 — the per-fund run records are the canonical audit trail.
    """
    from app.sync import sync_all_funds

    await sync_all_funds(db)
    return 0
