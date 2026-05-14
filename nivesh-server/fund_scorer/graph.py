"""
fund_scorer/graph.py — LangGraph orchestration for fund quality scoring.

Public interface:
    run_fund_scorer(scheme_code, db) → dict

Pipeline stages:
    1. Fetch fund metrics from DB (FundMaster + FundMetrics)
    2. Compute a quantitative quality score (0–10)
    3. Generate qualitative verdict via Groq LLM (with fallback)

Returns a dict with:
    scheme_code: str
    fund_name: str
    quality_score: float (0–10)
    rating_label: str (Excellent / Good / Average / Below Average / Poor)
    reasoning_text: str
    status: str (COMPLETED | FAILED)
    breakdown: dict
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FundMaster, FundMetrics

logger = logging.getLogger(__name__)

_LABEL_MAP = [
    (8.0, "Excellent"),
    (6.5, "Good"),
    (5.0, "Average"),
    (3.0, "Below Average"),
    (0.0, "Poor"),
]


async def run_fund_scorer(scheme_code: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Run the full fund scoring pipeline for a single scheme.

    Returns a state dict with quality_score, rating_label, reasoning_text.
    """
    # ── Fetch ────────────────────────────────────────────────────────────────
    fund_result = await db.execute(
        select(FundMaster).where(FundMaster.scheme_code == scheme_code)
    )
    fund = fund_result.scalar_one_or_none()
    if fund is None:
        return {"status": "FAILED", "error": f"Fund not found: {scheme_code}"}

    metrics_result = await db.execute(
        select(FundMetrics).where(FundMetrics.scheme_code == scheme_code)
    )
    metrics = metrics_result.scalar_one_or_none()

    # ── Compute score ────────────────────────────────────────────────────────
    breakdown = _compute_fund_score(metrics)
    quality_score = breakdown["total_score"]
    rating_label  = _score_to_label(quality_score)

    # ── Generate reasoning ───────────────────────────────────────────────────
    reasoning_text = await _generate_reasoning(fund, metrics, breakdown, rating_label)

    return {
        "scheme_code":   scheme_code,
        "fund_name":     fund.scheme_name,
        "quality_score": quality_score,
        "rating_label":  rating_label,
        "reasoning_text": reasoning_text,
        "breakdown":     breakdown,
        "status":        "COMPLETED",
    }


def _compute_fund_score(metrics) -> Dict[str, Any]:
    """Compute quantitative fund quality score from FundMetrics row."""

    def _f(val, fallback=None) -> Optional[float]:
        try:
            return float(val) if val is not None else fallback
        except (TypeError, ValueError):
            return fallback

    score = 0.0

    # Returns-based scoring (0–4 pts)
    cagr_3y = _f(metrics.cagr_3y if metrics else None)
    cagr_5y = _f(metrics.cagr_5y if metrics else None)

    if cagr_3y is not None:
        if cagr_3y >= 18:   score += 2.0
        elif cagr_3y >= 12: score += 1.5
        elif cagr_3y >= 8:  score += 1.0
        elif cagr_3y >= 0:  score += 0.5

    if cagr_5y is not None:
        if cagr_5y >= 15:   score += 2.0
        elif cagr_5y >= 10: score += 1.5
        elif cagr_5y >= 6:  score += 1.0
        elif cagr_5y >= 0:  score += 0.5

    # Risk-adjusted metrics (0–3 pts)
    sharpe   = _f(metrics.sharpe_ratio if metrics else None)
    sortino  = _f(metrics.sortino_ratio if metrics else None)
    max_dd   = _f(metrics.max_drawdown if metrics else None)

    if sharpe is not None:
        if sharpe >= 1.5:   score += 1.5
        elif sharpe >= 1.0: score += 1.0
        elif sharpe >= 0.5: score += 0.5

    if max_dd is not None:
        abs_dd = abs(max_dd)
        if abs_dd < 15:    score += 1.0
        elif abs_dd < 25:  score += 0.7
        elif abs_dd < 40:  score += 0.4

    # Alpha vs benchmark (0–3 pts)
    alpha = _f(metrics.alpha if metrics else None)
    if alpha is not None:
        if alpha >= 5:    score += 3.0
        elif alpha >= 2:  score += 2.0
        elif alpha >= 0:  score += 1.5
        else:             score += 0.5

    total = min(10.0, round(score, 3))

    return {
        "total_score": total,
        "cagr_3y":     cagr_3y,
        "cagr_5y":     cagr_5y,
        "sharpe":      sharpe,
        "sortino":     sortino,
        "max_dd":      max_dd,
        "alpha":       alpha,
    }


async def _generate_reasoning(fund, metrics, breakdown: Dict, label: str) -> str:
    """Generate qualitative verdict — Groq LLM with template fallback."""
    groq_key = os.environ.get("GROQ_API_KEY")

    if not groq_key or metrics is None:
        return _template_reasoning(fund, breakdown, label)

    try:
        return await asyncio.to_thread(_call_groq, groq_key, fund, breakdown, label)
    except Exception as exc:
        logger.warning(f"[fund_scorer] Groq call failed — using template: {exc}")
        return _template_reasoning(fund, breakdown, label)


def _template_reasoning(fund, breakdown: Dict, label: str) -> str:
    name = fund.scheme_name if fund else "This fund"
    score = breakdown.get("total_score", 0)
    cagr3 = breakdown.get("cagr_3y")
    alpha = breakdown.get("alpha")
    dd    = breakdown.get("max_dd")

    parts = [f"{name} is rated {label} with a quality score of {score:.1f}/10."]
    if cagr3 is not None:
        parts.append(f"3-year CAGR is {cagr3:.1f}%.")
    if alpha is not None:
        direction = "outperforming" if alpha >= 0 else "underperforming"
        parts.append(f"The fund is {direction} its benchmark by {abs(alpha):.1f}% (alpha).")
    if dd is not None:
        parts.append(f"Maximum drawdown is {abs(dd):.1f}%.")
    return " ".join(parts)


def _call_groq(api_key: str, fund, breakdown: Dict, label: str) -> str:
    """Blocking Groq LLM call for fund reasoning."""
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage, SystemMessage

    prompt = f"""You are a mutual fund analyst. Write 2-3 sentences summarizing this fund's quality.

Fund: {fund.scheme_name}
Category: {fund.scheme_category}
Rating: {label} ({breakdown.get("total_score", 0):.1f}/10)
3Y CAGR: {breakdown.get("cagr_3y")}%
5Y CAGR: {breakdown.get("cagr_5y")}%
Sharpe: {breakdown.get("sharpe")}
Alpha: {breakdown.get("alpha")}%
Max Drawdown: {breakdown.get("max_dd")}%

Write 2-3 factual sentences only."""

    llm = ChatGroq(
        groq_api_key=api_key,
        model_name="llama3-8b-8192",
        temperature=0.3,
        max_tokens=150,
    )

    response = llm.invoke([
        SystemMessage(content="You are a concise mutual fund analyst."),
        HumanMessage(content=prompt),
    ])
    return response.content.strip()


def _score_to_label(score: float) -> str:
    for threshold, label in _LABEL_MAP:
        if score >= threshold:
            return label
    return "Poor"
