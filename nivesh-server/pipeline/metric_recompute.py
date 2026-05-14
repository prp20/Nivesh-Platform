"""
pipeline/metric_recompute.py — Price-dependent financial ratio refresh.

Public interface (called by app/routers/pipeline.py):
    recompute_price_dependent_ratios_all()                  — refresh PE/PB/PS for all stocks
    recompute_price_dependent_ratios(stock_id, close)       — single stock recompute
    _get_latest_close(stock_id)                             — helper used by pipeline.py router
    _fetch_stocks_with_ratios()                             — helper used by pipeline.py router

Internal (called by scheduler):
    _run_fund_metrics_pipeline(db)                          — delegates to app/analytics.py

Strategy:
    1. For each stock, read latest close from price_data.
    2. Read EPS and book_value_ps from financial_ratios (latest period).
    3. Compute PE = close / EPS, PB = close / book_value_ps, PS = close / revenue_per_share.
    4. Upsert back to financial_ratios.
"""

import asyncio
import logging
from typing import Optional

from sqlalchemy import select, func as sa_func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Stock, PriceData, FinancialRatio

logger = logging.getLogger(__name__)


# ── Public interface ─────────────────────────────────────────────────────────


async def recompute_price_dependent_ratios_all() -> dict:
    """
    Refresh PE/PB/PS for all active stocks using their latest close price.

    Creates its own DB session.
    """
    async with AsyncSessionLocal() as db:
        from app.crud import get_active_stocks, start_etl_run, finish_etl_run

        run, created = await start_etl_run(db, pipeline_name="metric_recompute", triggered_by="scheduler")
        if not created:
            logger.warning("[metric_recompute] already RUNNING — skipping")
            return {"skipped": True}

        try:
            stocks = await get_active_stocks(db, is_index=False)
            updated = 0
            for stock in stocks:
                close = await _get_latest_close_in_session(db, stock.id)
                if close is None:
                    continue
                result = await recompute_price_dependent_ratios(stock.id, close, db=db)
                if result:
                    updated += 1

            await finish_etl_run(db, run.id, "COMPLETED", records_out=updated)
            return {"updated": updated, "stocks": len(stocks)}
        except Exception as exc:
            logger.exception("[metric_recompute] failed")
            await finish_etl_run(db, run.id, "FAILED", error_msg=str(exc)[:1000])
            raise


async def recompute_price_dependent_ratios(
    stock_id: int,
    close: float,
    db: Optional[AsyncSession] = None,
) -> Optional[dict]:
    """
    Recompute PE/PB/PS for a single stock given its latest close price.

    If db is provided, uses that session; otherwise creates a new one.
    Returns the updated ratio dict or None if no ratio row exists.
    """
    async def _do(session: AsyncSession) -> Optional[dict]:
        from app.crud import upsert_financial_ratios

        # Get latest financial ratio row
        result = await session.execute(
            select(FinancialRatio)
            .where(FinancialRatio.stock_id == stock_id)
            .order_by(desc(FinancialRatio.period_end))
            .limit(1)
        )
        ratio = result.scalar_one_or_none()
        if ratio is None:
            return None

        updates: dict = {
            "stock_id":    ratio.stock_id,
            "period_end":  ratio.period_end,
            "period_type": ratio.period_type,
        }

        if ratio.eps and ratio.eps > 0:
            updates["pe_ratio"] = round(close / float(ratio.eps), 3)
        if ratio.book_value_ps and ratio.book_value_ps > 0:
            updates["pb_ratio"] = round(close / float(ratio.book_value_ps), 3)
        if ratio.revenue_per_share and ratio.revenue_per_share > 0:
            updates["ps_ratio"] = round(close / float(ratio.revenue_per_share), 3)

        if len(updates) > 3:  # at least one ratio was computed
            await upsert_financial_ratios(session, updates)

        return updates

    if db is not None:
        return await _do(db)
    async with AsyncSessionLocal() as session:
        return await _do(session)


async def _get_latest_close(stock_id: int) -> Optional[float]:
    """
    Return the most recent close price for a stock.

    Opens its own session — used by pipeline.py router for ad-hoc queries.
    """
    async with AsyncSessionLocal() as db:
        return await _get_latest_close_in_session(db, stock_id)


async def _fetch_stocks_with_ratios() -> list:
    """
    Return all active stocks that have at least one financial_ratio row.

    Used by pipeline.py router for the /metrics/recompute endpoint.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Stock)
            .join(FinancialRatio, FinancialRatio.stock_id == Stock.id)
            .where(Stock.is_active.is_(True))
            .distinct()
            .order_by(Stock.symbol)
        )
        return list(result.scalars().all())


# ── Internal helpers ─────────────────────────────────────────────────────────


async def _get_latest_close_in_session(
    db: AsyncSession, stock_id: int
) -> Optional[float]:
    """Read max-date close from price_data within an existing session."""
    result = await db.execute(
        select(PriceData.close)
        .where(PriceData.stock_id == stock_id)
        .order_by(desc(PriceData.price_date))
        .limit(1)
    )
    val = result.scalar_one_or_none()
    return float(val) if val is not None else None


# ── Fund metrics pipeline (called by scheduler._run_fund_metrics) ─────────────


async def _run_fund_metrics_pipeline(db: AsyncSession) -> None:
    """
    Recompute all fund + benchmark metrics by delegating to app/analytics.py.

    Called by scheduler._run_fund_metrics() which handles EtlRun lifecycle.
    """
    from app.analytics import compute_all_metrics

    await compute_all_metrics(db)
    logger.info("[fund_metrics] compute_all_metrics completed")
