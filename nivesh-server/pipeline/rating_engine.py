"""
pipeline/rating_engine.py — Composite stock rating computation.

Public interface (called by app/routers/pipeline.py):
    run_rating_compute_all()                    — compute ratings for all active stocks
    compute_rating_for_stock(stock_id, symbol)  — single stock, returns score breakdown

Scoring model (0–10 scale, weighted composite):
    Fundamental (30%):  ROE, ROCE, PAT margin, D/E, interest coverage, CFO-to-PAT
    Valuation (20%):    PE (vs sector avg), PB, dividend yield
    Technical (25%):    SMA50 vs SMA200 (golden cross), RSI, MACD histogram, ADX
    Momentum (15%):     % from 52W high, volume ratio, RS vs Nifty
    Shareholding (10%): Promoter %, pledged %, FII trend

Rating labels:
    8.0–10.0  → Strong Buy
    6.5– 7.9  → Buy
    5.0– 6.4  → Hold
    3.0– 4.9  → Sell
    0.0– 2.9  → Strong Sell
"""

import asyncio
import logging
from datetime import date
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Stock, FinancialRatio, TechnicalIndicator, ShareholdingPattern
from app.crud import get_active_stocks, upsert_stock_rating, start_etl_run, finish_etl_run

logger = logging.getLogger(__name__)

_WEIGHTS = {
    "fundamental":  0.30,
    "valuation":    0.20,
    "technical":    0.25,
    "momentum":     0.15,
    "shareholding": 0.10,
}


# ── Public interface ─────────────────────────────────────────────────────────


async def run_rating_compute_all() -> dict:
    """Compute composite ratings for all active non-index stocks."""
    async with AsyncSessionLocal() as db:
        run, created = await start_etl_run(
            db, pipeline_name="stock_ratings", triggered_by="scheduler"
        )
        if not created:
            logger.warning("[stock_ratings] already RUNNING — skipping")
            return {"skipped": True}

        try:
            stocks = await get_active_stocks(db, is_index=False)
            succeeded = 0
            failed = 0
            for stock in stocks:
                try:
                    breakdown = await compute_rating_for_stock(stock.id, stock.symbol, db=db)
                    if breakdown:
                        succeeded += 1
                except Exception as exc:
                    logger.warning(f"[stock_ratings] {stock.symbol} failed — {exc}")
                    failed += 1

            status = "COMPLETED" if failed == 0 else "PARTIAL"
            await finish_etl_run(
                db, run.id, status,
                records_out=succeeded,
                error_msg=f"{failed} stocks failed" if failed else None,
            )
            return {"succeeded": succeeded, "failed": failed}

        except Exception as exc:
            logger.exception("[stock_ratings] pipeline-level failure")
            await finish_etl_run(db, run.id, "FAILED", error_msg=str(exc)[:1000])
            raise


async def compute_rating_for_stock(
    stock_id: int,
    symbol: str,
    db: Optional[AsyncSession] = None,
) -> Optional[dict]:
    """
    Compute composite rating for a single stock.

    Returns a score breakdown dict, or None if insufficient data.
    """
    async def _do(session: AsyncSession) -> Optional[dict]:
        ratio    = await _get_latest_ratio(session, stock_id)
        ta       = await _get_latest_ta(session, stock_id)
        holding  = await _get_latest_shareholding(session, stock_id)

        if ratio is None and ta is None:
            logger.debug(f"[rating] {symbol} — no data, skipping")
            return None

        fundamental_score  = _score_fundamental(ratio)
        valuation_score    = _score_valuation(ratio)
        technical_score    = _score_technical(ta)
        momentum_score     = _score_momentum(ta)
        shareholding_score = _score_shareholding(holding)

        total_score = round(
            fundamental_score  * _WEIGHTS["fundamental"]
            + valuation_score  * _WEIGHTS["valuation"]
            + technical_score  * _WEIGHTS["technical"]
            + momentum_score   * _WEIGHTS["momentum"]
            + shareholding_score * _WEIGHTS["shareholding"],
            3,
        )

        rating_label = _label(total_score)

        breakdown = {
            "stock_id":          stock_id,
            "rated_on":          date.today(),
            "total_score":       total_score,
            "rating_label":      rating_label,
            "fundamental_score": round(fundamental_score, 3),
            "valuation_score":   round(valuation_score, 3),
            "technical_score":   round(technical_score, 3),
            "momentum_score":    round(momentum_score, 3),
            "shareholding_score": round(shareholding_score, 3),
            "score_breakdown": {
                "weights": _WEIGHTS,
            },
        }

        await upsert_stock_rating(session, breakdown)
        return breakdown

    if db is not None:
        return await _do(db)
    async with AsyncSessionLocal() as session:
        return await _do(session)


