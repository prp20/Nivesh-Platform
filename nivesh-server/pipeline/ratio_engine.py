"""
pipeline/ratio_engine.py — Financial ratio computation from financial_statements.

Public interface (called by app/routers/pipeline.py):
    run_ratio_compute_all()                     — compute ratios for all active stocks
    compute_ratios_for_stock(stock_id, close)   — single stock ratio computation

Logic:
    1. Read all FinancialStatement rows for a stock (PL, BS, CF — annual).
    2. Extract key line items from the JSONB `data` field.
    3. Compute 30+ financial ratios.
    4. Upsert into financial_ratios (one row per period_end + period_type).

The `data` field schema follows the screener.in label mapping used in
fundamental_scraper.py — keys are the screener table row labels as-is.
"""

import asyncio
import logging
from datetime import date
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Stock, FinancialStatement, PriceData
from app.crud import (
    get_active_stocks,
    upsert_financial_ratios,
    start_etl_run,
    finish_etl_run,
)

logger = logging.getLogger(__name__)


# ── Public interface ─────────────────────────────────────────────────────────


async def run_ratio_compute_all() -> dict:
    """Compute financial ratios for all active non-index stocks."""
    async with AsyncSessionLocal() as db:
        run, created = await start_etl_run(
            db, pipeline_name="ratio_engine", triggered_by="scheduler"
        )
        if not created:
            logger.warning("[ratio_engine] already RUNNING — skipping")
            return {"skipped": True}

        try:
            stocks = await get_active_stocks(db, is_index=False)
            succeeded = 0
            failed = 0
            for stock in stocks:
                try:
                    close = await _get_latest_close(db, stock.id)
                    rows = await compute_ratios_for_stock(stock.id, close, db=db)
                    succeeded += len(rows)
                except Exception as exc:
                    logger.warning(f"[ratio_engine] {stock.symbol} failed — {exc}")
                    failed += 1

            status = "COMPLETED" if failed == 0 else "PARTIAL"
            await finish_etl_run(
                db, run.id, status,
                records_out=succeeded,
                error_msg=f"{failed} stocks failed" if failed else None,
            )
            return {"succeeded": succeeded, "failed": failed}

        except Exception as exc:
            logger.exception("[ratio_engine] pipeline-level failure")
            await finish_etl_run(db, run.id, "FAILED", error_msg=str(exc)[:1000])
            raise


async def compute_ratios_for_stock(
    stock_id: int,
    close: Optional[float] = None,
    db: Optional[AsyncSession] = None,
) -> list:
    """
    Compute financial ratios for a single stock from its financial statements.

    Returns a list of ratio dicts (one per period), each upserted to DB.
    """
    async def _do(session: AsyncSession) -> list:
        statements = await _get_statements(session, stock_id)
        if not statements:
            return []

        # Group by period_end
        by_period: dict = {}
        for stmt in statements:
            key = (stmt.period_end, stmt.period_type)
            if key not in by_period:
                by_period[key] = {}
            by_period[key][stmt.statement_type] = stmt.data or {}

        upserted = []
        for (period_end, period_type), data_by_type in by_period.items():
            ratio_row = _compute_ratios(
                stock_id=stock_id,
                period_end=period_end,
                period_type=period_type,
                pl=data_by_type.get("PL", {}),
                bs=data_by_type.get("BS", {}),
                cf=data_by_type.get("CF", {}),
                close=close,
            )
            await upsert_financial_ratios(session, ratio_row)
            upserted.append(ratio_row)

        return upserted

    if db is not None:
        return await _do(db)
    async with AsyncSessionLocal() as session:
        return await _do(session)


# ── Data fetchers ─────────────────────────────────────────────────────────────


async def _get_statements(db: AsyncSession, stock_id: int) -> list:
    result = await db.execute(
        select(FinancialStatement)
        .where(
            FinancialStatement.stock_id == stock_id,
            FinancialStatement.period_type == "annual",
        )
        .order_by(FinancialStatement.period_end)
    )
    return list(result.scalars().all())


async def _get_latest_close(db: AsyncSession, stock_id: int) -> Optional[float]:
    result = await db.execute(
        select(PriceData.close)
        .where(PriceData.stock_id == stock_id)
        .order_by(desc(PriceData.price_date))
        .limit(1)
    )
    val = result.scalar_one_or_none()
    return float(val) if val is not None else None


# ── Ratio computation ─────────────────────────────────────────────────────────


def _f(data: dict, *keys, fallback=None) -> Optional[float]:
    """
    Extract a float from a JSONB data dict by trying multiple key names.

    screener.in uses human-readable labels as keys (e.g. 'Net Profit', 'EPS').
    """
    for key in keys:
        val = data.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return fallback


