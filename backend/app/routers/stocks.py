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
from app.schemas import StockListResponse
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
            (SELECT close      FROM price_data    WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1) AS latest_close,
            (SELECT price_date FROM price_data    WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1) AS latest_date,
            (SELECT rating_label FROM stock_ratings WHERE stock_id = s.id ORDER BY rated_on DESC LIMIT 1) AS rating_label,
            (SELECT total_score  FROM stock_ratings WHERE stock_id = s.id ORDER BY rated_on DESC LIMIT 1) AS total_score
        FROM stocks s
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
            UPPER(symbol) LIKE UPPER(:q)
            OR UPPER(company_name) LIKE UPPER(:q)
          )
        ORDER BY
            CASE WHEN UPPER(symbol) = UPPER(:q_exact) THEN 0 ELSE 1 END,
            company_name
        LIMIT :limit
    """
    result = await db.execute(text(sql), {
        "q":       f"%{q}%",
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
            (SELECT close      FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1)          AS latest_close,
            (SELECT high       FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1)          AS latest_high,
            (SELECT low        FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1)          AS latest_low,
            (SELECT volume     FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1)          AS latest_volume,
            (SELECT price_date FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1)          AS latest_date,
            (SELECT close      FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1 OFFSET 1) AS prev_close,
            -- Valuation
            (SELECT pe_ratio        FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS pe_ratio,
            (SELECT pb_ratio        FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS pb_ratio,
            (SELECT ps_ratio        FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS ps_ratio,
            (SELECT ev_ebitda       FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS ev_ebitda,
            (SELECT ev_sales        FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS ev_sales,
            (SELECT market_cap      FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS market_cap,
            (SELECT dividend_yield  FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS dividend_yield,
            (SELECT dividend_per_share FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS dividend_per_share,
            -- Profitability
            (SELECT roe             FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS roe,
            (SELECT roce            FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS roce,
            (SELECT roa             FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS roa,
            (SELECT roic            FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS roic,
            (SELECT pat_margin      FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS pat_margin,
            (SELECT ebitda_margin   FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS ebitda_margin,
            (SELECT operating_margin FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS operating_margin,
            -- Solvency & Leverage
            (SELECT debt_equity     FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS debt_equity,
            (SELECT net_debt        FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS net_debt,
            (SELECT net_debt_ebitda FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS net_debt_ebitda,
            (SELECT interest_cov    FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS interest_cov,
            (SELECT current_ratio   FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS current_ratio,
            (SELECT quick_ratio     FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS quick_ratio,
            -- Growth
            (SELECT revenue_growth  FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS revenue_growth,
            (SELECT pat_growth      FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS pat_growth,
            (SELECT eps_growth      FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS eps_growth,
            -- Efficiency
            (SELECT asset_turnover     FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS asset_turnover,
            (SELECT inventory_turnover FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS inventory_turnover,
            (SELECT receivables_days   FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS receivables_days,
            (SELECT payable_days       FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS payable_days,
            (SELECT cash_conv_cycle    FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS cash_conv_cycle,
            -- Cash Flow
            (SELECT fcf            FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS fcf,
            (SELECT fcf_margin     FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS fcf_margin,
            (SELECT fcf_yield      FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS fcf_yield,
            (SELECT capex_to_revenue FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS capex_to_revenue,
            (SELECT cfo_to_pat     FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS cfo_to_pat,
            -- Quality
            (SELECT piotroski_f_score FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS piotroski_f_score,
            (SELECT altman_z_score    FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS altman_z_score,
            -- Per Share
            (SELECT eps           FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS eps,
            (SELECT book_value_ps FROM financial_ratios WHERE stock_id = s.id AND period_type = 'annual' ORDER BY period_end DESC LIMIT 1) AS book_value_ps,
            -- Technical Indicators
            (SELECT rsi_14          FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS rsi_14,
            (SELECT macd_hist       FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS macd_hist,
            (SELECT macd_line       FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS macd_line,
            (SELECT macd_signal     FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS macd_signal,
            (SELECT sma_20          FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS sma_20,
            (SELECT sma_50          FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS sma_50,
            (SELECT sma_200         FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS sma_200,
            (SELECT ema_9           FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS ema_9,
            (SELECT ema_21          FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS ema_21,
            (SELECT obv             FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS obv,
            (SELECT vwap_20         FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS vwap_20,
            (SELECT cci_20          FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS cci_20,
            (SELECT beta_1y         FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS beta_1y,
            (SELECT rs_6m_vs_nifty  FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS rs_6m_vs_nifty,
            (SELECT pct_from_52w_high FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS pct_from_52w_high,
            (SELECT pct_from_52w_low  FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1) AS pct_from_52w_low
        FROM stocks s
        WHERE s.symbol = :symbol AND s.is_active = TRUE
    """
    result = await db.execute(text(sql), {"symbol": symbol.upper()})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")
    data = dict(row._mapping)
    # Compute 1-day change % in Python (prev_close came from correlated subquery)
    latest = data.get("latest_close")
    prev = data.pop("prev_close", None)
    if latest is not None and prev and float(prev) != 0:
        data["change_pct"] = round((float(latest) - float(prev)) / float(prev) * 100, 2)
    else:
        data["change_pct"] = None
    return data


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


