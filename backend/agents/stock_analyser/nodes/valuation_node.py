"""ONE JOB: Produce UNDERVALUED / FAIR / OVERVALUED signal.

Compares PE, PB, PS, EV/EBITDA vs sector medians.
No LLM call, no DB call (data already in state).
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _f(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


UNDERVALUED_THRESH = 0.85   # stock value < 85% of median → undervalued
OVERVALUED_THRESH = 1.30    # stock value > 130% of median → overvalued

METRIC_MAP = [
    ("pe_ratio", "median_pe", "PE ratio"),
    ("pb_ratio", "median_pb", "P/B ratio"),
    ("ps_ratio", "median_ps", "P/S ratio"),
    ("ev_ebitda", "median_ev_ebitda", "EV/EBITDA"),
]


async def valuation_node(state: dict) -> dict:
    ratios = state.get("financial_ratios", {})
    medians = state.get("sector_medians", {})

    comparisons = []
    under_count = 0
    over_count = 0

    for ratio_key, median_key, label in METRIC_MAP:
        stock_val = _f(ratios.get(ratio_key))
        median_val = _f(medians.get(median_key))

        if stock_val is None or median_val is None or median_val == 0:
            comparisons.append(f"{label}: N/A (no sector median)")
            continue

        rel = stock_val / median_val
        if rel < UNDERVALUED_THRESH:
            comparisons.append(f"{label} {stock_val:.1f} vs median {median_val:.1f} (CHEAP)")
            under_count += 1
        elif rel > OVERVALUED_THRESH:
            comparisons.append(f"{label} {stock_val:.1f} vs median {median_val:.1f} (EXPENSIVE)")
            over_count += 1
        else:
            comparisons.append(f"{label} {stock_val:.1f} vs median {median_val:.1f} (FAIR)")

    total_compared = under_count + over_count + (
        sum(1 for c in comparisons if "FAIR" in c)
    )

    if total_compared == 0:
        signal = "FAIR"
        reason = "Insufficient sector data for valuation comparison."
    elif under_count > over_count and under_count >= 2:
        signal = "UNDERVALUED"
        reason = f"Stock trades below sector median on {under_count} of {total_compared} valuation metrics. " + "; ".join(comparisons)
    elif over_count > under_count and over_count >= 2:
        signal = "OVERVALUED"
        reason = f"Stock trades above sector median on {over_count} of {total_compared} valuation metrics. " + "; ".join(comparisons)
    else:
        signal = "FAIR"
        reason = "Stock is fairly valued relative to sector peers. " + "; ".join(comparisons)

    return {
        "valuation_signal": signal,
        "valuation_reasoning": reason,
        "logs": state["logs"] + [f"Valuation agent: {signal} ({under_count}U/{over_count}O)"],
    }