def _safe_div(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None or den == 0:
        return None
    return round(num / den, 3)


def _strip_plus(data: dict) -> dict:
    """
    Normalize screener.in field names by stripping trailing '+' aggregation markers.

    screener.in appends '+' to aggregated/multi-year fields (e.g. 'Sales+', 'Net Profit+',
    'Borrowings+') but not to non-aggregated fields ('Equity Capital', 'Total Assets').
    Stripping the suffix lets _f() match keys without needing '+' variants.
    """
    return {k.rstrip("+"): v for k, v in data.items()}


def _compute_ratios(
    stock_id: int,
    period_end: date,
    period_type: str,
    pl: dict,
    bs: dict,
    cf: dict,
    close: Optional[float],
) -> dict:
    """
    Compute all financial ratios from P&L, Balance Sheet, and Cash Flow data.

    Key screener.in labels used:
      PL: 'Revenue', 'Sales', 'Net Profit', 'EPS', 'Interest', 'Dividend Payout %'
      BS: 'Total Assets', 'Total Equity', 'Total Debt', 'Equity Capital',
          'Reserves', 'Book Value'
      CF: 'Cash from Operations', 'Cash from Operating Activity', 'Capex'
    """
    # Normalize screener.in keys — strip trailing '+' aggregation markers
    pl = _strip_plus(pl)
    bs = _strip_plus(bs)
    cf = _strip_plus(cf)

    # ── P&L line items ────────────────────────────────────────────────────────
    revenue      = _f(pl, "Revenue", "Sales", "Net Sales")
    net_profit   = _f(pl, "Net Profit", "PAT")
    ebitda       = _f(pl, "EBITDA", "Operating Profit")
    interest     = _f(pl, "Interest", "Finance Cost")
    depreciation = _f(pl, "Depreciation", "Depreciation & Amortisation")
    tax          = _f(pl, "Tax", "Tax %")
    eps          = _f(pl, "EPS", "EPS in Rs")
    div_payout   = _f(pl, "Dividend Payout %", "Payout %")
    dps          = _f(pl, "Dividend Per Share", "DPS")

    # ── Balance sheet line items ───────────────────────────────────────────────
    equity_capital = _f(bs, "Equity Capital")
    reserves       = _f(bs, "Reserves")
    total_debt     = _f(bs, "Total Debt", "Borrowings")
    total_assets   = _f(bs, "Total Assets", "Balance Sheet Size")
    book_value     = _f(bs, "Book Value", "Book Value Per Share")

    # screener.in has no combined 'Total Equity' field — derive from components
    total_equity = _f(bs, "Total Equity", "Shareholders Equity")
    if total_equity is None and equity_capital is not None and reserves is not None:
        total_equity = equity_capital + reserves
    elif total_equity is None and equity_capital is not None:
        total_equity = equity_capital

    # Book value per share: screener.in doesn't store this; derive from total equity / shares
    # Shares = equity_capital (Cr) * 1e7 / par_value; par usually ₹10 → shares = equity_capital * 1e6
    book_value = _f(bs, "Book Value", "Book Value Per Share")

    # ── Cash flow line items ──────────────────────────────────────────────────
    cfo   = _f(cf, "Cash from Operations", "Operating Cash Flow", "Cash from Operating Activity")
    capex = _f(cf, "Capex", "Capital Expenditure", "Fixed Assets Purchased")
    if capex is not None:
        capex = abs(capex)  # screener shows capex as negative

    # ── Derived metrics ───────────────────────────────────────────────────────
    # Use computed FCF (cfo - capex) when both available; fall back to screener's own FCF field
    fcf = (cfo - capex) if cfo is not None and capex is not None else _f(cf, "Free Cash Flow")

    # Shares outstanding from equity capital (in crores, assume par ₹10)
    shares = (equity_capital * 1e7 / 10) if equity_capital else None  # shares count

    # Derive book value per share from total equity when not directly available
    if book_value is None and total_equity is not None and shares:
        book_value = round(total_equity * 1e7 / shares, 2)

    # Revenue per share
    revenue_ps = _safe_div(revenue, shares / 1e7 if shares else None) if shares else None

    # ── Ratios ─────────────────────────────────────────────────────────────────
    row: dict = {
        "stock_id":    stock_id,
        "period_end":  period_end,
        "period_type": period_type,
    }

    row["eps"]             = eps
    row["book_value_ps"]   = book_value
    row["revenue_per_share"] = revenue_ps

    # Profitability
    row["pat_margin"]       = _safe_div(net_profit, revenue)
    row["ebitda_margin"]    = _safe_div(ebitda, revenue)
    row["operating_margin"] = _safe_div(ebitda, revenue)

    # Returns
    row["roe"]  = _safe_div(net_profit, total_equity) if total_equity else None
    row["roa"]  = _safe_div(net_profit, total_assets) if total_assets else None

    # ROCE = EBIT / Capital Employed
    ebit = (ebitda - depreciation) if ebitda and depreciation else ebitda
    cap_employed = (total_equity + total_debt) if total_equity and total_debt else total_equity
    row["roce"] = _safe_div(ebit, cap_employed) if ebit else None

    # Leverage
    row["debt_equity"] = _safe_div(total_debt, total_equity)
    row["interest_cov"] = _safe_div(ebit, interest) if ebit and interest else None

    # FCF metrics
    row["fcf"]          = fcf
    row["fcf_margin"]   = _safe_div(fcf, revenue) if fcf is not None and revenue else None
    row["cfo_to_pat"]   = _safe_div(cfo, net_profit) if cfo and net_profit else None

    # Capex ratios
    row["capex_to_revenue"]     = _safe_div(capex, revenue) if capex and revenue else None
    row["capex_to_depreciation"] = _safe_div(capex, depreciation) if capex and depreciation else None

    # Dividend
    row["dividend_per_share"]    = dps
    row["dividend_payout_ratio"] = div_payout

    # Price-dependent ratios (if close available)
    if close:
        row["pe_ratio"] = _safe_div(close, eps) if eps and eps > 0 else None
        row["pb_ratio"] = _safe_div(close, book_value) if book_value and book_value > 0 else None
        row["ps_ratio"] = _safe_div(close, revenue_ps) if revenue_ps and revenue_ps > 0 else None
        row["dividend_yield"] = round(dps / close * 100, 4) if dps and close else None

    # Market cap in crores
    if close and shares:
        row["market_cap"] = round(close * shares / 1e7, 4)

    return row
