"""
Computes financial ratios from stored financial_statements data.
Uses the normalised JSONB 'data' column — no re-scraping needed.

All division operations are guarded against zero and None.
A None ratio is stored as NULL in the DB — not as 0 or an error.
"""

import logging
from datetime import date
from typing import Optional
from pipeline.audit import audit_job
from app.database import raw_connection
import json

logger = logging.getLogger(__name__)


# ─── Main entry points ────────────────────────────────────────────────────────

async def run_ratio_compute_all():
    """Recompute ratios for all stocks that have financial statements."""
    async with audit_job("ratio_compute_all") as audit:
        stocks = await _fetch_stocks_with_statements()
        total = 0
        for stock in stocks:
            try:
                latest_close = await _get_latest_close(stock["id"])
                await compute_ratios_for_stock(stock["id"], latest_close)
                total += 1
            except Exception as e:
                logger.error(f"Ratio compute failed for {stock['symbol']}: {e}")
        audit.records_out = total


async def compute_ratios_for_stock(stock_id: int, latest_close: Optional[float]):
    """Compute and upsert annual + TTM ratios for one stock."""
    pl = await _get_statement(stock_id, "PL")
    bs = await _get_statement(stock_id, "BS")
    cf = await _get_statement(stock_id, "CF")

    if not pl or not bs:
        logger.warning(f"stock_id={stock_id}: missing PL or BS — skipping ratio compute")
        return

    # Use the most recent period available in PL as the reference
    periods = pl.get("periods", [])
    if not periods:
        return

    # Compute for the latest period (index -1 in each series)
    d = pl.get("data", {})
    b = bs.get("data", {})
    c = cf.get("data", {}) if cf else {}

    # Also compute TTM if at least 2 quarters/periods are available
    if len(periods) >= 2:
        await _compute_and_store_ttm_ratios(stock_id, pl, bs, cf, latest_close)

    def latest(series_key, data_dict=d):
        vals = data_dict.get(series_key, [])
        # Treat "n/a" strings as None
        return next((v for v in reversed(vals) if v is not None and str(v).lower() != "n/a"), None)

    def yoy_growth(series_key, data_dict=d):
        """Year-over-year growth %: (latest - prev) / abs(prev) * 100"""
        # Filter out None and "n/a" strings
        vals = [v for v in data_dict.get(series_key, []) if v is not None and str(v).lower() != "n/a"]
        if len(vals) < 2:
            return None
        curr, prev = vals[-1], vals[-2]
        if prev == 0 or prev is None:
            return None
        return round((curr - prev) / abs(prev) * 100, 3)

    def safe_div(num, denom):
        if num is None or denom is None or denom == 0:
            return None
        return round(num / denom, 3)

    # ─── Raw data extraction ───────────────────────────────────────────────────
    pat      = latest("net_profit")
    revenue  = latest("sales") or latest("revenue")  # screener.in uses "sales"
    ebitda   = latest("operating_profit")
    deprec   = latest("depreciation")
    ebit     = latest("ebit") or (
        (ebitda - deprec) if ebitda is not None and deprec is not None else None
    )
    interest = latest("interest")
    equity   = latest("shareholders_equity") or latest("net_worth") or latest("total_equity") or latest("reserves")
    tot_assets  = latest("total_assets", b)
    borrowings  = latest("borrowings", b)
    curr_assets = latest("current_assets", b)
    curr_liab   = latest("current_liabilities", b)
    cfo         = latest("cash_from_operating_activity", c)
    shares      = latest("shares_outstanding")    # in Crores

    # ─── Derived per-share values ──────────────────────────────────────────────
    # screener.in stores shares in Crores; face value typically Rs 1 or Rs 2
    # EPS = PAT (Cr) / Shares (Cr) * 100 gives per-share in paise; / 100 for Rs
    # Simpler: screener often shows EPS directly — use that if available
    eps         = latest("eps_in_rs") or latest("eps") or safe_div(pat, shares)
    book_val_ps = safe_div(equity, shares)

    # ─── Compute all ratios ────────────────────────────────────────────────────
    roe_val = safe_div(pat, equity)
    roe = round(roe_val * 100, 3) if roe_val is not None else None

    # ROCE = EBIT / Capital Employed (Total Assets - Current Liabilities)
    capital_employed = (tot_assets - curr_liab) if tot_assets is not None and curr_liab is not None else tot_assets
    roce_val = safe_div(ebit, capital_employed)
    roce = round(roce_val * 100, 3) if roce_val is not None else None


    roa_val = safe_div(pat, tot_assets)
    roa = round(roa_val * 100, 3) if roa_val is not None else None

    pat_margin_val = safe_div(pat, revenue)
    pat_margin = round(pat_margin_val * 100, 3) if pat_margin_val is not None else None

    ebitda_margin_val = safe_div(ebitda, revenue)
    ebitda_margin = round(ebitda_margin_val * 100, 3) if ebitda_margin_val is not None else None

    ratios = {
        # Valuation (need market price)
        "pe_ratio":       safe_div(latest_close, eps) if eps and eps > 0 else None,
        "pb_ratio":       safe_div(latest_close, book_val_ps) if book_val_ps and book_val_ps > 0 else None,
        "ps_ratio":       safe_div(latest_close * (shares or 0), revenue) if revenue else None,

        # Profitability
        "roe":            roe,
        "roce":           roce,
        "roa":            roa,
        "pat_margin":     pat_margin,
        "ebitda_margin":  ebitda_margin,

        # Leverage
        "debt_equity":    safe_div(borrowings, equity),
        "interest_cov":   safe_div(ebit, interest),
        "current_ratio":  safe_div(curr_assets, curr_liab),

        # Growth
        "revenue_growth": yoy_growth("sales") or yoy_growth("revenue"),
        "pat_growth":     yoy_growth("net_profit"),
        "eps_growth":     yoy_growth("eps_in_rs") or yoy_growth("eps") or yoy_growth("net_profit"),

        # Per-share
        "eps":            eps,
        "book_value_ps":  book_val_ps,

        # Quality
        "cfo_to_pat":     safe_div(cfo, pat),
    }

    # Use the latest period end from PL as the period_end for the ratio record
    period_end = await _get_latest_period_end(stock_id, "PL")
    if not period_end:
        return

    await _upsert_ratios(stock_id, period_end, "annual", ratios)


