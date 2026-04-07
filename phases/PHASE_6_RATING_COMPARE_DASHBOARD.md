# Phase 6 — Rating Engine, Compare & Dashboard
> **Duration:** Weeks 12–13  
> **Goal:** Rule-based stock rating system producing STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL labels, Compare page, and updated Dashboard with market overview.

---

## Prerequisites
- Phase 4 complete — `financial_ratios` populated
- Phase 5 complete — `technical_indicators` populated
- `shareholding_pattern` has data for rated stocks

---

## 6.1 Rating Engine

Create `backend/pipeline/rating_engine.py`:

```python
# backend/pipeline/rating_engine.py
"""
Rule-based, deterministic stock rating engine.
No ML, no LLM. Produces a 0–100 score and a 5-label rating.

Score weights:
  Fundamental quality  30%
  Valuation            20%
  Technical trend      20%
  Momentum             15%
  Earnings quality     10%
  Shareholding          5%
"""

import logging
from datetime import date
from typing import Optional
from dataclasses import dataclass, asdict
from pipeline.audit import audit_job
from app.database import raw_connection

logger = logging.getLogger(__name__)

# ─── Thresholds ───────────────────────────────────────────────────────────────
# All scores are on a 0–100 scale before weighting.

RATING_LABELS = [
    (75, "STRONG_BUY"),
    (60, "BUY"),
    (40, "HOLD"),
    (25, "SELL"),
    (0,  "STRONG_SELL"),
]


@dataclass
class RatingResult:
    stock_id:           int
    rated_on:           date
    total_score:        float
    rating_label:       str
    fundamental_score:  float
    valuation_score:    float
    technical_score:    float
    momentum_score:     float
    quality_score:      float
    shareholding_score: float
    score_breakdown:    dict


# ─── Main entry points ────────────────────────────────────────────────────────

async def run_rating_compute():
    """Compute ratings for all stocks that have all required data."""
    async with audit_job("rating_compute") as audit:
        stocks = await _fetch_ratable_stocks()
        total = 0
        for stock in stocks:
            try:
                result = await compute_rating(stock["id"])
                if result:
                    await _upsert_rating(result)
                    total += 1
            except Exception as e:
                logger.error(f"Rating compute failed for {stock['symbol']}: {e}")
        audit.records_out = total


async def compute_rating(stock_id: int) -> Optional[RatingResult]:
    """Compute a single stock's rating. Returns None if insufficient data."""
    ratios   = await _get_latest_ratios(stock_id)
    ti       = await _get_latest_technicals(stock_id)
    sh       = await _get_latest_shareholding(stock_id)
    price_data = await _get_price_metrics(stock_id)

    if not ratios or not ti:
        return None  # minimum required data

    close = price_data.get("latest_close")

    # ─── Compute sub-scores ───────────────────────────────────────────────────
    f_score = score_fundamentals(ratios)
    v_score = score_valuation(ratios)
    t_score = score_technicals(ti, close)
    m_score = score_momentum(ti, price_data)
    e_score = score_earnings_quality(ratios)
    s_score = score_shareholding(sh)

    # ─── Weighted total ───────────────────────────────────────────────────────
    total = round(
        f_score * 0.30 +
        v_score * 0.20 +
        t_score * 0.20 +
        m_score * 0.15 +
        e_score * 0.10 +
        s_score * 0.05,
        3
    )

    label = next(lbl for threshold, lbl in RATING_LABELS if total >= threshold)

    breakdown = {
        "fundamental": {
            "score": f_score,
            "roe":   ratios.get("roe"),
            "roce":  ratios.get("roce"),
            "pat_margin": ratios.get("pat_margin"),
            "revenue_growth": ratios.get("revenue_growth"),
            "debt_equity": ratios.get("debt_equity"),
        },
        "valuation": {
            "score":     v_score,
            "pe_ratio":  ratios.get("pe_ratio"),
            "pb_ratio":  ratios.get("pb_ratio"),
        },
        "technical": {
            "score":    t_score,
            "rsi_14":   ti.get("rsi_14"),
            "macd_hist":ti.get("macd_hist"),
            "vs_sma_200": "above" if close and ti.get("sma_200") and close > ti["sma_200"] else "below",
        },
        "momentum": {
            "score":       m_score,
            "return_1m":   price_data.get("return_1m"),
            "return_3m":   price_data.get("return_3m"),
        },
        "earnings_quality": {
            "score":     e_score,
            "cfo_to_pat":ratios.get("cfo_to_pat"),
            "interest_cov": ratios.get("interest_cov"),
        },
        "shareholding": {
            "score":          s_score,
            "promoter_pct":   sh.get("promoter_pct") if sh else None,
            "promoter_change":sh.get("promoter_change") if sh else None,
            "pledged_pct":    sh.get("pledged_pct") if sh else None,
        },
    }

    return RatingResult(
        stock_id=stock_id,
        rated_on=date.today(),
        total_score=total,
        rating_label=label,
        fundamental_score=f_score,
        valuation_score=v_score,
        technical_score=t_score,
        momentum_score=m_score,
        quality_score=e_score,
        shareholding_score=s_score,
        score_breakdown=breakdown,
    )


# ─── Scoring functions ────────────────────────────────────────────────────────

def score_fundamentals(r: dict) -> float:
    """Score 0–100. Based on profitability, growth, and leverage."""
    score = 0.0

    # ROE (0–25 pts)
    roe = r.get("roe") or 0
    score += 25 if roe >= 20 else 18 if roe >= 15 else 10 if roe >= 10 else 4 if roe >= 5 else 0

    # Revenue Growth YoY (0–20 pts)
    rg = r.get("revenue_growth") or 0
    score += 20 if rg >= 20 else 14 if rg >= 15 else 8 if rg >= 10 else 3 if rg >= 5 else 0

    # PAT Margin (0–20 pts)
    pm = r.get("pat_margin") or 0
    score += 20 if pm >= 15 else 14 if pm >= 10 else 8 if pm >= 5 else 0

    # Debt/Equity — inverse score (0–20 pts, lower D/E = better)
    de = r.get("debt_equity")
    if de is None:
        score += 10   # missing data → neutral
    elif de < 0.25:  score += 20
    elif de < 0.5:   score += 15
    elif de < 1.0:   score += 10
    elif de < 2.0:   score += 5
    else:            score += 0

    # ROCE (0–15 pts)
    roce = r.get("roce") or 0
    score += 15 if roce >= 20 else 10 if roce >= 15 else 5 if roce >= 10 else 0

    return min(score, 100.0)


def score_valuation(r: dict) -> float:
    """Score 0–100. Lower valuation = higher score."""
    score = 0.0

    # PE ratio (0–50 pts)
    pe = r.get("pe_ratio")
    if pe is None or pe <= 0:
        score += 25   # no data → neutral
    elif pe < 10:    score += 50   # deeply undervalued
    elif pe < 15:    score += 40
    elif pe < 20:    score += 35
    elif pe < 25:    score += 25
    elif pe < 35:    score += 15
    elif pe < 50:    score += 5
    else:            score += 0    # very expensive

    # PB ratio (0–30 pts)
    pb = r.get("pb_ratio")
    if pb is None or pb <= 0:
        score += 15   # no data → neutral
    elif pb < 1:     score += 30
    elif pb < 2:     score += 22
    elif pb < 3:     score += 15
    elif pb < 5:     score += 8
    else:            score += 0

    # PEG ratio bonus (0–20 pts)
    peg = r.get("peg_ratio")
    if peg is None:
        score += 10
    elif 0 < peg < 1:    score += 20
    elif peg < 1.5:      score += 10
    elif peg < 2:        score += 5

    return min(score, 100.0)


def score_technicals(ti: dict, close: Optional[float]) -> float:
    """Score 0–100. Trend alignment and momentum signals."""
    score = 0.0

    if close:
        sma_200 = ti.get("sma_200")
        sma_50  = ti.get("sma_50")
        # Trend (0–40 pts)
        if sma_200 and close > sma_200: score += 20
        if sma_50  and close > sma_50:  score += 20

    # RSI (0–30 pts)
    rsi = ti.get("rsi_14") or 50
    if 50 <= rsi <= 65:   score += 30   # ideal bullish zone
    elif 40 <= rsi < 50:  score += 15   # mild bullish
    elif 65 < rsi <= 75:  score += 10   # getting overbought
    elif rsi > 75:        score += 5    # overbought caution
    elif rsi < 30:        score += 10   # oversold — potential reversal bonus

    # MACD Histogram (0–30 pts)
    macd_hist = ti.get("macd_hist") or 0
    if macd_hist > 0:   score += 30
    elif macd_hist > -1: score += 10

    return min(score, 100.0)


def score_momentum(ti: dict, price_data: dict) -> float:
    """Score 0–100. Recent price momentum and ADX trend strength."""
    score = 0.0

    # 1-month return (0–40 pts)
    r1m = price_data.get("return_1m") or 0
    if r1m > 10:    score += 40
    elif r1m > 5:   score += 28
    elif r1m > 0:   score += 15
    elif r1m > -5:  score += 5
    else:           score += 0

    # 3-month return (0–40 pts)
    r3m = price_data.get("return_3m") or 0
    if r3m > 20:    score += 40
    elif r3m > 10:  score += 28
    elif r3m > 0:   score += 15
    elif r3m > -10: score += 5
    else:           score += 0

    # ADX strength (0–20 pts) — higher ADX = stronger trend
    adx = ti.get("adx_14") or 0
    if adx > 40:    score += 20
    elif adx > 25:  score += 12
    elif adx > 20:  score += 6

    return min(score, 100.0)


def score_earnings_quality(r: dict) -> float:
    """Score 0–100. Cash flow quality and financial safety."""
    score = 0.0

    # CFO/PAT (0–40 pts) — ratio > 1 means cash-backed earnings
    cfo_pat = r.get("cfo_to_pat")
    if cfo_pat is None:
        score += 20
    elif cfo_pat >= 1.5:  score += 40
    elif cfo_pat >= 1.0:  score += 30
    elif cfo_pat >= 0.7:  score += 15
    elif cfo_pat >= 0.5:  score += 5
    else:                 score += 0

    # Interest Coverage (0–30 pts)
    ic = r.get("interest_cov")
    if ic is None:
        score += 15
    elif ic >= 5:    score += 30
    elif ic >= 3:    score += 20
    elif ic >= 2:    score += 10
    elif ic >= 1:    score += 5
    else:            score += 0

    # PAT Growth consistency (0–30 pts)
    pat_growth = r.get("pat_growth") or 0
    if pat_growth >= 20:   score += 30
    elif pat_growth >= 10: score += 20
    elif pat_growth >= 0:  score += 10
    else:                  score += 0

    return min(score, 100.0)


def score_shareholding(sh: Optional[dict]) -> float:
    """Score 0–100. Promoter confidence and institutional activity."""
    if not sh:
        return 50.0   # no data → neutral

    score = 0.0

    # Promoter holding level (0–40 pts)
    promo = sh.get("promoter_pct") or 0
    if promo >= 60:    score += 40
    elif promo >= 50:  score += 30
    elif promo >= 40:  score += 20
    elif promo >= 30:  score += 10

    # Promoter holding trend (0–30 pts)
    promo_chg = sh.get("promoter_change") or 0
    if promo_chg > 2:    score += 30   # buying aggressively
    elif promo_chg > 0:  score += 20
    elif promo_chg > -1: score += 10   # stable
    else:                score += 0    # selling

    # Pledged shares penalty (0–30 pts, penalty if high)
    pledged = sh.get("pledged_pct") or 0
    if pledged == 0:     score += 30
    elif pledged < 5:    score += 20
    elif pledged < 15:   score += 10
    elif pledged < 30:   score += 5
    else:                score += 0   # >30% pledged is high risk

    return min(score, 100.0)


# ─── DB helpers ───────────────────────────────────────────────────────────────

async def _get_latest_ratios(stock_id: int) -> Optional[dict]:
    async with raw_connection() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM financial_ratios WHERE stock_id=$1 AND period_type='annual'
               ORDER BY period_end DESC LIMIT 1""",
            stock_id
        )
        return dict(row) if row else None


async def _get_latest_technicals(stock_id: int) -> Optional[dict]:
    async with raw_connection() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM technical_indicators WHERE stock_id=$1 AND timeframe='1d'
               ORDER BY ind_date DESC LIMIT 1""",
            stock_id
        )
        return dict(row) if row else None


async def _get_latest_shareholding(stock_id: int) -> Optional[dict]:
    async with raw_connection() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM shareholding_pattern WHERE stock_id=$1
               ORDER BY period_end DESC LIMIT 1""",
            stock_id
        )
        return dict(row) if row else None


async def _get_price_metrics(stock_id: int) -> dict:
    """Return latest close, 1-month return, and 3-month return."""
    sql = """
        SELECT
            close AS latest_close,
            (close - LAG(close, 22)  OVER (ORDER BY price_date)) /
                NULLIF(LAG(close, 22)  OVER (ORDER BY price_date), 0) * 100 AS return_1m,
            (close - LAG(close, 66)  OVER (ORDER BY price_date)) /
                NULLIF(LAG(close, 66)  OVER (ORDER BY price_date), 0) * 100 AS return_3m
        FROM price_data
        WHERE stock_id = $1
        ORDER BY price_date DESC
        LIMIT 1
    """
    # Subquery approach for correctness:
    sql = """
        SELECT
            curr.close                                                           AS latest_close,
            ROUND((curr.close - m1.close)  / NULLIF(m1.close, 0) * 100, 2)    AS return_1m,
            ROUND((curr.close - m3.close)  / NULLIF(m3.close, 0) * 100, 2)    AS return_3m
        FROM
            (SELECT close FROM price_data WHERE stock_id=$1 ORDER BY price_date DESC LIMIT 1)                    curr,
            (SELECT close FROM price_data WHERE stock_id=$1 ORDER BY price_date DESC LIMIT 1 OFFSET 22)  m1,
            (SELECT close FROM price_data WHERE stock_id=$1 ORDER BY price_date DESC LIMIT 1 OFFSET 66)  m3
    """
    async with raw_connection() as conn:
        row = await conn.fetchrow(sql, stock_id)
        return dict(row) if row else {"latest_close": None, "return_1m": None, "return_3m": None}


async def _fetch_ratable_stocks() -> list:
    """Stocks that have both financial_ratios and technical_indicators."""
    sql = """
        SELECT DISTINCT s.id, s.symbol
        FROM stocks s
        WHERE s.is_active = TRUE
          AND s.is_index  = FALSE
          AND EXISTS (SELECT 1 FROM financial_ratios     r  WHERE r.stock_id  = s.id)
          AND EXISTS (SELECT 1 FROM technical_indicators ti WHERE ti.stock_id = s.id)
        ORDER BY s.id
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql)
        return [dict(r) for r in rows]


async def _upsert_rating(result: RatingResult):
    import json
    sql = """
        INSERT INTO stock_ratings
            (stock_id, rated_on, total_score, rating_label,
             fundamental_score, valuation_score, technical_score,
             momentum_score, quality_score, shareholding_score, score_breakdown)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
        ON CONFLICT (stock_id, rated_on)
        DO UPDATE SET
            total_score=$3, rating_label=$4,
            fundamental_score=$5, valuation_score=$6, technical_score=$7,
            momentum_score=$8, quality_score=$9, shareholding_score=$10,
            score_breakdown=$11::jsonb
    """
    async with raw_connection() as conn:
        await conn.execute(sql,
            result.stock_id, result.rated_on,
            result.total_score, result.rating_label,
            result.fundamental_score, result.valuation_score, result.technical_score,
            result.momentum_score, result.quality_score, result.shareholding_score,
            json.dumps(result.score_breakdown),
        )
```

