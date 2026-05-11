"""ONE JOB: Combine 3 sub-agent signals → overall_health_score (0-100).

Fundamental: 40%, Technical: 30%, Valuation: 30%.
"""
import logging

logger = logging.getLogger(__name__)

# Signal → numeric score mapping
FUNDAMENTAL_SCORES = {"STRONG": 100, "GOOD": 65, "WEAK": 35, "POOR": 10}
TECHNICAL_SCORES = {"BULLISH": 100, "NEUTRAL": 60, "BEARISH": 20}
VALUATION_SCORES = {"UNDERVALUED": 100, "FAIR": 60, "OVERVALUED": 20}

WEIGHTS = {"fundamental": 0.40, "technical": 0.30, "valuation": 0.30}


async def aggregate_node(state: dict) -> dict:
    f_score = FUNDAMENTAL_SCORES.get(state.get("fundamental_signal", "WEAK"), 35)
    t_score = TECHNICAL_SCORES.get(state.get("technical_signal", "NEUTRAL"), 60)
    v_score = VALUATION_SCORES.get(state.get("valuation_signal", "FAIR"), 60)

    overall = round(
        f_score * WEIGHTS["fundamental"]
        + t_score * WEIGHTS["technical"]
        + v_score * WEIGHTS["valuation"],
        2,
    )

    return {
        "overall_health_score": overall,
        "logs": state["logs"] + [
            f"Aggregate: F={f_score}×0.4 + T={t_score}×0.3 + V={v_score}×0.3 = {overall}/100"
        ],
    }
