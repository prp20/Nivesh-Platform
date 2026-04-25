"""
backend/pipeline/rating_engine.py

Computes composite stock ratings using weighted min-max normalisation.
Strategy mirrors the mutual fund comparison engine in app/analytics.py.

Dimensions:
  - Fundamental  (ROE, ROCE, PAT margin, D/E, interest coverage)
  - Valuation    (PE, PB ratios — lower is better)
  - Technical    (RSI position, MACD histogram, MA alignment)
  - Momentum     (1-day, 5-day, 20-day price change)
  - Shareholding (promoter %, FII trend, no pledging)

Output:
  stock_ratings table — total_score, rating_label, sub-scores per dimension

NOTE: Pattern detection is deferred to a future phase.
      DetectedPattern table is reserved but not populated here.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from pipeline.audit import audit_job
from app.database import raw_connection

logger = logging.getLogger(__name__)


# ─── Metric definitions ───────────────────────────────────────────────────────
# (metric_key, source_table_alias, higher_is_better, dimension)

_FUNDAMENTAL_METRICS = [
    ("roe",            True,  "fundamental"),
    ("roce",           True,  "fundamental"),
    ("pat_margin",     True,  "fundamental"),
    ("ebitda_margin",  True,  "fundamental"),
    ("debt_equity",    False, "fundamental"),   # lower D/E = better
    ("interest_cov",   True,  "fundamental"),
    ("cfo_to_pat",     True,  "fundamental"),
    ("current_ratio",  True,  "fundamental"),
]

_VALUATION_METRICS = [
    ("pe_ratio",  False, "valuation"),   # lower PE = better
    ("pb_ratio",  False, "valuation"),   # lower PB = better
    ("ps_ratio",  False, "valuation"),
]

_TECHNICAL_METRICS = [
    ("rsi_14",    True,  "technical"),   # scored differently — see below
    ("macd_hist", True,  "technical"),
    ("adx_14",    True,  "technical"),   # trend strength
]

_MOMENTUM_METRICS = [
    # computed on-the-fly from price_data
    ("price_chg_1d",  True, "momentum"),
    ("price_chg_5d",  True, "momentum"),
    ("price_chg_20d", True, "momentum"),
]

_SHAREHOLDING_METRICS = [
    ("promoter_pct",  True,  "shareholding"),
    ("pledged_pct",   False, "shareholding"),   # lower pledge = better
    ("fii_pct",       True,  "shareholding"),
]

_DIMENSION_WEIGHTS = {
    "fundamental":  0.35,
    "valuation":    0.20,
    "technical":    0.25,
    "momentum":     0.10,
    "shareholding": 0.10,
}

_RATING_LABELS = [
    (80, "Strong Buy"),
    (60, "Buy"),
    (40, "Neutral"),
    (20, "Sell"),
    (0,  "Strong Sell"),
]


# ─── Main entry points ────────────────────────────────────────────────────────

async def run_rating_compute_all() -> dict:
    """Recompute ratings for all stocks with sufficient data. Called by scheduler."""
    stocks = await _fetch_ratable_stocks()
    async with audit_job("rating_compute_all", records_in=len(stocks)) as audit:
        success, skipped = 0, 0
        for i, stock in enumerate(stocks):
            try:
                await compute_rating_for_stock(stock["id"], stock["symbol"])
                success += 1
            except Exception as e:
                logger.error(f"Rating compute failed for {stock['symbol']}: {e}")
                skipped += 1
            
            # Report progress after each stock
            await audit.update_progress(i + 1)

        audit.records_out = success
        logger.info(f"rating_compute_all: {success} rated, {skipped} skipped")
        return {"rated": success, "skipped": skipped}


async def compute_rating_for_stock(stock_id: int, symbol: str) -> dict:
    """Compute and upsert a composite stock rating for a single stock."""
    ratios = await _get_latest_ratios(stock_id)
    ta     = await _get_latest_ta(stock_id)
    sh     = await _get_latest_shareholding(stock_id)
    mom    = await _get_price_momentum(stock_id)

    # Combine all raw metric values into a flat dict
    raw = {}
    if ratios:
        raw.update({k: ratios.get(k) for k, _, _ in _FUNDAMENTAL_METRICS})
        raw.update({k: ratios.get(k) for k, _, _ in _VALUATION_METRICS})
    if ta:
        raw["rsi_14"]    = ta.get("rsi_14")
        raw["macd_hist"] = ta.get("macd_hist")
        raw["adx_14"]    = ta.get("adx_14")
    if mom:
        raw.update(mom)
    if sh:
        raw["promoter_pct"] = sh.get("promoter_pct")
        raw["pledged_pct"]  = sh.get("pledged_pct")
        raw["fii_pct"]      = sh.get("fii_pct")

    # RSI scoring: 40–60 = neutral; >60 and <80 = bullish; extremes scored lower
    # Transform RSI to a "quality" score: peak at 60, falloff at extremes
    if raw.get("rsi_14") is not None:
        rsi = float(raw["rsi_14"])
        # Score RSI: 50-70 range is best for momentum, penalize overbought/oversold
        raw["rsi_14"] = 100 - abs(rsi - 60)  # transforms to 0-100 range centered at 60

    # Compute sub-scores per dimension using min-max normalization (over peer data)
    # For single stock we can only score against the fixed scale — not peer-relative.
    # We use fixed reference ranges for each metric to produce 0-100 scores.
    sub_scores = {
        "fundamental":  _score_metrics(raw, _FUNDAMENTAL_METRICS),
        "valuation":    _score_metrics(raw, _VALUATION_METRICS),
        "technical":    _score_metrics(raw, _TECHNICAL_METRICS),
        "momentum":     _score_metrics(raw, _MOMENTUM_METRICS),
        "shareholding": _score_metrics(raw, _SHAREHOLDING_METRICS),
    }

    # Weighted composite
    total = sum(
        sub_scores[dim] * weight
        for dim, weight in _DIMENSION_WEIGHTS.items()
        if sub_scores[dim] is not None
    )
    total = round(total, 2)

    # Map to label
    rating_label = "Unrated"
    for threshold, label in _RATING_LABELS:
        if total >= threshold:
            rating_label = label
            break

    rated_on = date.today()
    await _upsert_rating(
        stock_id=stock_id,
        rated_on=rated_on,
        total_score=total,
        rating_label=rating_label,
        fundamental_score=sub_scores["fundamental"],
        valuation_score=sub_scores["valuation"],
        technical_score=sub_scores["technical"],
        momentum_score=sub_scores["momentum"],
        shareholding_score=sub_scores["shareholding"],
        score_breakdown=raw,
    )

    return {
        "symbol":            symbol,
        "total_score":       total,
        "rating_label":      rating_label,
        "fundamental_score": sub_scores["fundamental"],
        "valuation_score":   sub_scores["valuation"],
        "technical_score":   sub_scores["technical"],
        "momentum_score":    sub_scores["momentum"],
        "shareholding_score":sub_scores["shareholding"],
    }


# ─── Scoring engine ───────────────────────────────────────────────────────────

# Fixed reference ranges for single-stock scoring (percentile-like normalization)
# These approximate typical NSE large/mid-cap ranges
_METRIC_RANGES = {
    "roe":            (0,    40),    # 0% to 40%+
    "roce":           (0,    35),
    "pat_margin":     (0,    30),
    "ebitda_margin":  (0,    40),
    "debt_equity":    (0,    3),     # inverted — 0=best, 3=worst
    "interest_cov":   (0,    20),
    "cfo_to_pat":     (0,    2),
    "current_ratio":  (0,    3),
    "pe_ratio":       (5,    60),    # inverted — 5=best(cheap), 60=worst(expensive)
    "pb_ratio":       (0.5,  8),     # inverted
    "ps_ratio":       (0,    10),    # inverted
    "rsi_14":         (0,    100),   # already transformed above
    "macd_hist":      (-5,   5),
    "adx_14":         (0,    50),
    "price_chg_1d":   (-5,   5),
    "price_chg_5d":   (-10,  10),
    "price_chg_20d":  (-20,  20),
    "promoter_pct":   (30,   80),
    "pledged_pct":    (0,    30),    # inverted
    "fii_pct":        (0,    30),
}


def _score_metrics(raw: dict, metric_defs: list) -> Optional[float]:
    """
    Score a set of metrics to 0-100 using fixed reference ranges.
    Returns None if no metrics have data.
    """
    scores = []
    for metric_key, higher_is_better, _ in metric_defs:
        val = raw.get(metric_key)
        if val is None:
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue

        lo, hi = _METRIC_RANGES.get(metric_key, (None, None))
        if lo is None or hi is None or hi == lo:
            continue

        # Clamp to range
        val = max(lo, min(hi, val))
        norm = (val - lo) / (hi - lo)      # 0.0 to 1.0

        if not higher_is_better:
            norm = 1.0 - norm               # invert

        scores.append(norm * 100)

    return round(sum(scores) / len(scores), 2) if scores else None


# ─── DB helpers ───────────────────────────────────────────────────────────────

async def _fetch_ratable_stocks() -> list:
    sql = """
        SELECT DISTINCT s.id, s.symbol
        FROM stocks s
        WHERE s.is_active = TRUE AND s.is_index = FALSE
          AND (
            EXISTS (SELECT 1 FROM financial_ratios fr WHERE fr.stock_id = s.id)
            OR EXISTS (SELECT 1 FROM technical_indicators ti WHERE ti.stock_id = s.id)
          )
        ORDER BY s.id
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql)
        return [dict(r) for r in rows]