---

## 6.2 Enable Rating Job in Scheduler

```python
# In pipeline/scheduler.py — uncomment:
from pipeline.rating_engine import run_rating_compute

scheduler.add_job(
    run_rating_compute,
    CronTrigger(day_of_week="mon-fri", hour=20, minute=15),
    max_instances=1, id="ratings"
)
```

---

## 6.3 Ratings API

Create `backend/app/routers/ratings.py`:

```python
# backend/app/routers/ratings.py
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.routers.stocks import _get_stock_id

router = APIRouter()

@router.get("/stocks/{symbol}/rating")
async def get_rating(
    symbol:  str,
    history: bool = False,
    limit:   int  = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stock = await _get_stock_id(symbol, db)
    if not stock:
        raise HTTPException(404, f"Stock '{symbol}' not found")

    if history:
        sql = """
            SELECT rated_on, total_score, rating_label,
                   fundamental_score, valuation_score, technical_score,
                   momentum_score, quality_score, shareholding_score
            FROM stock_ratings WHERE stock_id = :sid
            ORDER BY rated_on DESC LIMIT :limit
        """
        result = await db.execute(text(sql), {"sid": stock["id"], "limit": limit})
        return {"symbol": symbol.upper(), "history": [dict(r._mapping) for r in result.fetchall()]}
    else:
        sql = """
            SELECT rated_on, total_score, rating_label,
                   fundamental_score, valuation_score, technical_score,
                   momentum_score, quality_score, shareholding_score, score_breakdown
            FROM stock_ratings WHERE stock_id = :sid
            ORDER BY rated_on DESC LIMIT 1
        """
        result = await db.execute(text(sql), {"sid": stock["id"]})
        row = result.fetchone()
        if not row:
            raise HTTPException(404, f"No rating data for '{symbol}'")
        return {"symbol": symbol.upper(), **dict(row._mapping)}
```

