# Phase 4 — Ratio Engine & Screener
> **Duration:** Weeks 8–9  
> **Goal:** Compute 20+ financial ratios from stored statements, expose screener API with 15+ filter params, implement FilterPanel in frontend.

---

## Prerequisites
- Phase 3 complete — `financial_statements` and `shareholding_pattern` populated for 10+ stocks
- Latest close price available in `price_data`

---

## 4.1 Ratio Computation Engine

Create `backend/pipeline/ratio_engine.py`:

```python
# backend/pipeline/ratio_engine.py
"""
Computes financial ratios from stored financial_statements data.
Uses the normalised JSONB 'data' column — no re-scraping needed.

All division operations are guarded against zero and None.
A None ratio is stored as NULL in the DB — not as 0 or an error.
"""

import logging
from datetime import date, datetime
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
    """Compute and upsert annual ratios for one stock."""
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

    def latest(series_key, data_dict=d):
        vals = data_dict.get(series_key, [])
        return next((v for v in reversed(vals) if v is not None), None)

    def yoy_growth(series_key, data_dict=d):
        """Year-over-year growth %: (latest - prev) / abs(prev) * 100"""
        vals = [v for v in data_dict.get(series_key, []) if v is not None]
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
    revenue  = latest("revenue")
    ebitda   = latest("operating_profit")         # screener.in label
    deprec   = latest("depreciation")
    ebit     = latest("ebit") or (
        (ebitda - deprec) if ebitda is not None and deprec is not None else None
    )
    interest = latest("interest")
    equity   = latest("shareholders_equity") or latest("net_worth") or latest("total_equity")
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
    eps         = latest("eps") or safe_div(pat, shares)
    book_val_ps = safe_div(equity, shares)

    # ─── Compute all ratios ────────────────────────────────────────────────────
    ratios = {
        # Valuation (need market price)
        "pe_ratio":       safe_div(latest_close, eps) if eps and eps > 0 else None,
        "pb_ratio":       safe_div(latest_close, book_val_ps) if book_val_ps and book_val_ps > 0 else None,
        "ps_ratio":       safe_div(latest_close * (shares or 0), revenue) if revenue else None,

        # Profitability
        "roe":            safe_div(pat,    equity)     and round(safe_div(pat, equity) * 100, 3),
        "roce":           safe_div(ebit,   tot_assets) and round(safe_div(ebit, tot_assets) * 100, 3),
        "roa":            safe_div(pat,    tot_assets) and round(safe_div(pat, tot_assets) * 100, 3),
        "pat_margin":     safe_div(pat,    revenue)    and round(safe_div(pat, revenue) * 100, 3),
        "ebitda_margin":  safe_div(ebitda, revenue)    and round(safe_div(ebitda, revenue) * 100, 3),

        # Leverage
        "debt_equity":    safe_div(borrowings, equity),
        "interest_cov":   safe_div(ebit,       interest),
        "current_ratio":  safe_div(curr_assets, curr_liab),

        # Growth
        "revenue_growth": yoy_growth("revenue"),
        "pat_growth":     yoy_growth("net_profit"),
        "eps_growth":     yoy_growth("eps") or yoy_growth("net_profit"),  # fallback

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
            period_data = dict(row["data"])  # JSONB -> dict
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
```

---

## 4.2 Enable Ratio Jobs in Scheduler

```python
# In pipeline/scheduler.py — uncomment:
from pipeline.ratio_engine import run_ratio_compute_all

scheduler.add_job(
    run_ratio_compute_all,
    CronTrigger(day_of_week="sun", hour=9, minute=0),
    max_instances=1,
    id="ratio_compute"
)
```

---

## 4.3 Screener API

Create `backend/app/routers/screener.py`:

```python
# backend/app/routers/screener.py
"""
Dynamic screener endpoint. Builds a WHERE clause from filter params.
Joins stocks + financial_ratios + latest price in one query.
"""
from fastapi import APIRouter, Query, Depends
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
    min_interest_cov:Optional[float] = None,
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
    # Build filter clauses dynamically
    filters = ["s.is_active = TRUE", "s.is_index = FALSE"]
    params  = {"limit": limit, "offset": (page - 1) * limit}

    def add_filter(col, op, val, key):
        if val is not None:
            filters.append(f"{col} {op} :{key}")
            params[key] = val

    add_filter("r.min_pe",           ">=", min_pe,           "min_pe")
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
    from app.routers.stocks import _get_stock_id
    stock = await _get_stock_id(symbol, db)
    if not stock:
        from fastapi import HTTPException
        raise HTTPException(404, f"Stock '{symbol}' not found")

    sql = """
        SELECT period_end, period_type, pe_ratio, pb_ratio, roe, roce, roa,
               pat_margin, ebitda_margin, debt_equity, interest_cov, current_ratio,
               revenue_growth, pat_growth, eps, book_value_ps, cfo_to_pat, computed_at
        FROM financial_ratios
        WHERE stock_id = :sid AND period_type = :pt
        ORDER BY period_end DESC
        LIMIT :limit
    """
    result = await db.execute(text(sql), {"sid": stock["id"], "pt": period_type, "limit": limit})
    return {"symbol": symbol.upper(), "records": [dict(r._mapping) for r in result.fetchall()]}
```

