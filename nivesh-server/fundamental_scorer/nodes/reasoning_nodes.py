"""
fundamental_scorer/nodes/reasoning_nodes.py — AI qualitative reasoning node.

Functions:
    generate_reasoning_node(state_dict) → dict   (async — calls Groq LLM)

Uses langchain-groq to generate a brief qualitative verdict and label
based on the computed numeric scores in state_dict.

Environment variables required:
    GROQ_API_KEY  — Groq API key

Returns dict with:
    reasoning_label: str  — one of: Exceptional, Strong, Moderate, Weak, Poor
    reasoning_text:  str  — 2–3 sentence qualitative summary
    status: str           — REASONED | FAILED
"""

import asyncio
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

_LABEL_MAP = {
    (8.0, 10.0): "Exceptional",
    (6.5,  8.0): "Strong",
    (5.0,  6.5): "Moderate",
    (3.0,  5.0): "Weak",
    (0.0,  3.0): "Poor",
}


async def generate_reasoning_node(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate qualitative AI reasoning using Groq LLM.

    Falls back to a deterministic label + templated text if the LLM call
    fails or GROQ_API_KEY is not set.
    """
    composite = state_dict.get("composite_score", 0.0)
    label = _score_to_label(composite)

    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        logger.info("[reasoning] GROQ_API_KEY not set — using template fallback")
        return {
            "reasoning_label": label,
            "reasoning_text":  _template_reasoning(state_dict, label),
            "status": "REASONED",
        }

    try:
        reasoning_text = await asyncio.to_thread(
            _call_groq, groq_key, state_dict, label
        )
        return {
            "reasoning_label": label,
            "reasoning_text":  reasoning_text,
            "status": "REASONED",
        }
    except Exception as exc:
        logger.warning(f"[reasoning] Groq call failed — falling back to template: {exc}")
        return {
            "reasoning_label": label,
            "reasoning_text":  _template_reasoning(state_dict, label),
            "status": "REASONED",
        }


def _score_to_label(score: float) -> str:
    for (lo, hi), label in _LABEL_MAP.items():
        if lo <= score < hi:
            return label
    return "Poor"


def _template_reasoning(state_dict: Dict[str, Any], label: str) -> str:
    """Deterministic template-based reasoning when LLM is unavailable."""
    sym = state_dict.get("symbol", "This company")
    pl  = state_dict.get("pl_results") or {}
    bs  = state_dict.get("bs_results") or {}
    cf  = state_dict.get("cf_results") or {}

    composite = state_dict.get("composite_score", 0.0)
    revenue_cagr = pl.get("revenue_cagr")
    pat_margin   = pl.get("pat_margin_latest")
    latest_de    = bs.get("latest_de")
    avg_cfo_pat  = cf.get("avg_cfo_to_pat")

    parts = [f"{sym} shows {label.lower()} fundamentals with a composite score of {composite:.1f}/10."]

    if revenue_cagr is not None:
        direction = "growing" if revenue_cagr > 10 else ("declining" if revenue_cagr < 0 else "stable")
        parts.append(f"Revenue is {direction} at a {revenue_cagr:.1f}% CAGR.")

    if pat_margin is not None:
        quality = "strong" if pat_margin > 15 else ("moderate" if pat_margin > 8 else "thin")
        parts.append(f"PAT margin is {quality} at {pat_margin:.1f}%.")

    if latest_de is not None:
        leverage = "low-debt" if latest_de < 0.5 else ("moderately leveraged" if latest_de < 1.5 else "highly leveraged")
        parts.append(f"The balance sheet is {leverage} (D/E = {latest_de:.2f}x).")

    if avg_cfo_pat is not None and avg_cfo_pat > 0:
        quality = "high-quality" if avg_cfo_pat > 1.0 else "adequate"
        parts.append(f"Cash conversion is {quality} (CFO/PAT = {avg_cfo_pat:.2f}x).")

    return " ".join(parts)


def _call_groq(api_key: str, state_dict: Dict[str, Any], label: str) -> str:
    """Blocking Groq LLM call — run inside asyncio.to_thread()."""
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage, SystemMessage

    pl = state_dict.get("pl_results") or {}
    bs = state_dict.get("bs_results") or {}
    cf = state_dict.get("cf_results") or {}

    prompt = f"""You are a quantitative fundamental analyst. Provide a concise 2-3 sentence
qualitative assessment of a company based on these financial metrics:

Company: {state_dict.get("symbol")}
Composite Score: {state_dict.get("composite_score", 0):.1f}/10 ({label})

P&L: Revenue CAGR={pl.get("revenue_cagr")}% | PAT margin={pl.get("pat_margin_latest")}% | EPS CAGR={pl.get("eps_cagr")}%
BS:  D/E={bs.get("latest_de")} | Networth CAGR={bs.get("networth_cagr")}%
CF:  CFO/PAT={cf.get("avg_cfo_to_pat")} | FCF positive {cf.get("pct_positive_fcf", 0)*100:.0f}% of years

Write 2-3 sentences summarizing the investment quality. Be objective and factual.
Do not include a rating label — just the qualitative text."""

    llm = ChatGroq(
        groq_api_key=api_key,
        model_name="llama3-8b-8192",
        temperature=0.3,
        max_tokens=200,
    )

    messages = [
        SystemMessage(content="You are a concise financial analyst. Write 2-3 factual sentences only."),
        HumanMessage(content=prompt),
    ]

    response = llm.invoke(messages)
    return response.content.strip()
