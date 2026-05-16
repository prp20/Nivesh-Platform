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
    Recompute fund_metrics for every active fund.

    For each fund:
      1. Fetch NAV history from fund_nav_history (up to 3 years).
      2. Optionally fetch benchmark NAV history if fund has a benchmark_index_code.
      3. Call analytics.compute_all_metrics (sync, CPU-bound) in a thread executor.
      4. Upsert results into fund_metrics.

    Called by scheduler._run_fund_metrics() which manages the EtlRun lifecycle.
    """
    import asyncio
    from sqlalchemy import select as sa_select
    from app.analytics import compute_all_metrics
    from app.crud import get_fund_nav_history, get_benchmark_nav_history, upsert_fund_metrics
    from app.models import FundMaster

    result = await db.execute(
        sa_select(FundMaster).where(FundMaster.is_active.is_(True))
    )
    funds = result.scalars().all()
    logger.info("[fund_metrics] Computing metrics for %d active funds", len(funds))

    loop = asyncio.get_event_loop()
    updated = 0

    for fund in funds:
        try:
            nav_rows = await get_fund_nav_history(db, fund.scheme_code, limit=1100)
            if not nav_rows:
                continue

            nav_history = [
                {"nav_date": row.nav_date.isoformat(), "nav_value": float(row.nav_value)}
                for row in nav_rows
            ]

            benchmark_history = None
            if fund.benchmark_index_code:
                bench_rows = await get_benchmark_nav_history(
                    db, fund.benchmark_index_code, limit=1100
                )
                if bench_rows:
                    benchmark_history = [
                        {"nav_date": row.nav_date.isoformat(), "index_value": float(row.index_value)}
                        for row in bench_rows
                    ]

            # compute_all_metrics is synchronous and CPU-bound — run off the event loop
            metrics = await loop.run_in_executor(
                None, compute_all_metrics, nav_history, benchmark_history
            )
            if not metrics:
                continue

            metrics_row = {k: v for k, v in {
                "scheme_code":          fund.scheme_code,
                "current_nav":          metrics.get("current_nav"),
                "nav_date":             metrics.get("nav_date"),
                "standard_deviation":   metrics.get("std_dev"),
                "sharpe_ratio":         metrics.get("sharpe"),
                "sortino_ratio":        metrics.get("sortino"),
                "maximum_drawdown":     metrics.get("max_drawdown"),
                "cagr_3year":           metrics.get("cagr_3year"),
                "cagr_5year":           metrics.get("cagr_5year"),
                "absolute_return_1y":   metrics.get("absolute_return_1y"),
                "absolute_return_3y":   metrics.get("absolute_return_3y"),
                "absolute_return_5y":   metrics.get("absolute_return_5y"),
                "absolute_return_10y":  metrics.get("absolute_return_10y"),
                "short_term_return_6m": metrics.get("short_term_return_6m"),
                "alpha":                metrics.get("alpha"),
                "beta":                 metrics.get("beta"),
                "upside_capture":       metrics.get("upside_capture"),
                "downside_capture":     metrics.get("downside_capture"),
                "tracking_error":       metrics.get("tracking_error"),
                "information_ratio":    metrics.get("information_ratio"),
            }.items() if v is not None}

            await upsert_fund_metrics(db, metrics_row)
            updated += 1
        except Exception as exc:
            logger.error("[fund_metrics] Failed for %s: %s", fund.scheme_code, exc)

    logger.info("[fund_metrics] Completed: %d/%d funds updated", updated, len(funds))