async def _get_latest_ratios(stock_id: int) -> Optional[dict]:
    sql = """
        SELECT pe_ratio, pb_ratio, ps_ratio, roe, roce, roa,
               pat_margin, ebitda_margin, debt_equity, interest_cov,
               current_ratio, cfo_to_pat, dividend_yield, eps
        FROM financial_ratios
        WHERE stock_id = $1 AND period_type = 'annual'
        ORDER BY period_end DESC LIMIT 1
    """
    async with raw_connection() as conn:
        row = await conn.fetchrow(sql, stock_id)
        return dict(row) if row else None


async def _get_latest_ta(stock_id: int) -> Optional[dict]:
    sql = """
        SELECT rsi_14, macd_hist, adx_14, sma_50, sma_200
        FROM technical_indicators
        WHERE stock_id = $1 AND timeframe = '1d'
        ORDER BY ind_date DESC LIMIT 1
    """
    async with raw_connection() as conn:
        row = await conn.fetchrow(sql, stock_id)
        return dict(row) if row else None


async def _get_latest_shareholding(stock_id: int) -> Optional[dict]:
    sql = """
        SELECT promoter_pct, pledged_pct, fii_pct, dii_pct
        FROM shareholding_pattern
        WHERE stock_id = $1
        ORDER BY period_end DESC LIMIT 1
    """
    async with raw_connection() as conn:
        row = await conn.fetchrow(sql, stock_id)
        return dict(row) if row else None


