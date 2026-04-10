# Phase 2 — Price Ingestion & Basic Stock API
> **Duration:** Weeks 3–4  
> **Goal:** Daily OHLCV pipeline running, 5-year backfill complete, basic stock listing and price endpoints live.

---

## Prerequisites
- Phase 1 complete — all tables exist, stocks table seeded
- `yfinance` installed and validated
- APScheduler wired into FastAPI lifespan

---

## 2.1 Price Ingestion Pipeline

Create `backend/pipeline/price_ingestion.py`:

```python
# backend/pipeline/price_ingestion.py
import asyncio
import logging
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from pipeline.audit import audit_job
from app.database import raw_connection

logger = logging.getLogger(__name__)

CHUNK_SIZE = 50   # max symbols per yfinance batch call

# ─── Main entry point (called by APScheduler) ────────────────────────────────

async def run_daily_price_ingestion():
    """Fetches last 5 trading days for all active stocks."""
    async with audit_job("price_daily_ingestion") as audit:
        stocks = await _fetch_active_stocks()
        chunks = [stocks[i:i+CHUNK_SIZE] for i in range(0, len(stocks), CHUNK_SIZE)]
        total = 0
        for chunk in chunks:
            count = await _ingest_chunk(chunk, period="5d")
            total += count
            await asyncio.sleep(1)  # brief pause between chunks
        audit.records_out = total
        logger.info(f"price_daily_ingestion complete: {total} rows upserted")

async def run_index_ingestion():
    """Fetches last 5 trading days for all indices."""
    async with audit_job("index_daily_ingestion") as audit:
        indices = await _fetch_active_stocks(indices_only=True)
        count = await _ingest_chunk(indices, period="5d")
        audit.records_out = count

# ─── Backfill (run once from seed script) ────────────────────────────────────

async def run_backfill(period: str = "5y"):
    """Fetches full price history. Run once from scripts/seed/backfill_prices.py."""
    async with audit_job("price_backfill") as audit:
        stocks = await _fetch_active_stocks()
        chunks = [stocks[i:i+CHUNK_SIZE] for i in range(0, len(stocks), CHUNK_SIZE)]
        total = 0
        for i, chunk in enumerate(chunks):
            count = await _ingest_chunk(chunk, period=period)
            total += count
            logger.info(f"Backfill chunk {i+1}/{len(chunks)}: {count} rows")
            await asyncio.sleep(2)  # polite delay for backfill
        audit.records_out = total

# ─── Core ingestion logic ─────────────────────────────────────────────────────

async def _ingest_chunk(stocks: list, period: str) -> int:
    """Download prices for a batch of stocks and upsert to DB."""
    if not stocks:
        return 0

    tickers_str = " ".join(s["yf_symbol"] for s in stocks)
    try:
        df = yf.download(
            tickers_str,
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,    # adjusts for splits and dividends
            progress=False,
            threads=True,
        )
    except Exception as e:
        logger.error(f"yfinance download failed for chunk: {e}")
        return 0

    total = 0
    for stock in stocks:
        try:
            stock_df = _extract_ticker_df(df, stock["yf_symbol"], len(stocks))
            if stock_df is None or stock_df.empty:
                logger.warning(f"No data for {stock['yf_symbol']}")
                continue
            count = await _upsert_price_rows(stock["id"], stock_df)
            total += count
        except Exception as e:
            logger.error(f"Failed to upsert {stock['symbol']}: {e}")

    return total

def _extract_ticker_df(df: pd.DataFrame, yf_symbol: str, num_tickers: int) -> pd.DataFrame:
    """Extract a single ticker's data from a (possibly multi-ticker) DataFrame."""
    if num_tickers == 1:
        # Single ticker: df columns are ['Open', 'High', 'Low', 'Close', 'Volume']
        return df
    try:
        # Multi-ticker: df has MultiIndex columns (ticker, field)
        ticker_df = df[yf_symbol]
        if ticker_df.empty:
            return None
        return ticker_df
    except KeyError:
        return None

async def _upsert_price_rows(stock_id: int, df: pd.DataFrame) -> int:
    """Upsert rows into price_data. Uses ON CONFLICT to handle re-runs safely."""
    rows = []
    for idx, row in df.iterrows():
        if pd.isna(row.get("Close")):
            continue
        rows.append((
            stock_id,
            idx.date() if hasattr(idx, "date") else idx,
            _safe_float(row.get("Open")),
            _safe_float(row.get("High")),
            _safe_float(row.get("Low")),
            float(row["Close"]),
            float(row["Close"]),       # adj_close = close (auto_adjust=True handles this)
            int(row.get("Volume") or 0),
        ))

    if not rows:
        return 0

    sql = """
        INSERT INTO price_data (stock_id, price_date, open, high, low, close, adj_close, volume)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (stock_id, price_date) DO UPDATE SET
            open      = EXCLUDED.open,
            high      = EXCLUDED.high,
            low       = EXCLUDED.low,
            close     = EXCLUDED.close,
            adj_close = EXCLUDED.adj_close,
            volume    = EXCLUDED.volume
    """
    async with raw_connection() as conn:
        await conn.executemany(sql, rows)

    return len(rows)

# ─── DB helpers ──────────────────────────────────────────────────────────────

async def _fetch_active_stocks(indices_only: bool = False) -> list:
    sql = """
        SELECT id, symbol, yf_symbol
        FROM stocks
        WHERE is_active = TRUE
          AND is_index = $1
        ORDER BY id
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql, indices_only)
        return [dict(r) for r in rows]

def _safe_float(v) -> float | None:
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None
```