async def _compute_and_store_ttm_ratios(stock_id: int, pl: dict, bs: dict, cf: dict, latest_close: Optional[float]):
    """
    Compute trailing-twelve-months (TTM) ratios by summing/averaging last 4 quarters.
    For annual data, we use the last available period as reference.
    """
    d = pl.get("data", {})
    b = bs.get("data", {})
    c = cf.get("data", {}) if cf else {}

    def ttm_sum(series_key, data_dict=d, periods_needed=4):
        """Sum the last N periods for flow metrics (revenue, PAT, EBITDA, etc.)."""
        vals = [v for v in data_dict.get(series_key, [])[-periods_needed:] if v is not None and str(v).lower() != "n/a"]
        if not vals:
            return None
        return sum(vals)

    def latest(series_key, data_dict=d):
        """Get latest value for stock metrics (shares, etc.)."""
        vals = data_dict.get(series_key, [])
        return next((v for v in reversed(vals) if v is not None and str(v).lower() != "n/a"), None)

    def safe_div(num, denom):
        if num is None or denom is None or denom == 0:
            return None
        return round(num / denom, 3)

    # TTM aggregates for flow metrics
    pat_ttm      = ttm_sum("net_profit")
    revenue_ttm  = ttm_sum("sales") or ttm_sum("revenue")
    ebitda_ttm   = ttm_sum("operating_profit")
    deprec_ttm   = ttm_sum("depreciation")
    ebit_ttm     = ebitda_ttm - deprec_ttm if ebitda_ttm is not None and deprec_ttm is not None else ebitda_ttm
    interest_ttm = ttm_sum("interest")
    cfo_ttm      = ttm_sum("cash_from_operating_activity", c) if c else None

    # Stock metrics use latest values
    equity   = latest("shareholders_equity") or latest("net_worth") or latest("total_equity") or latest("reserves")
    tot_assets  = latest("total_assets", b)
    borrowings  = latest("borrowings", b)
    curr_assets = latest("current_assets", b)
    curr_liab   = latest("current_liabilities", b)
    shares      = latest("shares_outstanding")
    eps_ttm     = safe_div(pat_ttm, shares)
    book_val_ps = safe_div(equity, shares)

    # Compute TTM ratios
    roe_val = safe_div(pat_ttm, equity)
    roe_ttm = round(roe_val * 100, 3) if roe_val is not None else None

    # TTM ROCE = EBIT TTM / Capital Employed
    capital_employed_ttm = (tot_assets - curr_liab) if tot_assets is not None and curr_liab is not None else tot_assets
    roce_val = safe_div(ebit_ttm, capital_employed_ttm)
    roce_ttm = round(roce_val * 100, 3) if roce_val is not None else None


    roa_val = safe_div(pat_ttm, tot_assets)
    roa_ttm = round(roa_val * 100, 3) if roa_val is not None else None

    pat_margin_val = safe_div(pat_ttm, revenue_ttm)
    pat_margin_ttm = round(pat_margin_val * 100, 3) if pat_margin_val is not None else None

    ebitda_margin_val = safe_div(ebitda_ttm, revenue_ttm)
    ebitda_margin_ttm = round(ebitda_margin_val * 100, 3) if ebitda_margin_val is not None else None

    ratios_ttm = {
        "pe_ratio":       safe_div(latest_close, eps_ttm) if eps_ttm and eps_ttm > 0 else None,
        "pb_ratio":       safe_div(latest_close, book_val_ps) if book_val_ps and book_val_ps > 0 else None,
        "ps_ratio":       safe_div(latest_close * (shares or 0), revenue_ttm) if revenue_ttm else None,
        "roe":            roe_ttm,
        "roce":           roce_ttm,
        "roa":            roa_ttm,
        "pat_margin":     pat_margin_ttm,
        "ebitda_margin":  ebitda_margin_ttm,
        "debt_equity":    safe_div(borrowings, equity),
        "interest_cov":   safe_div(ebit_ttm, interest_ttm),
        "current_ratio":  safe_div(curr_assets, curr_liab),
        "revenue_growth": None,  # N/A for TTM
        "pat_growth":     None,  # N/A for TTM
        "eps_growth":     None,  # N/A for TTM
        "eps":            eps_ttm,
        "book_value_ps":  book_val_ps,
        "cfo_to_pat":     safe_div(cfo_ttm, pat_ttm),
    }

    # Use today's date as the TTM period_end (rolling)
    from datetime import datetime
    ttm_period_end = datetime.now().date()
    await _upsert_ratios(stock_id, ttm_period_end, "ttm", ratios_ttm)


