"""Compute nodes — pure Python, no LLM, no DB calls."""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Weights for the composite score (must sum to 1.0)
_WEIGHTS = {
    "sharpe_ratio": 0.30,
    "alpha": 0.25,
    "cagr_3year": 0.25,
    "sortino_ratio": 0.10,
    "expense_ratio_inv": 0.10,  # lower expense is better
}

# Reasonable "good" ceilings for normalization
_CEILINGS = {
    "sharpe_ratio": 2.0,
    "alpha": 0.15,
    "cagr_3year": 0.20,
    "sortino_ratio": 2.5,
    "expense_ratio_inv": 0.03,  # 3% upper bound for expense
}


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _composite(metrics: dict) -> float:
    sharpe = _to_float(metrics.get("sharpe_ratio"))
    alpha = _to_float(metrics.get("alpha"))
    cagr = _to_float(metrics.get("cagr_3year"))
    sortino = _to_float(metrics.get("sortino_ratio"))
    expense = _to_float(metrics.get("expense_ratio"), default=0.02)

    s_score = _clamp(sharpe / _CEILINGS["sharpe_ratio"] * 100)
    a_score = _clamp(alpha / _CEILINGS["alpha"] * 100)
    c_score = _clamp(cagr / _CEILINGS["cagr_3year"] * 100)
    so_score = _clamp(sortino / _CEILINGS["sortino_ratio"] * 100)
    # Lower expense is better: invert
    e_score = _clamp((1 - expense / _CEILINGS["expense_ratio_inv"]) * 100)

    return round(
        s_score * _WEIGHTS["sharpe_ratio"]
        + a_score * _WEIGHTS["alpha"]
        + c_score * _WEIGHTS["cagr_3year"]
        + so_score * _WEIGHTS["sortino_ratio"]
        + e_score * _WEIGHTS["expense_ratio_inv"],
        2,
    )


async def rank_among_peers(state: dict) -> dict:
    """Compute composite score and peer percentile rank — pure Python."""
    metrics = state["fund_metrics"]
    peers = state.get("peer_metrics", [])

    my_score = _composite(metrics)
    peer_scores = [_composite(p) for p in peers]

    if peer_scores:
        worse_than = sum(1 for ps in peer_scores if ps < my_score)
        percentile = round(worse_than / len(peer_scores) * 100, 1)
        # Rank: 1 = best
        all_scores = sorted(peer_scores + [my_score], reverse=True)
        rank = all_scores.index(my_score) + 1
    else:
        percentile = 50.0
        rank = 1

    return {
        "composite_score": my_score,
        "peer_percentile": percentile,
        "category_rank": rank,
        "category_size": len(peers) + 1,
        "status": "RANKED",
        "logs": state["logs"] + [
            f"Composite score: {my_score}/100, percentile: {percentile}, rank: {rank}/{len(peers)+1}"
        ],
    }