Register in `main.py`:

```python
from app.routers import ratings as ratings_router
app.include_router(ratings_router.router, prefix="/api/v1", tags=["Ratings"])
```

---

## 6.4 Admin Pipeline Endpoints

Create `backend/app/routers/admin_pipeline.py`:

```python
# backend/app/routers/admin_pipeline.py
"""
JWT-protected endpoints for manually triggering pipeline jobs.
Uses existing security.py for auth.
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.security import get_current_user   # existing auth dependency
import asyncio

router = APIRouter(prefix="/admin", dependencies=[Depends(get_current_user)])

@router.post("/pipeline/price/trigger")
async def trigger_price(symbol: str = Body(None, embed=True)):
    from pipeline.price_ingestion import run_daily_price_ingestion, ingest_chunk, _fetch_active_stocks
    if symbol:
        stocks = [s for s in await _fetch_active_stocks() if s["symbol"] == symbol.upper()]
        if not stocks:
            raise HTTPException(404, f"Symbol {symbol} not found")
        asyncio.create_task(ingest_chunk(stocks, period="5d"))
        return {"status": "triggered", "symbol": symbol.upper()}
    else:
        asyncio.create_task(run_daily_price_ingestion())
        return {"status": "triggered", "scope": "all"}

@router.post("/pipeline/fundamentals/trigger")
async def trigger_fundamentals(symbol: str = Body(..., embed=True)):
    from pipeline.fundamental_scraper import run_fundamental_scrape_one
    asyncio.create_task(run_fundamental_scrape_one(symbol.upper()))
    return {"status": "triggered", "symbol": symbol.upper()}

@router.post("/pipeline/ratings/trigger")
async def trigger_ratings():
    from pipeline.rating_engine import run_rating_compute
    asyncio.create_task(run_rating_compute())
    return {"status": "triggered"}

@router.get("/pipeline/audit")
async def get_audit(
    job_name: str = None,
    status:   str = None,
    limit:    int = 50,
    db: AsyncSession = Depends(get_db),
):
    filters = []
    params  = {"limit": limit}
    if job_name:
        filters.append("job_name = :job_name")
        params["job_name"] = job_name
    if status:
        filters.append("status = :status")
        params["status"] = status

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = f"""
        SELECT pa.*, s.symbol
        FROM pipeline_audit pa
        LEFT JOIN stocks s ON s.id = pa.stock_id
        {where}
        ORDER BY started_at DESC LIMIT :limit
    """
    result = await db.execute(text(sql), params)
    return {"records": [dict(r._mapping) for r in result.fetchall()]}
```

