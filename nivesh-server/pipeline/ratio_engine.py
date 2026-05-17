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

        # Compute ratios for each period; sort ascending so YoY growth can look back
        ratio_rows = []
        for (period_end, period_type), data_by_type in sorted(by_period.items()):
            # Skip periods that have no P&L data (e.g. a Sep quarterly BS without
            # a matching annual PL — screener.in publishes interim BS between annual PL releases)
            if not data_by_type.get("PL"):
                logger.debug(
                    "[ratio_engine] stock_id=%s period=%s — no PL data, skipping ratio computation",
                    stock_id, period_end,
                )
                continue
            ratio_row = _compute_ratios(
                stock_id=stock_id,
                period_end=period_end,
                period_type=period_type,
                pl=data_by_type.get("PL", {}),
                bs=data_by_type.get("BS", {}),
                cf=data_by_type.get("CF", {}),
                close=close,
            )
            ratio_rows.append(ratio_row)

        # Compute YoY growth: compare each period to the prior period ~12 months back
        _fill_yoy_growth(ratio_rows)

        # Strip private stash keys before DB upsert
        _STASH_KEYS = {"_revenue", "_net_profit"}
        upserted = []
        for ratio_row in ratio_rows:
            db_row = {k: v for k, v in ratio_row.items() if k not in _STASH_KEYS}
            await upsert_financial_ratios(session, db_row)
            upserted.append(db_row)

        return upserted

    if db is not None:
        return await _do(db)
    async with AsyncSessionLocal() as session:
        return await _do(session)