async def _get_price_momentum(stock_id: int) -> dict:
    """Compute 1d, 5d, 20d price change % from price_data."""
    sql = """
        SELECT close, price_date
        FROM price_data
        WHERE stock_id = $1
        ORDER BY price_date DESC
        LIMIT 25
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql, stock_id)

    if not rows:
        return {}

    closes = [float(r["close"]) for r in rows]   # index 0 = latest
    latest = closes[0]

    def pct_chg(n_ago):
        if len(closes) > n_ago and closes[n_ago] != 0:
            return round((latest - closes[n_ago]) / closes[n_ago] * 100, 3)
        return None

    return {
        "price_chg_1d":  pct_chg(1),
        "price_chg_5d":  pct_chg(5),
        "price_chg_20d": pct_chg(20),
    }


async def _upsert_rating(
    stock_id: int, rated_on: date, total_score: float, rating_label: str,
    fundamental_score, valuation_score, technical_score, momentum_score,
    shareholding_score, score_breakdown: dict
):
    import json
    sql = """
        INSERT INTO stock_ratings
            (stock_id, rated_on, total_score, rating_label,
             fundamental_score, valuation_score, technical_score,
             momentum_score, shareholding_score, score_breakdown)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
        ON CONFLICT (stock_id, rated_on) DO UPDATE SET
            total_score        = EXCLUDED.total_score,
            rating_label       = EXCLUDED.rating_label,
            fundamental_score  = EXCLUDED.fundamental_score,
            valuation_score    = EXCLUDED.valuation_score,
            technical_score    = EXCLUDED.technical_score,
            momentum_score     = EXCLUDED.momentum_score,
            shareholding_score = EXCLUDED.shareholding_score,
            score_breakdown    = EXCLUDED.score_breakdown
    """
    async with raw_connection() as conn:
        await conn.execute(
            sql,
            stock_id, rated_on, total_score, rating_label,
            fundamental_score, valuation_score, technical_score,
            momentum_score, shareholding_score,
            json.dumps(to_json_safe(score_breakdown)),
        )

def to_json_safe(obj):
    """Recursively convert Decimals and other non-JSON types to floats/safe types."""
    from decimal import Decimal
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [to_json_safe(v) for v in obj]
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj
