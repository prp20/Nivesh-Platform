"""ONE JOB: Produce rule-based pre-signal before the LLM refines it.

Inputs:  overall_health_score (0-100) + StockRating.total_score (0-100)
Output: pre_signal (BUY/HOLD/SELL) + pre_confidence (HIGH/MEDIUM/LOW)
"""
import logging

logger = logging.getLogger(__name__)


def _f(v, default: float = 50.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


async def decision_node(state: dict) -> dict:
    analysis = state.get("stock_analysis", {})
    rating = state.get("stock_rating", {})

    health = _f(analysis.get("overall_health_score"), 50.0)
    momentum = _f(rating.get("total_score"), 50.0)
    valuation_signal = analysis.get("valuation_signal", "FAIR")

    combined = health * 0.6 + momentum * 0.4

    if combined >= 70 and valuation_signal != "OVERVALUED":
        signal, confidence = "BUY", "HIGH"
    elif combined >= 55 and valuation_signal == "UNDERVALUED":
        signal, confidence = "BUY", "MEDIUM"
    elif combined >= 50:
        signal, confidence = "HOLD", "MEDIUM"
    elif combined >= 35:
        signal, confidence = "HOLD", "LOW"
    elif combined >= 20:
        signal, confidence = "SELL", "MEDIUM"
    else:
        signal, confidence = "SELL", "HIGH"

    return {
        "pre_signal": signal,
        "pre_confidence": confidence,
        "logs": state["logs"] + [
            f"Decision engine: combined={combined:.1f} → {signal} ({confidence})"
        ],
    }
