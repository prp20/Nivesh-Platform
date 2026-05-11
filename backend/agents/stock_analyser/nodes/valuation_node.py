"""ONE JOB: Produce UNDERVALUED / FAIR / OVERVALUED signal.

Primary:  compares PE, PB, PS, EV/EBITDA vs sector medians.
Fallback: when sector peers have no data, uses absolute benchmark ranges.
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

# Absolute fallback ranges (Indian large-cap benchmarks)
# (metric_key, label, cheap_threshold, expensive_threshold)
ABSOLUTE_BENCHMARKS = [
    ("pe_ratio",  "PE ratio",   15.0, 30.0),
    ("pb_ratio",  "P/B ratio",   1.5,  4.0),
    ("ps_ratio",  "P/S ratio",   1.0,  5.0),
    ("ev_ebitda", "EV/EBITDA",   8.0, 20.0),
]


def _absolute_signal(ratios: dict) -> tuple[str, str]:
    """Fallback: compare stock ratios against absolute benchmark thresholds."""
    comparisons = []
    cheap = 0
    expensive = 0

    for key, label, lo, hi in ABSOLUTE_BENCHMARKS:
        val = _f(ratios.get(key))
        if val is None or val <= 0:
            continue
        if val < lo:
            comparisons.append(f"{label} {val:.1f} (below {lo:.0f} — cheap)")
            cheap += 1
        elif val > hi:
            comparisons.append(f"{label} {val:.1f} (above {hi:.0f} — expensive)")
            expensive += 1
        else:
            comparisons.append(f"{label} {val:.1f} (within {lo:.0f}–{hi:.0f} range)")

    if not comparisons:
        return "FAIR", "No valuation ratios available to assess against benchmarks."

    note = "No sector peer data available; assessed against absolute benchmark ranges. "
    if cheap > expensive and cheap >= 2:
        return "UNDERVALUED", note + "; ".join(comparisons)
    elif expensive > cheap and expensive >= 2:
        return "OVERVALUED", note + "; ".join(comparisons)
    else:
        return "FAIR", note + "; ".join(comparisons)


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

    total_compared = under_count + over_count + sum(1 for c in comparisons if "FAIR" in c)

    if total_compared == 0:
        # No sector peer data — fall back to absolute benchmarks
        signal, reason = _absolute_signal(ratios)
    elif under_count > over_count and under_count >= 2:
        signal = "UNDERVALUED"
        reason = f"Trades below sector median on {under_count} of {total_compared} metrics. " + "; ".join(comparisons)
    elif over_count > under_count and over_count >= 2:
        signal = "OVERVALUED"
        reason = f"Trades above sector median on {over_count} of {total_compared} metrics. " + "; ".join(comparisons)
    else:
        signal = "FAIR"
        reason = "Fairly valued relative to sector peers. " + "; ".join(comparisons)

    return {
        "valuation_signal": signal,
        "valuation_reasoning": reason,
        "logs": state["logs"] + [f"Valuation agent: {signal} ({under_count}U/{over_count}O, fallback={total_compared==0})"],
    }