Register in `main.py`:

```python
from app.routers import admin_pipeline
app.include_router(admin_pipeline.router, prefix="/api/v1", tags=["Admin"])
```

---

## 6.5 Frontend — Rating Badge & Score Breakdown

Create `frontend/src/components/stocks/RatingBadge.jsx`:

```jsx
// frontend/src/components/stocks/RatingBadge.jsx
const RATING_CONFIG = {
  STRONG_BUY:  { cls: "cal-badge--green",  label: "Strong Buy"  },
  BUY:         { cls: "cal-badge--teal",   label: "Buy"         },
  HOLD:        { cls: "cal-badge--amber",  label: "Hold"        },
  SELL:        { cls: "cal-badge--orange", label: "Sell"        },
  STRONG_SELL: { cls: "cal-badge--red",    label: "Strong Sell" },
};

export default function RatingBadge({ label, size = "md" }) {
  if (!label) return <span className="cal-badge cal-badge--muted">—</span>;
  const config = RATING_CONFIG[label] || { cls: "cal-badge--muted", label };
  return (
    <span className={`cal-badge ${config.cls} cal-badge--${size}`}>
      {config.label}
    </span>
  );
}
```

Add RatingCard to StockDetail Overview tab:

```jsx
// Add to StockDetail.jsx OverviewTab
function RatingCard({ rating }) {
  if (!rating) return null;
  const scores = [
    ["Fundamentals (30%)", rating.fundamental_score],
    ["Valuation (20%)",    rating.valuation_score],
    ["Technicals (20%)",   rating.technical_score],
    ["Momentum (15%)",     rating.momentum_score],
    ["Quality (10%)",      rating.quality_score],
    ["Shareholding (5%)",  rating.shareholding_score],
  ];
  return (
    <div className="cal-rating-card">
      <div className="cal-rating-header">
        <RatingBadge label={rating.rating_label} size="lg" />
        <span className="cal-score">{rating.total_score?.toFixed(1)} / 100</span>
      </div>
      <div className="cal-score-bars">
        {scores.map(([name, score]) => (
          <div key={name} className="cal-score-bar-row">
            <span className="cal-score-bar-label">{name}</span>
            <div className="cal-score-bar-track">
              <div
                className="cal-score-bar-fill"
                style={{ width: `${score || 0}%`,
                         background: score >= 70 ? "#22C55E" : score >= 40 ? "#F59E0B" : "#EF4444" }}
              />
            </div>
            <span className="cal-score-bar-value">{score?.toFixed(0) ?? "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 6.6 Frontend — Dashboard Update

Update `frontend/src/pages/Dashboard.jsx` to include a Market Overview section:

```jsx
// Add to existing Dashboard.jsx (do not remove existing MF sections)