---

## 2.2 Backfill Script

Create `backend/scripts/seed/backfill_prices.py`:

```python
"""
One-time script: fetch 5 years of daily OHLCV for all stocks.
Run from backend/ directory: python scripts/seed/backfill_prices.py

Expected runtime: 20–40 minutes for ~200 stocks (network-dependent).
"""
import asyncio
import sys
sys.path.insert(0, ".")

from pipeline.price_ingestion import run_backfill

if __name__ == "__main__":
    period = sys.argv[1] if len(sys.argv) > 1 else "5y"
    print(f"Starting price backfill (period={period})...")
    asyncio.run(run_backfill(period=period))
    print("Backfill complete.")
```

---

## 2.3 Enable Price Jobs in Scheduler

Uncomment lines in `backend/pipeline/scheduler.py`:

```python
from pipeline.price_ingestion import run_daily_price_ingestion, run_index_ingestion

def configure_scheduler():
    scheduler.add_job(
        run_daily_price_ingestion,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=30),
        max_instances=1,
        id="price_daily"
    )
    scheduler.add_job(
        run_index_ingestion,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=40),
        max_instances=1,
        id="index_daily"
    )
```

---

## 2.4 Backend API — `routers/stocks.py`

Create `backend/app/routers/stocks.py`:

```python
# backend/app/routers/stocks.py
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from typing import Optional
from datetime import date, timedelta
from app.database import get_db
from app.models import Stock, PriceData
from app import schemas

router = APIRouter()

# ─── GET /stocks — paginated listing ─────────────────────────────────────────

@router.get("/stocks")
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

@router.get("/stocks/search")
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

@router.get("/stocks/{symbol}")
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

@router.get("/stocks/{symbol}/price")
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
              AND (:from_date IS NULL OR price_date >= :from_date)
              AND (:to_date   IS NULL OR price_date <= :to_date)
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
              AND (:from_date IS NULL OR price_date >= :from_date)
              AND (:to_date   IS NULL OR price_date <= :to_date)
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
              AND (:from_date IS NULL OR price_date >= :from_date)
              AND (:to_date   IS NULL OR price_date <= :to_date)
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
```

---

## 2.5 Register Router in main.py

Add to `backend/app/main.py` (additive only):

```python
from app.routers import stocks as stocks_router
app.include_router(stocks_router.router, prefix="/api/v1", tags=["Stocks"])
```

---

## 2.6 Frontend — Basic StockListing Page

Implement the existing `frontend/src/pages/StockListing.jsx` placeholder:

