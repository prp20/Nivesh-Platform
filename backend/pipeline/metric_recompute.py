"""
backend/pipeline/metric_recompute.py

Recomputes ONLY the price-dependent financial ratios daily.
These ratios change every trading day because they depend on the current market price:
  - PE Ratio  = latest_close / EPS
  - PB Ratio  = latest_close / Book Value Per Share
  - PS Ratio  = (latest_close × shares) / Revenue  [approximated]
  - Dividend Yield = Dividend / latest_close

Quarterly ratios (ROE, ROCE, D/E, margins, etc.) are NOT touched here.
Those are handled by pipeline/ratio_engine.py after screener.in scraping.

Entry points:
  recompute_price_dependent_ratios_all()         — all stocks (scheduler Mon-Fri 19:00)
  recompute_price_dependent_ratios(stock_id, close) — single stock
"""

import logging
from typing import Optional

from pipeline.audit import audit_job
from app.db_compat import raw_connection, db_execute, db_fetch, db_fetchrow

logger = logging.getLogger(__name__)


# ─── Main entry points ────────────────────────────────────────────────────────

async def recompute_price_dependent_ratios_all() -> dict:
    """Refresh PE/PB/PS/dividend_yield for all active stocks. Called by scheduler."""
    async with audit_job("price_ratio_refresh_all") as audit:
        stocks = await _fetch_stocks_with_ratios()
        success, skipped = 0, 0
        for stock in stocks:
            try:
                close = await _get_latest_close(stock["id"])
                if close is None:
                    skipped += 1
                    continue
                await recompute_price_dependent_ratios(stock["id"], close)
                success += 1
            except Exception as e:
                logger.error(f"Price ratio refresh failed for {stock['symbol']}: {e}")
                skipped += 1
        audit.records_out = success
        logger.info(f"price_ratio_refresh_all: {success} updated, {skipped} skipped")
        return {"updated": success, "skipped": skipped}


async def recompute_price_dependent_ratios(stock_id: int, latest_close: float) -> dict:
    """
    Recompute price-dependent ratios for one stock.
    Reads eps and book_value_ps from the stored financial_ratios row.
    Only updates: pe_ratio, pb_ratio, ps_ratio, dividend_yield.
    """
    stored = await _get_stored_fundamentals(stock_id)
    if not stored:
        logger.debug(f"stock_id={stock_id}: no existing ratio row — skipping price refresh")
        return {}

    eps          = stored.get("eps")
    book_val_ps  = stored.get("book_value_ps")
    # ps_ratio requires revenue + shares — approximate from stored ps_ratio base
    # We store the fully-recomputed ps_ratio if revenue is available in financial_statements
    revenue      = await _get_latest_revenue(stock_id)
    shares       = await _get_shares_outstanding(stock_id)
    dividend     = await _get_latest_dividend(stock_id)

    def safe_div(num, denom):
        if num is None or denom is None or denom == 0:
            return None
        return round(num / denom, 3)

    pe_ratio = safe_div(latest_close, eps) if eps and eps > 0 else None
    pb_ratio = safe_div(latest_close, book_val_ps) if book_val_ps and book_val_ps > 0 else None
    ps_ratio = safe_div(latest_close * (shares or 0), revenue) if revenue and shares else None
    dividend_yield = safe_div(dividend, latest_close) if dividend else None

    updates = {
        "pe_ratio":      pe_ratio,
        "pb_ratio":      pb_ratio,
        "ps_ratio":      ps_ratio,
        "dividend_yield": dividend_yield,
    }

    period_end = stored.get("period_end")
    period_type = stored.get("period_type", "annual")

    if period_end:
        await _update_price_ratios(stock_id, period_end, period_type, updates)

    return updates


# ─── DB helpers ───────────────────────────────────────────────────────────────

async def _fetch_stocks_with_ratios() -> list:
    """All active stocks that have at least one financial_ratios row."""
    sql = """
        SELECT DISTINCT s.id, s.symbol
        FROM stocks s
        JOIN financial_ratios fr ON fr.stock_id = s.id
        WHERE s.is_active = TRUE AND s.is_index = FALSE
        ORDER BY s.id
    """
    async with raw_connection() as conn:
        rows = await db_fetch(conn, sql)
        return [dict(r) for r in rows]


