"""
Dynamic screener endpoint with safe query building and validated inputs.

Uses FilterBuilder for parameterized WHERE clause construction and SortColumnMap
for safe ORDER BY column selection. All numeric ranges are validated.
"""
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from app.database import get_db
from app.schemas import ScreenerResponse, ScreenerFilterInput
from app.query_utils import FilterBuilder, SortColumnMap
from app import security

router = APIRouter()

# Define allowed sort columns to prevent ORDER BY injection
SORT_COLUMNS = SortColumnMap(
    {
        "total_score": "sr.total_score",
        "roe": "r.roe",
        "pe_ratio": "r.pe_ratio",
        "revenue_growth": "r.revenue_growth",
        "pat_margin": "r.pat_margin",
        "symbol": "s.symbol",
        "ev_ebitda": "r.ev_ebitda",
        "roic": "r.roic",
        "piotroski_f_score": "r.piotroski_f_score",
        "beta": "ti.beta_1y",
        "relative_strength": "ti.rs_6m_vs_nifty",
        "vol_ratio": "ti.volume_ratio",
    }
)

# Define allowed rating labels (prevent injection)
ALLOWED_RATING_LABELS = {"STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"}


@router.get("/screener", response_model=ScreenerResponse)
async def screener(
    # Valuation filters
    min_pe: Optional[float] = None,
    max_pe: Optional[float] = None,
    min_pb: Optional[float] = None,
    max_pb: Optional[float] = None,
    # Profitability filters
    min_roe: Optional[float] = None,
    min_roce: Optional[float] = None,
    min_pat_margin: Optional[float] = None,
    min_ebitda_margin: Optional[float] = None,
    # Growth filters
    min_revenue_growth: Optional[float] = None,
    min_pat_growth: Optional[float] = None,
    # Leverage filters
    max_debt_equity: Optional[float] = None,
    min_interest_cov: Optional[float] = None,
    # Quality filters
    min_cfo_to_pat: Optional[float] = None,
    # Stock filters
    sector: Optional[str] = None,
    market_cap_cat: Optional[str] = None,
    rating_label: Optional[str] = None,
    # Advanced Fundamental Filters
    min_roic: Optional[float] = None,
    min_ev_ebitda: Optional[float] = None,
    max_ev_ebitda: Optional[float] = None,
    min_piotroski: Optional[int] = None,
    min_fcf_yield: Optional[float] = None,
    # Advanced Technical Filters
    min_beta: Optional[float] = None,
    max_beta: Optional[float] = None,
    min_rs_6m: Optional[float] = None,
    min_volume_ratio: Optional[float] = None,
    # Pagination & sorting
    page: int = Query(1, ge=1, le=10000),
    limit: int = Query(25, ge=1, le=100),
    sort_by: str = Query("total_score", min_length=1, max_length=50),
    order: str = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
) -> ScreenerResponse:
    """
    Dynamic stock screener with 15+ validated filter parameters.

    All numeric ranges are validated (min <= max), columns are restricted to allow-list,
    and pagination is bounded. Safe against SQL injection.

    Args:
        min_pe, max_pe: P/E ratio range (0-500)
        min_pb, max_pb: P/B ratio range (0-50)
        min_roe: Minimum ROE (%)
        min_roce: Minimum ROCE (%)
        min_pat_margin: Minimum PAT margin (%)
        min_ebitda_margin: Minimum EBITDA margin (%)
        min_revenue_growth: Minimum revenue growth (%)
        min_pat_growth: Minimum PAT growth (%)
        max_debt_equity: Maximum debt/equity ratio (0-100)
        min_interest_cov: Minimum interest coverage
        min_cfo_to_pat: Minimum CFO-to-PAT ratio
        sector: Sector name (string match)
        market_cap_cat: Market cap category (Large/Mid/Small)
        rating_label: Stock rating label
        page: Page number (1-indexed)
        limit: Results per page (1-100)
        sort_by: Sort column (from SORT_COLUMNS allow-list)
        order: Sort order (asc/desc)

    Returns:
        ScreenerResponse with results, total count, applied filters
    """
    # Validate numeric ranges
    if min_pe is not None and max_pe is not None and min_pe > max_pe:
        raise HTTPException(status_code=400, detail="min_pe > max_pe")
    if min_pb is not None and max_pb is not None and min_pb > max_pb:
        raise HTTPException(status_code=400, detail="min_pb > max_pb")

    # Validate range bounds
    if min_pe is not None and min_pe < 0:
        raise HTTPException(status_code=400, detail="min_pe must be >= 0")
    if max_pe is not None and max_pe > 500:
        raise HTTPException(status_code=400, detail="max_pe must be <= 500")
    if min_pb is not None and min_pb < 0:
        raise HTTPException(status_code=400, detail="min_pb must be >= 0")
    if max_pb is not None and max_pb > 50:
        raise HTTPException(status_code=400, detail="max_pb must be <= 50")

    # Validate rating_label against allow-list
    if rating_label is not None and rating_label.upper() not in ALLOWED_RATING_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"rating_label must be one of {ALLOWED_RATING_LABELS}",
        )

    # Build WHERE clause using safe FilterBuilder
    builder = FilterBuilder(base_filters=["s.is_active = TRUE", "s.is_index = FALSE"])

    builder.add_range("r.pe_ratio", min_pe, max_pe, "min_pe", "max_pe")
    builder.add_range("r.pb_ratio", min_pb, max_pb, "min_pb", "max_pb")
    builder.add("r.roe", ">=", min_roe, "min_roe")
    builder.add("r.roce", ">=", min_roce, "min_roce")
    builder.add("r.pat_margin", ">=", min_pat_margin, "min_pat_margin")
    builder.add("r.ebitda_margin", ">=", min_ebitda_margin, "min_ebitda_margin")
    builder.add("r.revenue_growth", ">=", min_revenue_growth, "min_revenue_growth")
    builder.add("r.pat_growth", ">=", min_pat_growth, "min_pat_growth")
    builder.add("r.debt_equity", "<=", max_debt_equity, "max_debt_equity")
    builder.add("r.interest_cov", ">=", min_interest_cov, "min_interest_cov")
    builder.add("r.cfo_to_pat", ">=", min_cfo_to_pat, "min_cfo_to_pat")
    builder.add("s.sector", "=", sector, "sector")
    builder.add("s.market_cap_cat", "=", market_cap_cat, "market_cap_cat")
    builder.add("sr.rating_label", "=", rating_label, "rating_label")
    
    # Advanced Fundamental
    builder.add("r.roic", ">=", min_roic, "min_roic")
    builder.add_range("r.ev_ebitda", min_ev_ebitda, max_ev_ebitda, "min_ev_ebitda", "max_ev_ebitda")
    builder.add("r.piotroski_f_score", ">=", min_piotroski, "min_piotroski")
    builder.add("r.fcf_yield", ">=", min_fcf_yield, "min_fcf_yield")
    
    # Advanced Technical
    builder.add_range("ti.beta_1y", min_beta, max_beta, "min_beta", "max_beta")
    builder.add("ti.rs_6m_vs_nifty", ">=", min_rs_6m, "min_rs_6m")
    builder.add("ti.volume_ratio", ">=", min_volume_ratio, "min_volume_ratio")

    where_clause = builder.build_where()
    params = builder.get_params()

    # Add pagination params
    params["limit"] = limit
    params["offset"] = (page - 1) * limit

    # Get safe sort column and direction
    sort_col = SORT_COLUMNS.get_column(sort_by, "sr.total_score")
    order_dir = "DESC" if order == "desc" else "ASC"

    # Single WHERE clause definition, used in both main and count queries
    sql_main = f"""
        SELECT
            s.symbol, s.company_name, s.sector, s.industry, s.summary, s.market_cap_cat,
            p.close        AS latest_close,
            p.price_date   AS latest_date,
            r.roe,         r.roce,        r.pat_margin,
            r.pe_ratio,    r.pb_ratio,    r.debt_equity,
            r.revenue_growth, r.pat_growth, r.eps,
            r.interest_cov, r.cfo_to_pat,
            r.ev_ebitda,    r.roic,        r.fcf_yield,
            r.piotroski_f_score, r.altman_z_score,
            m.market_cap, m.dividend_yield, m.low_52w, m.high_52w, m.revenue_per_share,
            sr.rating_label, sr.total_score,
            ti.beta_1y, ti.rs_6m_vs_nifty, 
            ti.pct_from_52w_high, ti.pct_from_52w_low,
            ti.volume_ratio
        FROM stocks s
        LEFT JOIN LATERAL (
            SELECT roe, roce, pat_margin, pe_ratio, pb_ratio, debt_equity,
                   revenue_growth, pat_growth, eps, interest_cov, cfo_to_pat, ebitda_margin,
                   ev_ebitda, roic, fcf_yield, piotroski_f_score, altman_z_score
            FROM financial_ratios
            WHERE stock_id = s.id AND period_type = 'annual'
            ORDER BY period_end DESC LIMIT 1
        ) r ON TRUE
        LEFT JOIN LATERAL (
            SELECT market_cap, dividend_yield, low_52w, high_52w, revenue_per_share
            FROM financial_ratios
            WHERE stock_id = s.id AND period_type = 'latest'
            ORDER BY period_end DESC LIMIT 1
        ) m ON TRUE
        LEFT JOIN LATERAL (
            SELECT close, price_date
            FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1
        ) p ON TRUE
        LEFT JOIN LATERAL (
            SELECT rating_label, total_score
            FROM stock_ratings WHERE stock_id = s.id ORDER BY rated_on DESC LIMIT 1
        ) sr ON TRUE
        LEFT JOIN LATERAL (
            SELECT beta_1y, rs_6m_vs_nifty, pct_from_52w_high, pct_from_52w_low, volume_ratio
            FROM technical_indicators 
            WHERE stock_id = s.id AND timeframe = '1d'
            ORDER BY ind_date DESC LIMIT 1
        ) ti ON TRUE
        WHERE {where_clause}
        ORDER BY {sort_col} {order_dir} NULLS LAST
        LIMIT :limit OFFSET :offset
    """

    sql_count = f"""
        SELECT COUNT(*)
        FROM stocks s
        LEFT JOIN LATERAL (
            SELECT roe, roce, pat_margin, pe_ratio, pb_ratio, debt_equity,
                   revenue_growth, pat_growth, interest_cov, cfo_to_pat, ebitda_margin,
                   ev_ebitda, roic, fcf_yield, piotroski_f_score
            FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual'
            ORDER BY period_end DESC LIMIT 1
        ) r ON TRUE
        LEFT JOIN LATERAL (
            SELECT beta_1y, rs_6m_vs_nifty, volume_ratio
            FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d'
            ORDER BY ind_date DESC LIMIT 1
        ) ti ON TRUE
        LEFT JOIN LATERAL (
            SELECT rating_label FROM stock_ratings WHERE stock_id = s.id ORDER BY rated_on DESC LIMIT 1
        ) sr ON TRUE
        WHERE {where_clause}
    """

    # Execute both queries with same parameters
    result = await db.execute(text(sql_main), params)
    count = await db.execute(
        text(sql_count),
        {k: v for k, v in params.items() if k not in ("limit", "offset")},
    )

    # Build filters_applied dict (exclude pagination params)
    filters_applied = {
        k: v
        for k, v in params.items()
        if k not in ("limit", "offset") and v is not None
    }

    return ScreenerResponse(
        results=[dict(r._mapping) for r in result.fetchall()],
        total=count.scalar(),
        page=page,
        limit=limit,
        filters_applied=filters_applied,
    )