def _fill_yoy_growth(rows: list) -> None:
    """
    Mutate rows in-place: fill revenue_growth, pat_growth, eps_growth using
    the prior period ~12 months back.  rows must be sorted ascending by period_end.
    """
    from datetime import timedelta

    for i, curr in enumerate(rows):
        if curr.get("period_type") != "annual":
            continue
        curr_end = curr["period_end"]
        # Find the row whose period_end is closest to 12 months prior
        target = curr_end.replace(year=curr_end.year - 1)
        prior = None
        for j in range(i - 1, -1, -1):
            cand = rows[j]
            if cand.get("period_type") != "annual":
                continue
            delta = abs((cand["period_end"] - target).days)
            if delta <= 90:  # within 3 months of the same period last year
                prior = cand
                break
        if prior is None:
            continue

        def _growth(curr_val, prev_val):
            if curr_val is None or prev_val is None or prev_val == 0:
                return None
            return round((curr_val - prev_val) / abs(prev_val), 4)

        # Revenue growth: derive from revenue_per_share × shares if absolute not stored
        curr_rev = curr.get("_revenue")
        prev_rev = prior.get("_revenue")
        curr["revenue_growth"] = _growth(curr_rev, prev_rev)
        curr["pat_growth"]     = _growth(curr.get("_net_profit"), prior.get("_net_profit"))
        curr["eps_growth"]     = _growth(curr.get("eps"), prior.get("eps"))


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
    return {k.rstrip("+").strip(): v for k, v in data.items()}


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
    revenue      = _f(pl, "Revenue", "Sales", "Net Sales", "Net Revenue")
    net_profit   = _f(pl, "Net Profit", "PAT", "Profit after Tax")
    ebitda       = _f(pl, "EBITDA", "Operating Profit")
    interest     = _f(pl, "Interest", "Finance Cost", "Finance Costs", "Interest Expense")
    depreciation = _f(pl, "Depreciation", "Depreciation & Amortisation", "D&A")
    tax          = _f(pl, "Tax", "Tax %")
    eps          = _f(pl, "EPS", "EPS in Rs", "Basic EPS")
    div_payout   = _f(pl, "Dividend Payout %", "Payout %")
    dps          = _f(pl, "Dividend Per Share", "DPS")

    # ── Balance sheet line items ───────────────────────────────────────────────
    equity_capital = _f(bs, "Equity Capital")
    reserves       = _f(bs, "Reserves")
    total_debt     = _f(bs, "Total Debt", "Borrowings", "Total Borrowings")
    total_assets   = _f(bs, "Total Assets", "Balance Sheet Size")
    book_value     = _f(bs, "Book Value", "Book Value Per Share")
    cash           = _f(bs, "Cash Equivalents", "Cash & Equivalents",
                         "Cash and Cash Equivalents", "Cash and Bank Balances", "Cash")
    inventories    = _f(bs, "Inventories", "Inventory")
    receivables    = _f(bs, "Trade Receivables", "Debtors", "Receivables")
    payables       = _f(bs, "Trade Payables", "Creditors", "Payables")

    # screener.in has no combined 'Total Equity' field — derive from components
    total_equity = _f(bs, "Total Equity", "Shareholders Equity")
    if total_equity is None and equity_capital is not None and reserves is not None:
        total_equity = equity_capital + reserves
    elif total_equity is None and equity_capital is not None:
        total_equity = equity_capital

    # Book value per share (screener sometimes provides it directly)
    book_value = _f(bs, "Book Value", "Book Value Per Share")

    # ── Cash flow line items ──────────────────────────────────────────────────
    cfo   = _f(cf, "Cash from Operations", "Operating Cash Flow", "Cash from Operating Activity")
    capex = _f(cf, "Capex", "Capital Expenditure", "Fixed Assets Purchased")
    if capex is not None:
        capex = abs(capex)  # screener shows capex as negative

    # ── Derived metrics ───────────────────────────────────────────────────────
    # FCF: prefer cfo − capex; fall back to screener's own FCF field
    fcf = (cfo - capex) if cfo is not None and capex is not None else _f(cf, "Free Cash Flow")

    # Shares outstanding from equity capital (crores, par ₹10)
    shares = (equity_capital * 1e7 / 10) if equity_capital else None

    # Derive book value per share from total equity when not directly available
    if book_value is None and total_equity is not None and shares:
        book_value = round(total_equity * 1e7 / shares, 2)

    # Revenue per share
    revenue_ps = _safe_div(revenue, shares / 1e7 if shares else None) if shares else None

    # EBIT and capital employed
    ebit = (ebitda - depreciation) if ebitda and depreciation else ebitda
    cap_employed = (total_equity + total_debt) if total_equity and total_debt else total_equity

    # Net debt
    net_debt: Optional[float] = None
    if total_debt is not None and cash is not None:
        net_debt = round(total_debt - cash, 4)
    elif total_debt is not None:
        net_debt = total_debt

    # Market cap in crores (needs close + shares)
    market_cap_cr: Optional[float] = None
    if close and shares:
        market_cap_cr = round(close * shares / 1e7, 4)

    # Enterprise value = market cap + net debt
    ev: Optional[float] = None
    if market_cap_cr is not None and net_debt is not None:
        ev = market_cap_cr + net_debt

    # ROIC = EBIT * (1 − effective_tax_rate) / (equity + debt)
    roic: Optional[float] = None
    if ebit is not None and cap_employed and cap_employed > 0:
        # Approximate tax rate from P&L; default 0.25 if unavailable
        if tax is not None and revenue:
            # screener "Tax %" is the effective tax rate directly
            eff_tax = min(max(tax / 100.0, 0.0), 0.5)
        else:
            eff_tax = 0.25
        nopat = ebit * (1 - eff_tax)
        roic = round(nopat / cap_employed, 4)

    # Working capital ratios (all values in crores; days = Cr / (Revenue/365))
    rev_per_day = revenue / 365.0 if revenue and revenue > 0 else None
    cogs_per_day = (revenue - (ebitda or 0)) / 365.0 if revenue and revenue > 0 else None

    inv_turnover: Optional[float] = None
    receivables_days: Optional[float] = None
    payable_days: Optional[float] = None
    ccc: Optional[float] = None

    if inventories is not None and cogs_per_day and cogs_per_day > 0:
        inv_days = inventories / cogs_per_day
        if inv_days > 0:
            inv_turnover = round(365.0 / inv_days, 3)

    if receivables is not None and rev_per_day and rev_per_day > 0:
        receivables_days = round(receivables / rev_per_day, 3)

    if payables is not None and cogs_per_day and cogs_per_day > 0:
        payable_days = round(payables / cogs_per_day, 3)

    inv_days_val = (365.0 / inv_turnover) if inv_turnover else None
    if inv_days_val is not None and receivables_days is not None and payable_days is not None:
        ccc = round(inv_days_val + receivables_days - payable_days, 3)

    # ── Build row ─────────────────────────────────────────────────────────────
    row: dict = {
        "stock_id":    stock_id,
        "period_end":  period_end,
        "period_type": period_type,
        # Stash raw intermediates for YoY growth (removed before upsert by caller)
        "_revenue":    revenue,
        "_net_profit": net_profit,
    }

    row["eps"]               = eps
    row["book_value_ps"]     = book_value
    row["revenue_per_share"] = revenue_ps

    # Profitability
    row["pat_margin"]       = _safe_div(net_profit, revenue)
    row["ebitda_margin"]    = _safe_div(ebitda, revenue)
    row["operating_margin"] = _safe_div(ebitda, revenue)

    # Returns
    row["roe"]  = _safe_div(net_profit, total_equity) if total_equity else None
    row["roa"]  = _safe_div(net_profit, total_assets) if total_assets else None
    row["roce"] = _safe_div(ebit, cap_employed) if ebit else None
    row["roic"] = roic

    # Leverage
    row["debt_equity"]  = _safe_div(total_debt, total_equity)
    row["net_debt"]     = net_debt
    row["interest_cov"] = _safe_div(ebit, interest) if ebit and interest else None

    # Enterprise value multiples
    row["ev_ebitda"] = _safe_div(ev, ebitda) if ev is not None and ebitda and ebitda > 0 else None
    row["ev_sales"]  = _safe_div(ev, revenue) if ev is not None and revenue and revenue > 0 else None
    row["net_debt_ebitda"] = _safe_div(net_debt, ebitda) if net_debt is not None and ebitda and ebitda > 0 else None

    # Efficiency
    row["asset_turnover"]     = _safe_div(revenue, total_assets) if total_assets and total_assets > 0 else None
    row["inventory_turnover"] = inv_turnover
    row["receivables_days"]   = receivables_days
    row["payable_days"]       = payable_days
    row["cash_conv_cycle"]    = ccc

    # FCF metrics
    row["fcf"]          = fcf
    row["fcf_margin"]   = _safe_div(fcf, revenue) if fcf is not None and revenue else None
    row["cfo_to_pat"]   = _safe_div(cfo, net_profit) if cfo and net_profit else None

    # Capex ratios
    row["capex_to_revenue"]      = _safe_div(capex, revenue) if capex and revenue else None
    row["capex_to_depreciation"] = _safe_div(capex, depreciation) if capex and depreciation else None

    # Dividend
    row["dividend_per_share"]    = dps
    row["dividend_payout_ratio"] = div_payout

    # Price-dependent ratios (if close available)
    if close:
        row["pe_ratio"]       = _safe_div(close, eps) if eps and eps > 0 else None
        row["pb_ratio"]       = _safe_div(close, book_value) if book_value and book_value > 0 else None
        row["ps_ratio"]       = _safe_div(close, revenue_ps) if revenue_ps and revenue_ps > 0 else None
        row["dividend_yield"] = round(dps / close * 100, 4) if dps and close else None
        row["fcf_yield"]      = _safe_div(fcf, market_cap_cr) if fcf is not None and market_cap_cr and market_cap_cr > 0 else None

    # Market cap
    row["market_cap"] = market_cap_cr

    return row
