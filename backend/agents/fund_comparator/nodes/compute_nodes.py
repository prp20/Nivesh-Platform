"""Compute nodes — build metrics matrix and rank funds."""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Columns to include in the comparison matrix
COMPARISON_METRICS = [
    "cagr_3year", "cagr_5year", "sharpe_ratio", "sortino_ratio",
    "alpha", "beta", "maximum_drawdown", "tracking_error",
    "information_ratio", "upside_capture", "downside_capture", "expense_ratio",
]

# Metric weight for overall ranking (must sum to 1.0)
# True if higher value is better, False if lower is better
METRIC_DIRECTION: dict[str, bool] = {
    "cagr_3year": True,
    "cagr_5year": True,
    "sharpe_ratio": True,
    "sortino_ratio": True,
    "alpha": True,
    "beta": False,           # lower beta = less market risk (context-dependent, but generally penalise high)
    "maximum_drawdown": False,  # less negative = better
    "tracking_error": False,
    "information_ratio": True,
    "upside_capture": True,
    "downside_capture": False,
    "expense_ratio": False,
}

METRIC_WEIGHTS: dict[str, float] = {
    "cagr_3year": 0.20,
    "cagr_5year": 0.10,
    "sharpe_ratio": 0.20,
    "sortino_ratio": 0.10,
    "alpha": 0.15,
    "beta": 0.00,           # not included in weighted score
    "maximum_drawdown": 0.10,
    "tracking_error": 0.00,
    "information_ratio": 0.05,
    "upside_capture": 0.05,
    "downside_capture": 0.05,
    "expense_ratio": 0.10,
}


def _safe_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


async def build_metrics_matrix(state: dict) -> dict:
    """Extract the 12 comparison metrics for each fund."""
    matrix: dict[str, dict] = {}
    for code, data in state["funds_data"].items():
        m = data["metrics"]
        matrix[code] = {metric: _safe_float(m.get(metric)) for metric in COMPARISON_METRICS}
    return {
        "metrics_matrix": matrix,
        "logs": state["logs"] + ["Metrics matrix built"],
    }


async def rank_funds(state: dict) -> dict:
    """Rank 1-N per metric (1=best). Compute overall weighted rank score."""
    matrix = state["metrics_matrix"]
    codes = list(matrix.keys())
    n = len(codes)
    rankings: dict[str, dict] = {c: {} for c in codes}

    for metric in COMPARISON_METRICS:
        # Only rank codes that have a non-None value for this metric
        has_value = [(c, matrix[c][metric]) for c in codes if matrix[c][metric] is not None]
        higher_better = METRIC_DIRECTION.get(metric, True)
        sorted_codes = sorted(has_value, key=lambda x: x[1], reverse=higher_better)
        for rank_pos, (code, _) in enumerate(sorted_codes, start=1):
            rankings[code][metric] = rank_pos
        # Assign worst rank to codes with None
        for code, val in [(c, matrix[c][metric]) for c in codes if matrix[c][metric] is None]:
            rankings[code][metric] = n + 1

    # Overall weighted score: lower = better rank
    for code in codes:
        weighted_score = 0.0
        for metric, weight in METRIC_WEIGHTS.items():
            if weight > 0:
                rank = rankings[code].get(metric, n + 1)
                weighted_score += rank * weight
        rankings[code]["_weighted_score"] = round(weighted_score, 4)

    # Overall rank: lowest weighted_score = rank 1
    sorted_overall = sorted(codes, key=lambda c: rankings[c]["_weighted_score"])
    for rank_pos, code in enumerate(sorted_overall, start=1):
        rankings[code]["overall_rank"] = rank_pos

    winner = sorted_overall[0]
    return {
        "rankings": rankings,
        "winner_code": winner,
        "logs": state["logs"] + [f"Funds ranked. Winner: {winner}"],
    }