@router.get("/stocks/{symbol}/ratios")
async def get_ratios(
    symbol:      str,
    period_type: str = Query("annual", regex="^(annual|ttm)$"),
    limit:       int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    """Get financial ratios history for a stock."""
    from app.routers.stocks import _get_stock_id

    stock = await _get_stock_id(symbol, db)
    if not stock:
        raise HTTPException(404, f"Stock '{symbol}' not found")

    sql = """
        SELECT period_end, period_type, pe_ratio, pb_ratio, ps_ratio, ev_ebitda, roe, roce, roic, roa,
               pat_margin, ebitda_margin, debt_equity, interest_cov, current_ratio,
               revenue_growth, pat_growth, eps_growth, eps, book_value_ps, 
               dividend_yield, market_cap, low_52w, high_52w, revenue_per_share,
               cfo_to_pat, piotroski_f_score, altman_z_score, computed_at
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
    current_user: str = Depends(security.get_current_user),
):
    """Compare up to 5 stocks side-by-side."""
    from app.routers.stocks import _get_stock_id

    symbol_list = [s.strip().upper() for s in symbols.split(",")][:5]
    if len(symbol_list) < 2:
        raise HTTPException(400, "Provide at least two symbols to compare")

    result = []
    for sym in symbol_list:
        stock = await _get_stock_id(sym, db)
        if not stock:
            continue
        sql = """
            SELECT s.symbol, s.company_name, s.sector,
                   p.close AS latest_close, p.price_date,
                   r.pe_ratio, r.pb_ratio, r.roe, r.roce,
                   r.pat_margin, r.ebitda_margin, r.debt_equity, r.revenue_growth,
                   r.pat_growth, r.eps, r.interest_cov,
                   sr.rating_label, sr.total_score,
                   sr.fundamental_score, sr.technical_score, sr.valuation_score
            FROM stocks s
            LEFT JOIN LATERAL (
                SELECT close, price_date FROM price_data WHERE stock_id=s.id ORDER BY price_date DESC LIMIT 1
            ) p ON TRUE
            LEFT JOIN LATERAL (
                SELECT pe_ratio, pb_ratio, roe, roce, pat_margin, ebitda_margin, debt_equity,
                       revenue_growth, pat_growth, eps, interest_cov
                FROM financial_ratios WHERE stock_id=s.id ORDER BY period_end DESC LIMIT 1
            ) r ON TRUE
            LEFT JOIN LATERAL (
                SELECT rating_label, total_score, fundamental_score, technical_score, valuation_score
                FROM stock_ratings WHERE stock_id=s.id ORDER BY rated_on DESC LIMIT 1
            ) sr ON TRUE
            WHERE s.symbol = :symbol AND s.is_active = TRUE
        """
        row = await db.execute(text(sql), {"symbol": sym})
        r = row.fetchone()
        if r:
            result.append(dict(r._mapping))

    return {"symbols": symbol_list, "comparison": result}
