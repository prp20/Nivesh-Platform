# backend/app/routers/stocks.py
"""
Stock endpoints with validated filtering and safe query construction.
"""
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from datetime import date
from app.database import get_db
from app.models import Stock, PriceData
from schemas.stocks import StockListResponse
from app.query_utils import FilterBuilder, SortColumnMap
from app import security

router = APIRouter(prefix="/stocks", tags=["Stocks"])

# Define allowed sort columns
SORT_COLUMNS = SortColumnMap(
    {
        "symbol": "s.symbol",
        "company_name": "s.company_name",
        "sector": "s.sector",
    }
)


# ─── GET /stocks — paginated listing ─────────────────────────────────────────

@router.get("", response_model=StockListResponse)
async def list_stocks(
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    market_cap_cat: Optional[str] = None,
    is_index: bool = False,
    page: int = Query(1, ge=1, le=10000),
    limit: int = Query(25, ge=1, le=100),
    sort_by: str = Query("symbol", min_length=1, max_length=50),
    order: str = Query("asc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
) -> StockListResponse:
    """
    List stocks with optional filtering and pagination.

    Args:
        sector: Filter by sector name
        industry: Filter by industry name
        market_cap_cat: Filter by market cap category (Large/Mid/Small)
        is_index: Filter by index flag (True for indices only, False for stocks)
        page: Page number (1-indexed)
        limit: Results per page (1-100)
        sort_by: Sort column (symbol, company_name, sector)
        order: Sort order (asc/desc)

    Returns:
        StockListResponse with paginated results
    """
    # Build WHERE clause using safe FilterBuilder
    builder = FilterBuilder(base_filters=["s.is_active = TRUE"])
    builder.add("s.is_index", "=", is_index, "is_index")
    builder.add("s.sector", "=", sector, "sector")
    builder.add("s.industry", "=", industry, "industry")

    # Handle unified Market Cap labels
    mcap_mapping = {
        "Large Cap": ["Large Cap", "largecap", "NIFTY 100", "LARGE CAP", "LargeCap"],
        "Mid Cap": ["Mid Cap", "midcap", "NIFTY MIDCAP 150", "MID CAP", "MidCap"],
        "Small Cap": ["Small Cap", "smallcap", "NIFTY SMALLCAP 250", "SMALL CAP", "SmallCap"],
    }

    if market_cap_cat in mcap_mapping:
        builder.add_in("s.market_cap_cat", mcap_mapping[market_cap_cat], "market_cap_cat")
    else:
        builder.add("s.market_cap_cat", "=", market_cap_cat, "market_cap_cat")

    where_clause = builder.build_where()
    params = builder.get_params()

    # Add pagination params
    params["limit"] = limit
    params["offset"] = (page - 1) * limit

    # Get safe sort column and direction
    sort_col = SORT_COLUMNS.get_column(sort_by, "s.symbol")
    order_dir = "DESC" if order == "desc" else "ASC"

    sql = f"""
        SELECT
            s.id, s.symbol, s.company_name, s.sector, s.industry, s.summary, s.market_cap_cat,
            p.close      AS latest_close,
            p.price_date AS latest_date,
            r.rating_label,
            r.total_score
        FROM stocks s
        LEFT JOIN LATERAL (
            SELECT close, price_date
            FROM price_data
            WHERE stock_id = s.id
            ORDER BY price_date DESC
            LIMIT 1
        ) p ON TRUE
        LEFT JOIN LATERAL (
            SELECT rating_label, total_score
            FROM stock_ratings
            WHERE stock_id = s.id
            ORDER BY rated_on DESC
            LIMIT 1
        ) r ON TRUE
        WHERE {where_clause}
        ORDER BY {sort_col} {order_dir}
        LIMIT :limit OFFSET :offset
    """

    count_sql = f"""
        SELECT COUNT(*) FROM stocks s
        WHERE {where_clause}
    """

    result = await db.execute(text(sql), params)
    count = await db.execute(
        text(count_sql),
        {k: v for k, v in params.items() if k not in ("limit", "offset")},
    )

    return StockListResponse(
        results=[dict(r._mapping) for r in result.fetchall()],
        total=count.scalar(),
        page=page,
        limit=limit,
    )


# ─── GET /stocks/search ───────────────────────────────────────────────────────

@router.get("/search")
async def search_stocks(
    q:     str = Query(..., min_length=1, max_length=50),
    limit: int = Query(10, ge=1, le=20),
    db:    AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    sql = """
        SELECT id, symbol, company_name, sector, market_cap_cat
        FROM stocks
        WHERE is_active = TRUE
          AND (
            symbol ILIKE :q
            OR to_tsvector('english', company_name) @@ plainto_tsquery('english', :q_plain)
          )
        ORDER BY
            CASE WHEN symbol ILIKE :q_exact THEN 0 ELSE 1 END,
            company_name
        LIMIT :limit
    """
    result = await db.execute(text(sql), {
        "q":       f"%{q}%",
        "q_plain": q,
        "q_exact": q.upper(),
        "limit":   limit,
    })
    return {"results": [dict(r._mapping) for r in result.fetchall()]}


# ─── GET /stocks/{symbol} — full snapshot ────────────────────────────────────

@router.get("/{symbol}")
async def get_stock(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    sql = """
        SELECT
            s.*,
            p.close      AS latest_close,
            p.high       AS latest_high,
            p.low        AS latest_low,
            p.volume     AS latest_volume,
            p.price_date AS latest_date,
            -- 1-day change %
            ROUND(
                (p.close - p2.close) / NULLIF(p2.close, 0) * 100, 2
            ) AS change_pct,
            -- Valuation
            r.pe_ratio, r.pb_ratio, r.ps_ratio, r.ev_ebitda, r.ev_sales, r.market_cap, r.dividend_yield, r.dividend_per_share,
            -- Profitability
            r.roe, r.roce, r.roa, r.roic, r.pat_margin, r.ebitda_margin, r.operating_margin,
            -- Solvency & Leverage
            r.debt_equity, r.net_debt, r.net_debt_ebitda, r.interest_cov, r.current_ratio, r.quick_ratio,
            -- Growth
            r.revenue_growth, r.pat_growth, r.eps_growth,
            -- Efficiency
            r.asset_turnover, r.inventory_turnover, r.receivables_days, r.payable_days, r.cash_conv_cycle,
            -- Cash Flow
            r.fcf, r.fcf_margin, r.fcf_yield, r.capex_to_revenue, r.cfo_to_pat,
            -- Quality
            r.piotroski_f_score, r.altman_z_score,
            -- Per Share
            r.eps, r.book_value_ps,
            -- Technical Indicators
            ti.rsi_14, ti.macd_hist, ti.macd_line, ti.macd_signal,
            ti.sma_20, ti.sma_50, ti.sma_200, ti.ema_9, ti.ema_21,
            ti.obv, ti.vwap_20, ti.cci_20, ti.beta_1y, ti.rs_6m_vs_nifty,
            ti.pct_from_52w_high, ti.pct_from_52w_low,
            ti.adx_14, ti.stoch_k
        FROM stocks s
        LEFT JOIN LATERAL (
            SELECT close, high, low, volume, price_date
            FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1
        ) p ON TRUE
        LEFT JOIN LATERAL (
            SELECT close FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1 OFFSET 1
        ) p2 ON TRUE
        LEFT JOIN LATERAL (
            SELECT *
            FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1
        ) r ON TRUE
        LEFT JOIN LATERAL (
            SELECT rating_label, total_score, fundamental_score, technical_score
            FROM stock_ratings WHERE stock_id = s.id ORDER BY rated_on DESC LIMIT 1
        ) r_rt ON TRUE
        LEFT JOIN LATERAL (
            SELECT *
            FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1D' ORDER BY ind_date DESC LIMIT 1
        ) ti ON TRUE
        WHERE s.symbol = :symbol AND s.is_active = TRUE
    """
    result = await db.execute(text(sql), {"symbol": symbol.upper()})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")
    return dict(row._mapping)


# ─── GET /stocks/{symbol}/price — OHLCV history ──────────────────────────────

@router.get("/{symbol}/price")
async def get_price_history(
    symbol:    str,
    from_date: Optional[date] = None,
    to_date:   Optional[date] = None,
    interval:  str = Query("1d", regex="^(1d|1w|1mo)$"),
    limit:     int = Query(365, ge=1, le=2000),
    db:        AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    stock = await _get_stock_id(symbol, db)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")

    # Build dynamic WHERE clause based on filters
    where_clause = "WHERE stock_id = :sid"
    params = {"sid": stock["id"], "limit": limit}

    if from_date:
        where_clause += " AND price_date >= :from_date"
        params["from_date"] = from_date
    if to_date:
        where_clause += " AND price_date <= :to_date"
        params["to_date"] = to_date

    if interval == "1d":
        sql = f"""
            SELECT price_date AS "time", open, high, low, adj_close AS close, volume
            FROM price_data
            {where_clause}
            ORDER BY price_date DESC
            LIMIT :limit
        """
    elif interval == "1w":
        sql = f"""
            SELECT
                date_trunc('week', price_date)::date AS "time",
                (ARRAY_AGG(open ORDER BY price_date))[1]  AS open,
                MAX(high)                                  AS high,
                MIN(low)                                   AS low,
                (ARRAY_AGG(adj_close ORDER BY price_date DESC))[1] AS close,
                SUM(volume)                                AS volume
            FROM price_data
            {where_clause}
            GROUP BY date_trunc('week', price_date)
            ORDER BY "time" DESC
            LIMIT :limit
        """
    else:  # 1mo
        sql = f"""
        SELECT
            date_trunc('month', price_date)::date AS "time",
            (ARRAY_AGG(open ORDER BY price_date))[1]       AS open,
            MAX(high)                                       AS high,
            MIN(low)                                        AS low,
            (ARRAY_AGG(adj_close ORDER BY price_date DESC))[1] AS close,
            SUM(volume)                                     AS volume
        FROM price_data
        {where_clause}
        GROUP BY date_trunc('month', price_date)
        ORDER BY "time" DESC
        LIMIT :limit
        """

    result = await db.execute(text(sql), params)

    rows = [dict(r._mapping) for r in result.fetchall()]
    rows.reverse()  # return chronological order
    return {"symbol": symbol.upper(), "interval": interval, "data": rows}


# ─── Shared helper ────────────────────────────────────────────────────────────

async def _get_stock_id(symbol: str, db: AsyncSession):
    result = await db.execute(
        text("SELECT id, symbol FROM stocks WHERE symbol = :s AND is_active = TRUE"),
        {"s": symbol.upper()}
    )
    row = result.fetchone()
    return dict(row._mapping) if row else None


# ─── GET /stocks/{symbol}/fundamentals ────────────────────────────────────────

@router.get("/{symbol}/fundamentals")
async def get_fundamentals(
    symbol:         str,
    statement_type: str = Query("PL", regex="^(PL|BS|CF)$"),
    period_type:    str = Query("annual", regex="^(annual|quarterly)$"),
    limit:          int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    stock = await _get_stock_id(symbol, db)
    if not stock:
        raise HTTPException(404, f"Stock '{symbol}' not found")

    sql = """
        SELECT period_end, period_type, data, scraped_at
        FROM financial_statements
        WHERE stock_id      = :sid
          AND statement_type = :st
          AND period_type    = :pt
        ORDER BY period_end DESC
        LIMIT :limit
    """
    result = await db.execute(text(sql), {
        "sid": stock["id"], "st": statement_type, "pt": period_type, "limit": limit
    })
    rows = [dict(r._mapping) for r in result.fetchall()]
    return {"symbol": symbol.upper(), "statement_type": statement_type, "records": rows}


# ─── GET /stocks/{symbol}/shareholding ────────────────────────────────────────

@router.get("/{symbol}/shareholding")
async def get_shareholding(
    symbol: str,
    limit:  int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    stock = await _get_stock_id(symbol, db)
    if not stock:
        raise HTTPException(404, f"Stock '{symbol}' not found")

    sql = """
        SELECT period_end, promoter_pct, fii_pct, dii_pct, public_pct, pledged_pct,
               promoter_change, fii_change
        FROM shareholding_pattern
        WHERE stock_id = :sid
        ORDER BY period_end DESC
        LIMIT :limit
    """
    result = await db.execute(text(sql), {"sid": stock["id"], "limit": limit})
    return {"symbol": symbol.upper(), "records": [dict(r._mapping) for r in result.fetchall()]}