async def _get_latest_close(stock_id: int) -> Optional[float]:
    async with raw_connection() as conn:
        row = await db_fetchrow(conn,
            "SELECT close FROM price_data WHERE stock_id=$1 ORDER BY price_date DESC LIMIT 1",
            (stock_id,)
        )
        return float(row["close"]) if row else None


async def _get_stored_fundamentals(stock_id: int) -> Optional[dict]:
    """Fetch the latest financial_ratios row — we need eps, book_value_ps, period_end."""
    sql = """
        SELECT eps, book_value_ps, period_end, period_type
        FROM financial_ratios
        WHERE stock_id = $1 AND period_type = 'annual'
        ORDER BY period_end DESC
        LIMIT 1
    """
    async with raw_connection() as conn:
        row = await db_fetchrow(conn, sql, (stock_id,))
        return dict(row) if row else None


async def _get_latest_revenue(stock_id: int) -> Optional[float]:
    """Fetch latest annual revenue from financial_statements."""
    sql = """
        SELECT data->>'sales' AS sales, data->>'revenue' AS revenue
        FROM financial_statements
        WHERE stock_id = $1 AND statement_type = 'PL' AND period_type = 'annual'
        ORDER BY period_end DESC
        LIMIT 1
    """
    async with raw_connection() as conn:
        row = await db_fetchrow(conn, sql, (stock_id,))
        if not row:
            return None
        # data stores a single period snapshot (dict, not list)
        val = row["sales"] or row["revenue"]
        try:
            return float(val) if val else None
        except (TypeError, ValueError):
            return None


async def _get_shares_outstanding(stock_id: int) -> Optional[float]:
    """Fetch shares outstanding (in Crores) from financial_statements."""
    sql = """
        SELECT data->>'shares_outstanding' AS shares
        FROM financial_statements
        WHERE stock_id = $1 AND statement_type = 'PL' AND period_type = 'annual'
        ORDER BY period_end DESC
        LIMIT 1
    """
    async with raw_connection() as conn:
        row = await db_fetchrow(conn, sql, (stock_id,))
        if not row or not row["shares"]:
            return None
        try:
            return float(row["shares"])
        except (TypeError, ValueError):
            return None


async def _get_latest_dividend(stock_id: int) -> Optional[float]:
    """
    Fetch latest dividend per share from P&L statement.
    Tries multiple possible field names: dividend_payout, dividend_per_share, dps.
    Returns None if field doesn't exist or value is unparseable.
    """
    sql = """
        SELECT
            COALESCE(data->>'dividend_payout', data->>'dividend_per_share', data->>'dps') AS div
        FROM financial_statements
        WHERE stock_id = $1 AND statement_type = 'PL' AND period_type = 'annual'
        ORDER BY period_end DESC
        LIMIT 1
    """
    async with raw_connection() as conn:
        row = await db_fetchrow(conn, sql, (stock_id,))
        if not row or not row["div"] or row["div"] == "n/a":
            return None
        try:
            return float(row["div"])
        except (TypeError, ValueError):
            return None


async def _update_price_ratios(stock_id: int, period_end, period_type: str, updates: dict):
    """Update only the 4 price-dependent columns in an existing financial_ratios row."""
    sql = """
        UPDATE financial_ratios
        SET
            pe_ratio       = $3,
            pb_ratio       = $4,
            ps_ratio       = $5,
            dividend_yield = $6,
            computed_at    = CURRENT_TIMESTAMP
        WHERE stock_id = $1
          AND period_end = $2
          AND period_type = $7
    """
    async with raw_connection() as conn:
        await db_execute(conn, sql, (
            stock_id, period_end,
            updates.get("pe_ratio"),
            updates.get("pb_ratio"),
            updates.get("ps_ratio"),
            updates.get("dividend_yield"),
            period_type,
        ))