```jsx
// frontend/src/pages/StockListing.jsx
import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { fetchStocks, setFilter, setPage } from "../store/slices/stocksSlice";

export default function StockListing() {
  const dispatch  = useDispatch();
  const { list, pagination, filters, status } = useSelector(s => s.stocks);
  const [search, setSearch] = useState("");

  useEffect(() => {
    dispatch(fetchStocks({ ...filters, page: pagination.page, limit: 25 }));
  }, [filters, pagination.page]);

  return (
    <div className="cal-page">
      <div className="cal-page-header">
        <h1 className="cal-heading">Stocks</h1>
        <input
          className="cal-search-input"
          placeholder="Search symbol or company..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === "Enter" && dispatch(fetchStocks({ q: search }))}
        />
      </div>

      {/* Filter Bar */}
      <div className="cal-filter-bar">
        {["Banking","IT","Pharma","Auto","FMCG","Energy","Telecom"].map(sec => (
          <button
            key={sec}
            className={`cal-chip ${filters.sector === sec ? "cal-chip--active" : ""}`}
            onClick={() => dispatch(setFilter({ key: "sector", val: filters.sector === sec ? "" : sec }))}
          >
            {sec}
          </button>
        ))}
      </div>

      {/* Stock Table */}
      {status === "loading" ? (
        <div className="cal-loading-skeleton" />
      ) : (
        <table className="cal-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Company</th>
              <th>Sector</th>
              <th>Price</th>
              <th>Change</th>
              <th>Rating</th>
            </tr>
          </thead>
          <tbody>
            {list.map(stock => (
              <tr
                key={stock.symbol}
                className="cal-table-row cal-table-row--clickable"
                onClick={() => { window.location.hash = `#/stocks/${stock.symbol}` }}
              >
                <td className="cal-symbol">{stock.symbol}</td>
                <td>{stock.company_name}</td>
                <td><span className="cal-badge">{stock.sector}</span></td>
                <td>₹{stock.latest_close?.toFixed(2) ?? "—"}</td>
                <td className={stock.change_pct >= 0 ? "cal-positive" : "cal-negative"}>
                  {stock.change_pct != null ? `${stock.change_pct > 0 ? "+" : ""}${stock.change_pct}%` : "—"}
                </td>
                <td><RatingBadge label={stock.rating_label} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Pagination */}
      <div className="cal-pagination">
        <button disabled={pagination.page <= 1} onClick={() => dispatch(setPage(pagination.page - 1))}>←</button>
        <span>Page {pagination.page} of {Math.ceil(pagination.total / 25)}</span>
        <button onClick={() => dispatch(setPage(pagination.page + 1))}>→</button>
      </div>
    </div>
  );
}

function RatingBadge({ label }) {
  if (!label) return <span className="cal-badge cal-badge--muted">—</span>;
  const colors = {
    STRONG_BUY: "cal-badge--green",
    BUY:        "cal-badge--teal",
    HOLD:       "cal-badge--amber",
    SELL:       "cal-badge--orange",
    STRONG_SELL:"cal-badge--red",
  };
  return <span className={`cal-badge ${colors[label] || "cal-badge--muted"}`}>{label.replace("_", " ")}</span>;
}
```

Create `frontend/src/api/stockService.js`:

```javascript
// frontend/src/api/stockService.js
import axios from "./client";  // reuse existing Axios instance

const stockService = {
  getStocks:      (params)  => axios.get("/api/v1/stocks",              { params }).then(r => r.data),
  searchStocks:   (q)       => axios.get("/api/v1/stocks/search",       { params: { q } }).then(r => r.data),
  getStockDetail: (symbol)  => axios.get(`/api/v1/stocks/${symbol}`).then(r => r.data),
  getPriceHistory:(symbol, params) => axios.get(`/api/v1/stocks/${symbol}/price`, { params }).then(r => r.data),
  getFundamentals:(symbol, params) => axios.get(`/api/v1/stocks/${symbol}/fundamentals`, { params }).then(r => r.data),
  getRatios:      (symbol)  => axios.get(`/api/v1/stocks/${symbol}/ratios`).then(r => r.data),
  getTechnicals:  (symbol, timeframe = "1d") => axios.get(`/api/v1/stocks/${symbol}/technicals`, { params: { timeframe } }).then(r => r.data),
  getPatterns:    (symbol)  => axios.get(`/api/v1/stocks/${symbol}/patterns`).then(r => r.data),
  getRating:      (symbol)  => axios.get(`/api/v1/stocks/${symbol}/rating`).then(r => r.data),
  getScreener:    (filters) => axios.get("/api/v1/screener",            { params: filters }).then(r => r.data),
  getCompare:     (symbols) => axios.get("/api/v1/compare",             { params: { symbols: symbols.join(",") } }).then(r => r.data),
};

export default stockService;
```

Create `frontend/src/store/slices/stocksSlice.js`:

```javascript
// frontend/src/store/slices/stocksSlice.js
import { createSlice, createAsyncThunk } from "@reduxjs/toolkit";
import stockService from "../../api/stockService";

