"""
Dynamic screener endpoint. Builds a WHERE clause from filter params.
Joins stocks + financial_ratios + latest price in one query.
"""
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from app.database import get_db

router = APIRouter()


@router.get("/screener")
async def screener(
    # Valuation filters
    min_pe:          Optional[float] = None,
    max_pe:          Optional[float] = None,
    min_pb:          Optional[float] = None,
    max_pb:          Optional[float] = None,
    # Profitability filters
    min_roe:         Optional[float] = None,
    min_roce:        Optional[float] = None,
    min_pat_margin:  Optional[float] = None,
    min_ebitda_margin: Optional[float] = None,
    # Growth filters
    min_revenue_growth: Optional[float] = None,
    min_pat_growth:  Optional[float] = None,
    # Leverage filters
    max_debt_equity: Optional[float] = None,
    min_interest_cov: Optional[float] = None,
    # Quality filters
    min_cfo_to_pat:  Optional[float] = None,
    # Stock filters
    sector:          Optional[str]   = None,
    market_cap_cat:  Optional[str]   = None,
    rating_label:    Optional[str]   = None,
    # Pagination
    page:  int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    sort_by: str = Query("total_score", regex="^(total_score|roe|pe_ratio|revenue_growth|pat_margin|symbol)$"),
    order:   str = Query("desc",        regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Dynamic stock screener with 15+ filter parameters.
    Builds WHERE clause from non-None filters.
    """
    # Build filter clauses dynamically
    filters = ["s.is_active = TRUE", "s.is_index = FALSE"]
    params  = {"limit": limit, "offset": (page - 1) * limit}

    def add_filter(col, op, val, key):
        if val is not None:
            filters.append(f"{col} {op} :{key}")
            params[key] = val

    add_filter("r.pe_ratio",         ">=", min_pe,           "min_pe")
    add_filter("r.pe_ratio",         "<=", max_pe,           "max_pe")
    add_filter("r.pb_ratio",         ">=", min_pb,           "min_pb")
    add_filter("r.pb_ratio",         "<=", max_pb,           "max_pb")
    add_filter("r.roe",              ">=", min_roe,          "min_roe")
    add_filter("r.roce",             ">=", min_roce,         "min_roce")
    add_filter("r.pat_margin",       ">=", min_pat_margin,   "min_pat_margin")
    add_filter("r.ebitda_margin",    ">=", min_ebitda_margin,"min_ebitda_margin")
    add_filter("r.revenue_growth",   ">=", min_revenue_growth,"min_revenue_growth")
    add_filter("r.pat_growth",       ">=", min_pat_growth,   "min_pat_growth")
    add_filter("r.debt_equity",      "<=", max_debt_equity,  "max_debt_equity")
    add_filter("r.interest_cov",     ">=", min_interest_cov, "min_interest_cov")
    add_filter("r.cfo_to_pat",       ">=", min_cfo_to_pat,   "min_cfo_to_pat")
    add_filter("s.sector",           "=",  sector,           "sector")
    add_filter("s.market_cap_cat",   "=",  market_cap_cat,   "market_cap_cat")
    add_filter("sr.rating_label",    "=",  rating_label,     "rating_label")

    where = " AND ".join(filters)

    sort_col_map = {
        "total_score":    "sr.total_score",
        "roe":            "r.roe",
        "pe_ratio":       "r.pe_ratio",
        "revenue_growth": "r.revenue_growth",
        "pat_margin":     "r.pat_margin",
        "symbol":         "s.symbol",
    }
    sort_col = sort_col_map.get(sort_by, "sr.total_score")

    sql = f"""
        SELECT
            s.symbol, s.company_name, s.sector, s.market_cap_cat,
            p.close        AS latest_close,
            p.price_date   AS latest_date,
            r.roe,         r.roce,        r.pat_margin,
            r.pe_ratio,    r.pb_ratio,    r.debt_equity,
            r.revenue_growth, r.pat_growth, r.eps,
            r.interest_cov, r.cfo_to_pat,
            sr.rating_label, sr.total_score
        FROM stocks s
        LEFT JOIN LATERAL (
            SELECT roe, roce, pat_margin, pe_ratio, pb_ratio, debt_equity,
                   revenue_growth, pat_growth, eps, interest_cov, cfo_to_pat, ebitda_margin
            FROM financial_ratios
            WHERE stock_id = s.id AND period_type = 'annual'
            ORDER BY period_end DESC LIMIT 1
        ) r ON TRUE
        LEFT JOIN LATERAL (
            SELECT close, price_date
            FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1
        ) p ON TRUE
        LEFT JOIN LATERAL (
            SELECT rating_label, total_score
            FROM stock_ratings WHERE stock_id = s.id ORDER BY rated_on DESC LIMIT 1
        ) sr ON TRUE
        WHERE {where}
        ORDER BY {sort_col} {order} NULLS LAST
        LIMIT :limit OFFSET :offset
    """

    count_sql = f"""
        SELECT COUNT(*)
        FROM stocks s
        LEFT JOIN LATERAL (
            SELECT roe, roce, pat_margin, pe_ratio, pb_ratio, debt_equity,
                   revenue_growth, pat_growth, interest_cov, cfo_to_pat, ebitda_margin
            FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual'
            ORDER BY period_end DESC LIMIT 1
        ) r ON TRUE
        LEFT JOIN LATERAL (
            SELECT rating_label FROM stock_ratings WHERE stock_id = s.id ORDER BY rated_on DESC LIMIT 1
        ) sr ON TRUE
        WHERE {where}
    """

    result = await db.execute(text(sql), params)
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    count  = await db.execute(text(count_sql), count_params)

    return {
        "results": [dict(r._mapping) for r in result.fetchall()],
        "total":   count.scalar(),
        "page":    page,
        "limit":   limit,
        "filters_applied": {k: v for k, v in params.items() if k not in ("limit", "offset") and v is not None},
    }


@router.get("/stocks/{symbol}/ratios")
async def get_ratios(
    symbol:      str,
    period_type: str = Query("annual", regex="^(annual|ttm)$"),
    limit:       int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Get financial ratios history for a stock."""
    from app.routers.stocks import _get_stock_id

    stock = await _get_stock_id(symbol, db)
    if not stock:
        raise HTTPException(404, f"Stock '{symbol}' not found")

    sql = """
        SELECT period_end, period_type, pe_ratio, pb_ratio, ps_ratio, roe, roce, roa,
               pat_margin, ebitda_margin, debt_equity, interest_cov, current_ratio,
               revenue_growth, pat_growth, eps_growth, eps, book_value_ps, cfo_to_pat, computed_at
        FROM financial_ratios
        WHERE stock_id = :sid AND period_type = :pt
        ORDER BY period_end DESC
        LIMIT :limit
    """
    result = await db.execute(text(sql), {"sid": stock["id"], "pt": period_type, "limit": limit})
    return {"symbol": symbol.upper(), "records": [dict(r._mapping) for r in result.fetchall()]}


@router.get("/compare")
async def compare_stocks(
    symbols: str = Query(..., description="Comma-separated symbols, max 5"),
    db: AsyncSession = Depends(get_db),
):
    """Compare up to 5 stocks side-by-side."""
    from app.routers.stocks import _get_stock_id

    symbol_list = [s.strip().upper() for s in symbols.split(",")][:5]
    if not symbol_list:
        raise HTTPException(400, "Provide at least one symbol")

    result = []
    for sym in symbol_list:
        stock = await _get_stock_id(sym, db)
        if not stock:
            continue
        sql = """
            SELECT s.symbol, s.company_name, s.sector,
                   p.close AS latest_close, p.price_date,
                   r.pe_ratio, r.pb_ratio, r.roe, r.roce,
                   r.pat_margin, r.debt_equity, r.revenue_growth,
                   r.eps, r.interest_cov,
                   sr.rating_label, sr.total_score,
                   sr.fundamental_score, sr.technical_score
            FROM stocks s
            LEFT JOIN LATERAL (
                SELECT close, price_date FROM price_data WHERE stock_id=s.id ORDER BY price_date DESC LIMIT 1
            ) p ON TRUE
            LEFT JOIN LATERAL (
                SELECT pe_ratio, pb_ratio, roe, roce, pat_margin, debt_equity,
                       revenue_growth, eps, interest_cov
                FROM financial_ratios WHERE stock_id=s.id ORDER BY period_end DESC LIMIT 1
            ) r ON TRUE
            LEFT JOIN LATERAL (
                SELECT rating_label, total_score, fundamental_score, technical_score
                FROM stock_ratings WHERE stock_id=s.id ORDER BY rated_on DESC LIMIT 1
            ) sr ON TRUE
            WHERE s.symbol = :symbol AND s.is_active = TRUE
        """
        row = await db.execute(text(sql), {"symbol": sym})
        r = row.fetchone()
        if r:
            result.append(dict(r._mapping))

    return {"symbols": symbol_list, "comparison": result}