function MarketOverview() {
  const [indices, setIndices] = useState([]);
  const [topGainers, setTopGainers] = useState([]);

  useEffect(() => {
    stockService.getStocks({ is_index: true, limit: 5 })
      .then(d => setIndices(d.results));
    stockService.getStocks({ sort_by: "change_pct", order: "desc", limit: 5 })
      .then(d => setTopGainers(d.results));
  }, []);

  return (
    <section className="cal-section">
      <h2 className="cal-section-heading">Market Overview</h2>

      {/* Index Cards */}
      <div className="cal-index-cards">
        {indices.map(idx => (
          <div key={idx.symbol} className="cal-index-card">
            <span className="cal-index-name">{idx.company_name}</span>
            <span className="cal-index-price">
              {idx.latest_close?.toLocaleString("en-IN")}
            </span>
            <span className={idx.change_pct >= 0 ? "cal-positive" : "cal-negative"}>
              {idx.change_pct > 0 ? "+" : ""}{idx.change_pct?.toFixed(2)}%
            </span>
          </div>
        ))}
      </div>

      {/* Top Gainers */}
      <div className="cal-top-movers">
        <h3 className="cal-subheading">Top Gainers Today</h3>
        {topGainers.map(s => (
          <div key={s.symbol} className="cal-mover-row"
            onClick={() => { window.location.hash = `#/stocks/${s.symbol}` }}>
            <span className="cal-symbol">{s.symbol}</span>
            <span className="cal-positive">+{s.change_pct?.toFixed(2)}%</span>
            <RatingBadge label={s.rating_label} size="sm" />
          </div>
        ))}
      </div>
    </section>
  );
}
```

---

## 6.7 Extend compareSlice for Stocks

Add to `frontend/src/store/slices/compareSlice.js` (additive only):

```javascript
// ADD to initial state:
stockCompareList: [],