export const fetchStocks      = createAsyncThunk("stocks/fetchAll",    (p) => stockService.getStocks(p));
export const searchStocks     = createAsyncThunk("stocks/search",      (q) => stockService.searchStocks(q));
export const fetchStockDetail = createAsyncThunk("stocks/fetchDetail", (s) => stockService.getStockDetail(s));
export const fetchScreener    = createAsyncThunk("stocks/screener",    (f) => stockService.getScreener(f));

const stocksSlice = createSlice({
  name: "stocks",
  initialState: {
    list:           [],
    detail:         null,
    screenerResult: [],
    filters:        { sector: "", market_cap_cat: "", rating_label: "", min_roe: "", max_pe: "", max_debt_equity: "" },
    pagination:     { page: 1, limit: 25, total: 0 },
    status:         "idle",
    error:          null,
  },
  reducers: {
    setFilter:    (state, { payload: { key, val } }) => { state.filters[key] = val; state.pagination.page = 1; },
    resetFilters: (state) => { state.filters = {}; state.pagination.page = 1; },
    setPage:      (state, { payload }) => { state.pagination.page = payload; },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchStocks.pending,   (s)    => { s.status = "loading"; })
      .addCase(fetchStocks.fulfilled, (s, a) => { s.status = "succeeded"; s.list = a.payload.results; s.pagination.total = a.payload.total; })
      .addCase(fetchStocks.rejected,  (s, a) => { s.status = "failed"; s.error = a.error.message; })
      .addCase(fetchStockDetail.fulfilled, (s, a) => { s.detail = a.payload; })
      .addCase(fetchScreener.fulfilled,    (s, a) => { s.screenerResult = a.payload.results; });
  },
});

export const { setFilter, resetFilters, setPage } = stocksSlice.actions;
export default stocksSlice.reducer;
```

Register in Redux store (add to existing store setup):

```javascript
// In store/index.js — add new reducer
import stocksReducer from "./slices/stocksSlice";

// Add to combineReducers or configureStore:
// stocks: stocksReducer
```

Add new hash routes in `App.jsx`:

```javascript
// In existing route map in App.jsx, add:
"#/stocks":          StockListing,
"#/stocks/:symbol":  StockDetail,   // StockDetail still placeholder — Phase 3+
"#/screener":        Screener,      // Screener still placeholder — Phase 4
```

---

## 2.7 Validation Checklist

```bash
# 1. Run backfill (do this first — takes 20–40 min)
cd backend && python scripts/seed/backfill_prices.py 5y

# 2. Verify price data loaded
psql -U user -d nivesh -c "SELECT COUNT(*) FROM price_data;"
# Expected: 500,000+ rows for ~200 stocks × 5 years

# 3. Test price query performance
psql -U user -d nivesh -c "
  EXPLAIN ANALYZE
  SELECT * FROM price_data
  WHERE stock_id = 1
  ORDER BY price_date DESC
  LIMIT 300;
"
# Must use Index Scan on idx_price_stock_date, not Seq Scan

# 4. Test API endpoints
curl "http://localhost:8000/api/v1/stocks?limit=5" | jq '.results[0]'
curl "http://localhost:8000/api/v1/stocks/search?q=reliance" | jq '.results'
curl "http://localhost:8000/api/v1/stocks/RELIANCE" | jq '.latest_close'
curl "http://localhost:8000/api/v1/stocks/RELIANCE/price?interval=1d&limit=10" | jq '.data | length'

# 5. Verify APScheduler registered jobs
curl http://localhost:8000/health | jq '.scheduler'
```

---

## 2.8 Deliverables for Phase 2

- [ ] `pipeline/price_ingestion.py` implemented
- [ ] `scripts/seed/backfill_prices.py` run — 500K+ price rows in DB
- [ ] APScheduler price jobs active (Mon-Fri 18:30 and 18:40 IST)
- [ ] `GET /api/v1/stocks` — returns paginated list with latest price
- [ ] `GET /api/v1/stocks/search` — returns matching stocks
- [ ] `GET /api/v1/stocks/{symbol}` — returns full snapshot
- [ ] `GET /api/v1/stocks/{symbol}/price` — returns OHLCV with interval support
- [ ] `frontend/src/api/stockService.js` created
- [ ] `frontend/src/store/slices/stocksSlice.js` created and registered
- [ ] `StockListing.jsx` renders a live table from the API
- [ ] Index scan confirmed for price_data queries (no seq scans)
- [ ] Existing MF endpoints regression tested — all pass
