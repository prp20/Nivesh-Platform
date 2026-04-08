# backend/app/routers/stocks.py
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from datetime import date
from app.database import get_db
from app.models import Stock, PriceData

router = APIRouter(prefix="/stocks", tags=["Stocks"])


# ─── GET /stocks — paginated listing ─────────────────────────────────────────

@router.get("")
async def list_stocks(
    sector:         Optional[str] = None,
    market_cap_cat: Optional[str] = None,
    is_index:       bool = False,
    page:           int  = Query(1, ge=1),
    limit:          int  = Query(25, ge=1, le=100),
    sort_by:        str  = Query("symbol", regex="^(symbol|company_name|sector)$"),
    order:          str  = Query("asc",    regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    filters = ["s.is_active = TRUE", "s.is_index = :is_index"]
    params  = {"is_index": is_index, "limit": limit, "offset": offset}

    if sector:
        filters.append("s.sector = :sector")
        params["sector"] = sector
    if market_cap_cat:
        filters.append("s.market_cap_cat = :market_cap_cat")
        params["market_cap_cat"] = market_cap_cat

    where = " AND ".join(filters)
    sql = f"""
        SELECT
            s.id, s.symbol, s.company_name, s.sector, s.market_cap_cat,
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
        WHERE {where}
        ORDER BY s.{sort_by} {order}
        LIMIT :limit OFFSET :offset
    """
    count_sql = f"SELECT COUNT(*) FROM stocks s WHERE {where}"

    result = await db.execute(text(sql),   params)
    count  = await db.execute(text(count_sql), {k: v for k, v in params.items() if k not in ("limit", "offset")})

    return {
        "results": [dict(r._mapping) for r in result.fetchall()],
        "total":   count.scalar(),
        "page":    page,
        "limit":   limit,
    }


# ─── GET /stocks/search ───────────────────────────────────────────────────────

@router.get("/search")
async def search_stocks(
    q:     str = Query(..., min_length=1, max_length=50),
    limit: int = Query(10, ge=1, le=20),
    db:    AsyncSession = Depends(get_db),
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
async def get_stock(symbol: str, db: AsyncSession = Depends(get_db)):
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
            r.rating_label,
            r.total_score,
            r.fundamental_score,
            r.technical_score,
            ti.rsi_14,
            ti.macd_hist,
            ti.sma_200
        FROM stocks s
        LEFT JOIN LATERAL (
            SELECT close, high, low, volume, price_date
            FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1
        ) p ON TRUE
        LEFT JOIN LATERAL (
            SELECT close FROM price_data WHERE stock_id = s.id ORDER BY price_date DESC LIMIT 1 OFFSET 1
        ) p2 ON TRUE
        LEFT JOIN LATERAL (
            SELECT rating_label, total_score, fundamental_score, technical_score
            FROM stock_ratings WHERE stock_id = s.id ORDER BY rated_on DESC LIMIT 1
        ) r ON TRUE
        LEFT JOIN LATERAL (
            SELECT rsi_14, macd_hist, sma_200
            FROM technical_indicators WHERE stock_id = s.id AND timeframe = '1d' ORDER BY ind_date DESC LIMIT 1
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
):
    stock = await _get_stock_id(symbol, db)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")

    if interval == "1d":
        sql = """
            SELECT price_date AS "time", open, high, low, close, adj_close, volume
            FROM price_data
            WHERE stock_id = :sid
            ORDER BY price_date DESC
            LIMIT :limit
        """
    elif interval == "1w":
        sql = """
            SELECT
                date_trunc('week', price_date)::date AS "time",
                (ARRAY_AGG(open ORDER BY price_date))[1]  AS open,
                MAX(high)                                  AS high,
                MIN(low)                                   AS low,
                (ARRAY_AGG(close ORDER BY price_date DESC))[1] AS close,
                SUM(volume)                                AS volume
            FROM price_data
            WHERE stock_id = :sid
            GROUP BY date_trunc('week', price_date)
            ORDER BY "time" DESC
            LIMIT :limit
        """
    else:  # 1mo
        sql = """
            SELECT
                date_trunc('month', price_date)::date AS "time",
                (ARRAY_AGG(open ORDER BY price_date))[1]       AS open,
                MAX(high)                                       AS high,
                MIN(low)                                        AS low,
                (ARRAY_AGG(close ORDER BY price_date DESC))[1] AS close,
                SUM(volume)                                     AS volume
            FROM price_data
            WHERE stock_id = :sid
            GROUP BY date_trunc('month', price_date)
            ORDER BY "time" DESC
            LIMIT :limit
        """

    result = await db.execute(text(sql), {
        "sid":       stock["id"],
        "from_date": from_date,
        "to_date":   to_date,
        "limit":     limit,
    })
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