// ADD reducers:
addStockToCompare: (state, { payload: symbol }) => {
  if (state.stockCompareList.length >= 5) return;
  if (!state.stockCompareList.includes(symbol))
    state.stockCompareList.push(symbol);
},
removeStockFromCompare: (state, { payload: symbol }) => {
  state.stockCompareList = state.stockCompareList.filter(s => s !== symbol);
},
clearStockCompare: (state) => {
  state.stockCompareList = [];
},
```

---

## 6.8 Validation Checklist

```bash
# 1. Run rating compute manually
python3 -c "
import asyncio
from pipeline.rating_engine import run_rating_compute
asyncio.run(run_rating_compute())
"

# 2. Verify ratings in DB
psql -U user -d nivesh -c "
  SELECT s.symbol, r.total_score, r.rating_label,
         r.fundamental_score, r.technical_score
  FROM stock_ratings r JOIN stocks s ON s.id = r.stock_id
  ORDER BY r.total_score DESC LIMIT 10;
"

# 3. Verify no STRONG_BUY with score < 75
psql -U user -d nivesh -c "
  SELECT COUNT(*) FROM stock_ratings
  WHERE rating_label = 'STRONG_BUY' AND total_score < 75;
"
# Must return 0

# 4. Test API
curl "http://localhost:8000/api/v1/stocks/RELIANCE/rating" | jq '{label: .rating_label, score: .total_score}'
curl "http://localhost:8000/api/v1/stocks/RELIANCE/rating?history=true&limit=5" | jq '.history | length'

