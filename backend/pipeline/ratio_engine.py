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
        try:
            val = float(num) / float(denom)
            import math
            if not math.isfinite(val):
                return None
            return round(val, 3)
        except:
            return None

    # ─── Raw data extraction ───────────────────────────────────────────────────
    pat      = latest("net_profit")
    revenue  = latest("sales") or latest("revenue")  # screener.in uses "sales"
    ebitda   = latest("operating_profit")
    deprec   = latest("depreciation")
    ebit     = latest("ebit") or (
        (ebitda - deprec) if ebitda is not None and deprec is not None else None
    )
    interest = latest("interest")
    # Handle equity summation (Equity Capital + Reserves)
    equity_cap = latest("equity_capital", b) or 0.0
    reserves   = latest("reserves", b) or 0.0
    equity     = latest("shareholders_equity", b) or latest("net_worth", b) or (equity_cap + reserves)
    
    tot_assets  = latest("total_assets", b)
    curr_assets = latest("current_assets", b)
    curr_liab   = latest("current_liabilities", b)
    cfo         = latest("cash_from_operating_activity", c)
    eps         = latest("eps_in_rs") or latest("eps")
    shares      = latest("shares_outstanding") or latest("no_of_equity_shares") or safe_div(pat, eps) # in Crores
    
    # Handle label mismatch (Axis Bank uses 'borrowing')
    borrowings  = latest("borrowings", b) or latest("borrowing", b) or 0.0
    cash_equivalents = latest("cash_equivalents", b) or latest("cash_and_equivalents", b) or 0.0
    
    # Dividends
    div_payout_pct = latest("dividend_payout") # raw % like 25
    div_paid = latest("dividend_payout") # some stocks store amt
    # Most Screener data has "dividend_payout" as a % of net profit
    total_div_paid = (pat * (div_payout_pct / 100)) if pat and div_payout_pct else None

    # ─── Derived per-share values ──────────────────────────────────────────────
    eps         = latest("eps_in_rs") or latest("eps") or safe_div(pat, shares)
    book_val_ps = safe_div(equity, shares)
    dps         = safe_div(total_div_paid, shares)

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

    # Valuation (need market price)
    mkt_cap = latest_close * (shares or 0) if latest_close and shares else None
    ev = (mkt_cap + borrowings - cash_equivalents) if mkt_cap is not None and borrowings is not None else None
    
    # Cash Flow & Capex
    capex = latest("capital_expenditures", c) or latest("fixed_assets_purchased", c) or 0.0
    fcf = (cfo - abs(capex)) if cfo is not None else None

    # Efficiency
    inventory   = latest("inventory", b) or latest("inventories", b)
    receivables = latest("trade_receivables", b) or latest("receivables", b)
    payables    = latest("trade_payables", b) or latest("payables", b)
    
    # Quality Scores
    piotroski = _compute_piotroski_f_score(pl, bs, cf)
    altman_z  = _compute_altman_z_score(pat, revenue, tot_assets, equity, borrowings, curr_assets, curr_liab, mkt_cap)

    ratios = {
        # Valuation
        "pe_ratio":       safe_div(latest_close, eps) if eps and eps > 0 else None,
        "pb_ratio":       safe_div(latest_close, book_val_ps) if book_val_ps and book_val_ps > 0 else None,
        "ps_ratio":       safe_div(mkt_cap, revenue) if mkt_cap and revenue else None,
        "ev_ebitda":      safe_div(ev, ebitda),
        "ev_sales":       safe_div(ev, revenue),

        # Profitability
        "roe":            roe,
        "roce":           roce,
        "roa":            roa,
        "roic":           safe_div(ebit * 0.75, (equity + borrowings - cash_equivalents)) if ebit and equity else None, # 25% tax est
        "pat_margin":     pat_margin,
        "ebitda_margin":  ebitda_margin,
        "operating_margin": safe_div(ebit, revenue) * 100 if ebit and revenue else None,

        # Leverage
        "debt_equity":    safe_div(borrowings, equity),
        "net_debt":       (borrowings - cash_equivalents) if borrowings is not None else None,
        "net_debt_ebitda": safe_div((borrowings - cash_equivalents), ebitda) if borrowings is not None else None,
        "interest_cov":   safe_div(ebit, interest),
        "current_ratio":  safe_div(curr_assets, curr_liab),
        "quick_ratio":    safe_div((curr_assets - (inventory or 0)), curr_liab) if curr_assets and curr_liab else None,

        # Efficiency
        "asset_turnover":     safe_div(revenue, tot_assets),
        "inventory_turnover": safe_div(revenue, inventory),
        "receivables_days":   safe_div(receivables, revenue) * 365 if receivables and revenue else None,
        "payable_days":       safe_div(payables, revenue * 0.7) * 365 if payables and revenue else None, # 70% COGS est
        "cash_conv_cycle":    None, # Computed below

        # Growth
        "revenue_growth": yoy_growth("sales") or yoy_growth("revenue"),
        "pat_growth":     yoy_growth("net_profit"),
        "eps_growth":     yoy_growth("eps_in_rs") or yoy_growth("eps") or yoy_growth("net_profit"),

        # Cash Flow
        "fcf":            fcf,
        "fcf_margin":     safe_div(fcf, revenue) * 100 if fcf and revenue else None,
        "fcf_yield":      safe_div(fcf, mkt_cap) * 100 if fcf and mkt_cap else None,
        "capex_to_revenue": safe_div(abs(capex), revenue) * 100 if capex and revenue else None,
        "capex_to_depreciation": safe_div(abs(capex), deprec) if capex and deprec else None,

        # Quality
        "piotroski_f_score": piotroski,
        "altman_z_score":  altman_z,
        "roic":           safe_div(ebit * 0.75, (equity + borrowings - cash_equivalents)) if ebit and equity else None, # 25% tax est
        "cfo_to_pat":     safe_div(cfo, pat),

        # Per-share
        "eps":            eps,
        "book_value_ps":  book_val_ps,
        "market_cap":     mkt_cap,
        "dividend_yield": safe_div(dps, latest_close) * 100 if dps and latest_close else None,
        "dividend_per_share": dps,
    }

    # CCC = DIO + DSO - DPO
    if ratios["inventory_turnover"] and ratios["receivables_days"] and ratios["payable_days"]:
        dio = 365 / ratios["inventory_turnover"]
        ratios["cash_conv_cycle"] = dio + ratios["receivables_days"] - ratios["payable_days"]

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
             pe_ratio, pb_ratio, ps_ratio, ev_ebitda, ev_sales,
             roe, roce, roa, roic, pat_margin, ebitda_margin, operating_margin,
             debt_equity, net_debt, net_debt_ebitda, interest_cov, current_ratio, quick_ratio,
             asset_turnover, inventory_turnover, receivables_days, payable_days, cash_conv_cycle,
             revenue_growth, pat_growth, eps_growth,
             fcf, fcf_margin, fcf_yield, capex_to_revenue, capex_to_depreciation,
             piotroski_f_score, altman_z_score,
             eps, book_value_ps, market_cap, cfo_to_pat,
             dividend_yield, dividend_per_share,
             computed_at)
        VALUES
            ($1, $2, $3,
             $4, $5, $6, $7, $8,
             $9, $10, $11, $12, $13, $14, $15,
             $16, $17, $18, $19, $20, $21,
             $22, $23, $24, $25, $26,
             $27, $28, $29,
             $30, $31, $32, $33, $34,
             $35, $36,
             $37, $38, $39, $40, $41, $42,
             NOW())
        ON CONFLICT (stock_id, period_end, period_type)
        DO UPDATE SET
            pe_ratio=$4, pb_ratio=$5, ps_ratio=$6, ev_ebitda=$7, ev_sales=$8,
            roe=$9, roce=$10, roa=$11, roic=$12, pat_margin=$13, ebitda_margin=$14, operating_margin=$15,
            debt_equity=$16, net_debt=$17, net_debt_ebitda=$18, interest_cov=$19, current_ratio=$20, quick_ratio=$21,
            asset_turnover=$22, inventory_turnover=$23, receivables_days=$24, payable_days=$25, cash_conv_cycle=$26,
            revenue_growth=$27, pat_growth=$28, eps_growth=$29,
            fcf=$30, fcf_margin=$31, fcf_yield=$32, capex_to_revenue=$33, capex_to_depreciation=$34,
            piotroski_f_score=$35, altman_z_score=$36,
            eps=$37, book_value_ps=$38, market_cap=$39, cfo_to_pat=$40,
            dividend_yield=$41, dividend_per_share=$42,
            computed_at=NOW()
    """
    r = ratios
    async with raw_connection() as conn:
        await conn.execute(sql,
            stock_id, period_end, period_type,
            r.get("pe_ratio"),  r.get("pb_ratio"),  r.get("ps_ratio"), r.get("ev_ebitda"), r.get("ev_sales"),
            r.get("roe"),       r.get("roce"),       r.get("roa"),       r.get("roic"),      r.get("pat_margin"), r.get("ebitda_margin"), r.get("operating_margin"),
            r.get("debt_equity"), r.get("net_debt"), r.get("net_debt_ebitda"), r.get("interest_cov"), r.get("current_ratio"), r.get("quick_ratio"),
            r.get("asset_turnover"), r.get("inventory_turnover"), r.get("receivables_days"), r.get("payable_days"), r.get("cash_conv_cycle"),
            r.get("revenue_growth"), r.get("pat_growth"), r.get("eps_growth"),
            r.get("fcf"),       r.get("fcf_margin"), r.get("fcf_yield"), r.get("capex_to_revenue"), r.get("capex_to_depreciation"),
            r.get("piotroski_f_score"), r.get("altman_z_score"),
            r.get("eps"),       r.get("book_value_ps"), r.get("market_cap"), r.get("cfo_to_pat"),
            r.get("dividend_yield"), r.get("dividend_per_share")
        )

# ─── Quality Scoring Logics ──────────────────────────────────────────────────

def _compute_piotroski_f_score(pl: dict, bs: dict, cf: dict) -> Optional[int]:
    """
    Compute binary 9-point fundamental health score.
    Returns 0-9.
    """
    d = pl.get("data", {})
    b = bs.get("data", {})
    c = cf.get("data", {})
    
    def val(key, data_dict=d):
        vals = data_dict.get(key, [])
        return vals[-1] if vals else None

    def prev(key, data_dict=d):
        vals = data_dict.get(key, [])
        return vals[-2] if len(vals) >= 2 else None

    # Profitability (4 pts)
    roa = val("net_profit") / val("total_assets", b) if val("net_profit") and val("total_assets", b) else 0
    p1 = 1 if roa > 0 else 0
    p2 = 1 if (val("cash_from_operating_activity", c) or 0) > 0 else 0
    
    roa_prev = prev("net_profit") / prev("total_assets", b) if prev("net_profit") and prev("total_assets", b) else 0
    p3 = 1 if roa > roa_prev else 0
    p4 = 1 if (val("cash_from_operating_activity", c) or 0) > (val("net_profit") or 0) else 0

    # Leverage (3 pts)
    de = (val("borrowings", b) or val("borrowing", b) or 0) / (val("shareholders_equity", b) or 1)
    de_prev = (prev("borrowings", b) or prev("borrowing", b) or 0) / (prev("shareholders_equity", b) or 1)
    p5 = 1 if de < de_prev else 0
    
    cr = (val("current_assets", b) or 0) / (val("current_liabilities", b) or 1)
    cr_prev = (prev("current_assets", b) or 0) / (prev("current_liabilities", b) or 1)
    p6 = 1 if cr > cr_prev else 0
    p7 = 1 if (val("shares_outstanding") or 0) <= (prev("shares_outstanding") or 999999) else 0

    # Efficiency (2 pts)
    gm = (val("operating_profit") or 0) / (val("sales") or 1)
    gm_prev = (prev("operating_profit") or 0) / (prev("sales") or 1)
    p8 = 1 if gm > gm_prev else 0
    
    at = (val("sales") or 0) / (val("total_assets", b) or 1)
    at_prev = (prev("sales") or 0) / (prev("total_assets", b) or 1)
    p9 = 1 if at > at_prev else 0

    return p1 + p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9

def _compute_altman_z_score(pat, revenue, assets, equity, debt, curr_assets, curr_liabs, mkt_cap) -> Optional[float]:
    """Simplified Z-Score: 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5"""
    if not all([assets, revenue, equity, mkt_cap]): return None
    try:
        x1 = (curr_assets - curr_liabs) / assets
        x2 = equity / assets # using equity as proxy for retained earnings
        x3 = (pat * 1.4) / assets # proxy for EBIT
        x4 = mkt_cap / (debt or 1)
        x5 = revenue / assets
        return round(1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5, 3)
    except:
        return None