Register in `main.py`:

```python
from app.routers import screener as screener_router
app.include_router(screener_router.router, prefix="/api/v1", tags=["Screener"])
```

---

## 4.4 Compare Endpoint

Add to `backend/app/routers/stocks.py`:

```python
@router.get("/compare")
async def compare_stocks(
    symbols: str = Query(..., description="Comma-separated symbols, max 5"),
    db: AsyncSession = Depends(get_db),
):
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
```

---

## 4.5 Frontend — Screener Page & FilterPanel

Create `frontend/src/pages/Screener.jsx`:

```jsx
// frontend/src/pages/Screener.jsx
import { useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { fetchScreener } from "../store/slices/stocksSlice";

const SECTORS = ["Banking","IT","Pharma","Auto","FMCG","Energy","Telecom","NBFC","Infrastructure","Metals"];
const RATINGS = ["STRONG_BUY","BUY","HOLD","SELL","STRONG_SELL"];
const MKT_CAPS = [["large","Large Cap"],["mid","Mid Cap"],["small","Small Cap"]];

export default function Screener() {
  const dispatch = useDispatch();
  const { screenerResult, status } = useSelector(s => s.stocks);
  const [filters, setFilters] = useState({
    min_roe: "", max_pe: "", max_debt_equity: "",
    min_pat_margin: "", min_revenue_growth: "",
    sector: "", market_cap_cat: "", rating_label: "",
    sort_by: "total_score", order: "desc",
  });

  const setF = (key, val) => setFilters(f => ({ ...f, [key]: val }));

  const apply = () => {
    const clean = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v !== "" && v !== null)
    );
    dispatch(fetchScreener(clean));
  };

  const reset = () => {
    setFilters({ min_roe: "", max_pe: "", max_debt_equity: "",
                 min_pat_margin: "", min_revenue_growth: "",
                 sector: "", market_cap_cat: "", rating_label: "",
                 sort_by: "total_score", order: "desc" });
  };

  return (
    <div className="cal-screener-layout">
      {/* Filter Sidebar */}
      <aside className="cal-filter-sidebar">
        <h2 className="cal-filter-heading">Filters</h2>

        <div className="cal-filter-group">
          <label className="cal-filter-label">Sector</label>
          <select className="cal-select" value={filters.sector} onChange={e => setF("sector", e.target.value)}>
            <option value="">All Sectors</option>
            {SECTORS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div className="cal-filter-group">
          <label className="cal-filter-label">Market Cap</label>
          {MKT_CAPS.map(([val, label]) => (
            <button
              key={val}
              className={`cal-chip ${filters.market_cap_cat === val ? "cal-chip--active" : ""}`}
              onClick={() => setF("market_cap_cat", filters.market_cap_cat === val ? "" : val)}
            >{label}</button>
          ))}
        </div>

        <div className="cal-filter-group">
          <label className="cal-filter-label">Rating</label>
          {RATINGS.map(r => (
            <button
              key={r}
              className={`cal-chip ${filters.rating_label === r ? "cal-chip--active" : ""}`}
              onClick={() => setF("rating_label", filters.rating_label === r ? "" : r)}
            >{r.replace("_"," ")}</button>
          ))}
        </div>

        <div className="cal-filter-group">
          <label className="cal-filter-label">Min ROE (%)</label>
          <input className="cal-input" type="number" placeholder="e.g. 15"
            value={filters.min_roe} onChange={e => setF("min_roe", e.target.value)} />
        </div>

        <div className="cal-filter-group">
          <label className="cal-filter-label">Max P/E</label>
          <input className="cal-input" type="number" placeholder="e.g. 30"
            value={filters.max_pe} onChange={e => setF("max_pe", e.target.value)} />
        </div>

        <div className="cal-filter-group">
          <label className="cal-filter-label">Max Debt/Equity</label>
          <input className="cal-input" type="number" placeholder="e.g. 1.0"
            value={filters.max_debt_equity} onChange={e => setF("max_debt_equity", e.target.value)} />
        </div>

        <div className="cal-filter-group">
          <label className="cal-filter-label">Min PAT Margin (%)</label>
          <input className="cal-input" type="number" placeholder="e.g. 10"
            value={filters.min_pat_margin} onChange={e => setF("min_pat_margin", e.target.value)} />
        </div>

        <div className="cal-filter-group">
          <label className="cal-filter-label">Min Revenue Growth (%)</label>
          <input className="cal-input" type="number" placeholder="e.g. 15"
            value={filters.min_revenue_growth} onChange={e => setF("min_revenue_growth", e.target.value)} />
        </div>

        <div className="cal-filter-actions">
          <button className="cal-btn cal-btn--primary" onClick={apply}>Apply Filters</button>
          <button className="cal-btn cal-btn--ghost"   onClick={reset}>Reset</button>
        </div>
      </aside>

      {/* Results */}
      <main className="cal-screener-results">
        <div className="cal-results-header">
          <span>{screenerResult.length} stocks found</span>
          <select className="cal-select cal-select--sm"
            value={filters.sort_by}
            onChange={e => setF("sort_by", e.target.value)}>
            <option value="total_score">Rating Score</option>
            <option value="roe">ROE</option>
            <option value="pe_ratio">P/E</option>
            <option value="revenue_growth">Revenue Growth</option>
          </select>
        </div>

        <table className="cal-table">
          <thead>
            <tr>
              <th>Symbol</th><th>Company</th><th>Sector</th>
              <th>Price</th><th>P/E</th><th>ROE%</th>
              <th>D/E</th><th>Rev Growth%</th><th>Rating</th>
            </tr>
          </thead>
          <tbody>
            {screenerResult.map(s => (
              <tr key={s.symbol} className="cal-table-row cal-table-row--clickable"
                onClick={() => { window.location.hash = `#/stocks/${s.symbol}` }}>
                <td className="cal-symbol">{s.symbol}</td>
                <td>{s.company_name}</td>
                <td><span className="cal-badge">{s.sector}</span></td>
                <td>₹{s.latest_close?.toFixed(2) ?? "—"}</td>
                <td>{s.pe_ratio?.toFixed(1) ?? "—"}</td>
                <td className={s.roe >= 15 ? "cal-positive" : ""}>{s.roe?.toFixed(1) ?? "—"}%</td>
                <td className={s.debt_equity > 1 ? "cal-negative" : ""}>{s.debt_equity?.toFixed(2) ?? "—"}</td>
                <td className={s.revenue_growth >= 0 ? "cal-positive" : "cal-negative"}>
                  {s.revenue_growth?.toFixed(1) ?? "—"}%
                </td>
                <td><RatingBadge label={s.rating_label} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}

function RatingBadge({ label }) {
  if (!label) return <span className="cal-badge cal-badge--muted">—</span>;
  const colors = { STRONG_BUY:"cal-badge--green", BUY:"cal-badge--teal",
                   HOLD:"cal-badge--amber", SELL:"cal-badge--orange", STRONG_SELL:"cal-badge--red" };
  return <span className={`cal-badge ${colors[label]||"cal-badge--muted"}`}>{label.replace("_"," ")}</span>;
}
```

---

## 4.6 Validation Checklist

```bash
# 1. Run ratio compute manually for a single stock
python3 -c "
import asyncio
from pipeline.ratio_engine import compute_ratios_for_stock, _get_latest_close
async def test():
    close = await _get_latest_close(1)  # stock_id 1
    await compute_ratios_for_stock(1, close)
    print('Done')
asyncio.run(test())
"

# 2. Verify ratios in DB
psql -U user -d nivesh -c "
  SELECT r.pe_ratio, r.roe, r.debt_equity, r.pat_margin, r.revenue_growth
  FROM financial_ratios r
  JOIN stocks s ON s.id = r.stock_id
  WHERE s.symbol = 'BHARTIARTL'
  ORDER BY r.period_end DESC LIMIT 1;
"

# 3. Screener API — basic filter
curl "http://localhost:8000/api/v1/screener?min_roe=10&max_pe=40&sector=IT" | jq '{total, first: .results[0].symbol}'

# 4. Verify filter correctness
curl "http://localhost:8000/api/v1/screener?min_roe=15" | jq '[.results[] | select(.roe < 15)] | length'
# Must return 0 — no results with roe < 15

# 5. Compare endpoint
curl "http://localhost:8000/api/v1/compare?symbols=RELIANCE,TCS,INFY" | jq '.comparison | length'

# 6. Query plan — must use idx_ratios_screener
psql -U user -d nivesh -c "
  EXPLAIN ANALYZE
  SELECT * FROM financial_ratios WHERE roe > 15 AND pe_ratio < 30
  ORDER BY roe DESC LIMIT 25;
"
```

---

## 4.7 Deliverables for Phase 4

- [ ] `pipeline/ratio_engine.py` implemented
- [ ] Ratios computed for all stocks with fundamentals — `financial_ratios` table populated
- [ ] Ratio compute job scheduled (Sunday 09:00 IST, after fundamental scrape)
- [ ] `GET /api/v1/screener` with all 15 filter params working
- [ ] `GET /api/v1/stocks/{symbol}/ratios` returns ratio history
- [ ] `GET /api/v1/compare?symbols=` returns side-by-side data for up to 5 stocks
- [ ] Screener filter correctness verified (no false positives in results)
- [ ] `EXPLAIN ANALYZE` confirms index usage on screener queries
- [ ] `Screener.jsx` page renders and filters correctly
- [ ] StockDetail Overview tab shows key ratios from `/stocks/{symbol}`