# ─── DB helpers ───────────────────────────────────────────────────────────────

async def _get_statement(stock_id: int, stmt_type: str) -> Optional[dict]:
    """Fetch the latest statement of a given type, merged across all periods."""
    sql = """
        SELECT data, period_end
        FROM financial_statements
        WHERE stock_id = $1 AND statement_type = $2 AND period_type = 'annual'
        ORDER BY period_end DESC
        LIMIT 5
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql, stock_id, stmt_type)
        if not rows:
            return None

        # Merge periods into time-series lists (most recent first → reversed)
        periods = []
        merged  = {}
        for row in reversed(rows):  # oldest first
            raw_val = row["data"]
            if isinstance(raw_val, str):
                period_data = json.loads(raw_val)
            else:
                period_data = dict(raw_val)  # JSONB -> dict
            periods.append(str(row["period_end"]))
            for key, val in period_data.items():
                if key not in merged:
                    merged[key] = []
                merged[key].append(val)

        return {"periods": periods, "data": merged}


async def _get_latest_period_end(stock_id: int, stmt_type: str) -> Optional[date]:
    async with raw_connection() as conn:
        row = await conn.fetchrow(
            "SELECT period_end FROM financial_statements WHERE stock_id=$1 AND statement_type=$2 ORDER BY period_end DESC LIMIT 1",
            stock_id, stmt_type
        )
        return row["period_end"] if row else None


async def _get_latest_close(stock_id: int) -> Optional[float]:
    async with raw_connection() as conn:
        row = await conn.fetchrow(
            "SELECT close FROM price_data WHERE stock_id=$1 ORDER BY price_date DESC LIMIT 1",
            stock_id
        )
        return float(row["close"]) if row else None


async def _fetch_stocks_with_statements() -> list:
    sql = """
        SELECT DISTINCT s.id, s.symbol
        FROM stocks s
        JOIN financial_statements fs ON fs.stock_id = s.id
        WHERE s.is_active = TRUE AND s.is_index = FALSE
        ORDER BY s.id
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql)
        return [dict(r) for r in rows]


async def _upsert_ratios(stock_id: int, period_end: date, period_type: str, ratios: dict):
    sql = """
        INSERT INTO financial_ratios
            (stock_id, period_end, period_type,
             pe_ratio, pb_ratio, ps_ratio,
             roe, roce, roa, pat_margin, ebitda_margin,
             debt_equity, interest_cov, current_ratio,
             revenue_growth, pat_growth, eps_growth,
             eps, book_value_ps, cfo_to_pat,
             computed_at)
        VALUES
            ($1, $2, $3,
             $4, $5, $6,
             $7, $8, $9, $10, $11,
             $12, $13, $14,
             $15, $16, $17,
             $18, $19, $20,
             NOW())
        ON CONFLICT (stock_id, period_end, period_type)
        DO UPDATE SET
            pe_ratio=$4, pb_ratio=$5, ps_ratio=$6,
            roe=$7, roce=$8, roa=$9, pat_margin=$10, ebitda_margin=$11,
            debt_equity=$12, interest_cov=$13, current_ratio=$14,
            revenue_growth=$15, pat_growth=$16, eps_growth=$17,
            eps=$18, book_value_ps=$19, cfo_to_pat=$20,
            computed_at=NOW()
    """
    r = ratios
    async with raw_connection() as conn:
        await conn.execute(sql,
            stock_id, period_end, period_type,
            r.get("pe_ratio"),  r.get("pb_ratio"),  r.get("ps_ratio"),
            r.get("roe"),       r.get("roce"),       r.get("roa"),
            r.get("pat_margin"),r.get("ebitda_margin"),
            r.get("debt_equity"), r.get("interest_cov"), r.get("current_ratio"),
            r.get("revenue_growth"), r.get("pat_growth"), r.get("eps_growth"),
            r.get("eps"),       r.get("book_value_ps"), r.get("cfo_to_pat"),
        )