# ── Data fetchers ─────────────────────────────────────────────────────────────


async def _get_latest_ratio(db: AsyncSession, stock_id: int):
    result = await db.execute(
        select(FinancialRatio)
        .where(FinancialRatio.stock_id == stock_id)
        .order_by(desc(FinancialRatio.period_end))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_latest_ta(db: AsyncSession, stock_id: int):
    result = await db.execute(
        select(TechnicalIndicator)
        .where(TechnicalIndicator.stock_id == stock_id)
        .order_by(desc(TechnicalIndicator.ind_date))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_latest_shareholding(db: AsyncSession, stock_id: int):
    result = await db.execute(
        select(ShareholdingPattern)
        .where(ShareholdingPattern.stock_id == stock_id)
        .order_by(desc(ShareholdingPattern.period_end))
        .limit(1)
    )
    return result.scalar_one_or_none()


# ── Scoring functions (all return float 0–10) ─────────────────────────────────


def _f(val, fallback: float = 0.0) -> float:
    """Safe float conversion with fallback."""
    try:
        return float(val) if val is not None else fallback
    except (TypeError, ValueError):
        return fallback


def _clamp(val: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, val))


def _score_fundamental(ratio) -> float:
    if ratio is None:
        return 5.0  # neutral when no data

    score = 0.0

    # ROE (0–3 pts): >20% = 3, 15–20% = 2, 10–15% = 1.5, else scaled
    roe = _f(ratio.roe)
    if roe >= 20:   score += 3.0
    elif roe >= 15: score += 2.0
    elif roe >= 10: score += 1.5
    elif roe >= 5:  score += 0.75
    # else 0

    # ROCE (0–2 pts): >25% = 2, 15–25% = 1.5, else scaled
    roce = _f(ratio.roce)
    if roce >= 25:   score += 2.0
    elif roce >= 15: score += 1.5
    elif roce >= 10: score += 1.0

    # PAT margin (0–2 pts): >20% = 2, 10–20% = 1.5, 5–10% = 1
    pat = _f(ratio.pat_margin)
    if pat >= 20:   score += 2.0
    elif pat >= 10: score += 1.5
    elif pat >= 5:  score += 1.0

    # Debt / Equity (0–2 pts): <0.5 = 2, 0.5–1 = 1.5, 1–2 = 1, >2 = 0
    de = _f(ratio.debt_equity, fallback=99.0)
    if de < 0.5:   score += 2.0
    elif de < 1.0: score += 1.5
    elif de < 2.0: score += 1.0

    # CFO to PAT (0–1 pt): >1.0 = 1 (good cash conversion)
    cfo = _f(ratio.cfo_to_pat, fallback=0.0)
    if cfo >= 1.0: score += 1.0
    elif cfo >= 0.5: score += 0.5

    return _clamp(score)


def _score_valuation(ratio) -> float:
    if ratio is None:
        return 5.0

    score = 0.0

    # PE ratio (0–4 pts): lower is better in context; <15=4, 15–25=3, 25–40=2, >40=1, N/A=2
    pe = _f(ratio.pe_ratio, fallback=-1.0)
    if pe <= 0:    score += 2.0  # negative / missing — neutral
    elif pe < 15:  score += 4.0
    elif pe < 25:  score += 3.0
    elif pe < 40:  score += 2.0
    else:          score += 1.0

    # PB ratio (0–3 pts): <1=3, 1–3=2, 3–6=1, >6=0
    pb = _f(ratio.pb_ratio, fallback=-1.0)
    if pb <= 0:    score += 1.5
    elif pb < 1:   score += 3.0
    elif pb < 3:   score += 2.0
    elif pb < 6:   score += 1.0

    # Dividend yield (0–3 pts): >3%=3, 1–3%=2, 0–1%=1
    dy = _f(ratio.dividend_yield, fallback=0.0)
    if dy >= 3:   score += 3.0
    elif dy >= 1: score += 2.0
    elif dy > 0:  score += 1.0

    return _clamp(score)


def _score_technical(ta) -> float:
    if ta is None:
        return 5.0

    score = 0.0

    # Golden cross SMA50 > SMA200 (0–3 pts)
    sma50  = _f(ta.sma_50,  fallback=0.0)
    sma200 = _f(ta.sma_200, fallback=0.0)
    if sma50 > 0 and sma200 > 0:
        if sma50 > sma200:  score += 3.0  # bullish
        else:                score += 1.0  # bearish

    # RSI (0–3 pts): 40–70 = healthy trend = 3, >70 overbought = 1, <30 oversold = 1
    rsi = _f(ta.rsi_14, fallback=50.0)
    if 40 <= rsi <= 70:  score += 3.0
    elif 30 <= rsi < 40: score += 2.0
    elif 70 < rsi <= 80: score += 2.0
    else:                 score += 1.0

    # MACD histogram > 0 → bullish (0–2 pts)
    hist = _f(ta.macd_hist, fallback=0.0)
    if hist > 0:   score += 2.0
    elif hist > -0.5: score += 1.0

    # ADX > 25 → strong trend (0–2 pts)
    adx = _f(ta.adx_14, fallback=0.0)
    if adx >= 30:   score += 2.0
    elif adx >= 20: score += 1.5
    elif adx >= 15: score += 1.0

    return _clamp(score)


def _score_momentum(ta) -> float:
    if ta is None:
        return 5.0

    score = 0.0

    # % from 52W high (0–4 pts): closer to 52W high is bullish
    pct_high = _f(ta.pct_from_52w_high, fallback=-50.0)
    if pct_high >= -5:    score += 4.0  # within 5% of 52W high
    elif pct_high >= -15: score += 3.0
    elif pct_high >= -30: score += 2.0
    elif pct_high >= -50: score += 1.0

    # Volume ratio (0–3 pts): high volume = strong momentum confirmation
    vr = _f(ta.volume_ratio, fallback=1.0)
    if vr >= 2.0:   score += 3.0
    elif vr >= 1.5: score += 2.0
    elif vr >= 1.0: score += 1.5
    elif vr >= 0.7: score += 1.0

    # RS vs Nifty 6M (0–3 pts): positive RS = outperforming
    rs = _f(ta.rs_6m_vs_nifty, fallback=0.0)
    if rs >= 20:    score += 3.0
    elif rs >= 10:  score += 2.5
    elif rs >= 0:   score += 2.0
    elif rs >= -10: score += 1.0

    return _clamp(score)


def _score_shareholding(holding) -> float:
    if holding is None:
        return 5.0

    score = 0.0

    # Promoter % (0–4 pts): >60%=4, 50–60%=3, 35–50%=2, <35%=1
    promo = _f(holding.promoter_pct, fallback=0.0)
    if promo >= 60:   score += 4.0
    elif promo >= 50: score += 3.0
    elif promo >= 35: score += 2.0
    else:             score += 1.0

    # Pledged shares (0–3 pts): 0%=3, <5%=2, <20%=1, else 0
    pledged = _f(holding.pledged_pct, fallback=0.0)
    if pledged == 0:    score += 3.0
    elif pledged < 5:   score += 2.0
    elif pledged < 20:  score += 1.0

    # FII trend (0–3 pts): positive FII change = bullish
    fii_chg = _f(holding.fii_change, fallback=0.0)
    if fii_chg >= 2:    score += 3.0
    elif fii_chg >= 0:  score += 2.0
    elif fii_chg >= -2: score += 1.0

    return _clamp(score)


def _label(score: float) -> str:
    if score >= 8.0:  return "Strong Buy"
    if score >= 6.5:  return "Buy"
    if score >= 5.0:  return "Hold"
    if score >= 3.0:  return "Sell"
    return "Strong Sell"