# 5. Test screener with rating filter
curl "http://localhost:8000/api/v1/screener?rating_label=BUY&min_roe=15" | jq '.total'

# 6. End-to-end pipeline test for INFY
curl -X POST http://localhost:8000/api/v1/admin/pipeline/fundamentals/trigger \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"symbol":"INFY"}'
# Wait 30s, then:
curl -X POST http://localhost:8000/api/v1/admin/pipeline/ratings/trigger \
  -H "Authorization: Bearer <token>"
curl "http://localhost:8000/api/v1/stocks/INFY/rating" | jq .
```

---

## 6.9 Deliverables for Phase 6

- [ ] `pipeline/rating_engine.py` — all 6 scoring functions implemented
- [ ] Rating compute verified: STRONG_BUY always has score ≥ 75
- [ ] Rating job scheduled (Mon-Fri 20:15 IST)
- [ ] `GET /stocks/{symbol}/rating` returns current rating + breakdown
- [ ] `GET /stocks/{symbol}/rating?history=true` returns rating trend
- [ ] `POST /admin/pipeline/*/trigger` endpoints working (JWT protected)
- [ ] `GET /admin/pipeline/audit` returns pipeline run history
- [ ] `RatingBadge.jsx` with correct colours for all 5 labels
- [ ] `RatingCard.jsx` shows score bars in StockDetail Overview tab
- [ ] Dashboard Market Overview section shows index cards + top gainers
- [ ] `compareSlice.js` extended with stock compare reducers
- [ ] Full end-to-end test: scrape → ratio → technicals → rating for one stock
