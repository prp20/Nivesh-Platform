"""
fundamental_scorer/nodes/compute_nodes.py — Deterministic scoring node.

Functions:
    compute_scores_node(state_dict) → dict   (synchronous — pure computation)

Scoring logic:
    Each statement type (PL, BS, CF) is scored 0–10 based on key metrics.
    Composite score = weighted average of the three statement scores.

    PL (Profit & Loss):
        - Revenue growth (5-year CAGR)
        - PAT margin trend
        - EPS growth
        - Consistency (years with positive PAT / total years)

    BS (Balance Sheet):
        - Debt / Equity trend
        - Current ratio / liquidity
        - Asset quality (net block growth)
        - Networth growth

    CF (Cash Flow):
        - CFO / PAT ratio (cash conversion quality)
        - FCF generation (CFO - Capex)
        - Capex intensity (growth investment)
        - Financing cash flow (debt repayment vs new borrowing)
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PL_WEIGHT  = 0.40
_BS_WEIGHT  = 0.35
_CF_WEIGHT  = 0.25


def compute_scores_node(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute deterministic scores from financial statements in state_dict.

    Returns dict with keys: pl_results, bs_results, cf_results, composite_score, status, logs.
    """
    try:
        stmts = state_dict.get("statements_data", {})
        pl_rows = stmts.get("PL", [])
        bs_rows = stmts.get("BS", [])
        cf_rows = stmts.get("CF", [])

        if not pl_rows:
            return {
                "status": "FAILED",
                "error": "Insufficient history — no PL data",
                "composite_score": 0.0,
            }

        pl_results = _score_pl(pl_rows)
        bs_results = _score_bs(bs_rows)
        cf_results = _score_cf(cf_rows)

        composite = round(
            pl_results["pl_score"] * _PL_WEIGHT
            + bs_results["bs_score"] * _BS_WEIGHT
            + cf_results["cf_score"] * _CF_WEIGHT,
            3,
        )

        return {
            "pl_results":      pl_results,
            "bs_results":      bs_results,
            "cf_results":      cf_results,
            "composite_score": composite,
            "status":          "COMPUTED",
            "logs":            state_dict.get("logs", []) + [
                f"PL={pl_results['pl_score']:.2f} "
                f"BS={bs_results['bs_score']:.2f} "
                f"CF={cf_results['cf_score']:.2f} "
                f"Composite={composite:.2f}"
            ],
        }

    except Exception as exc:
        logger.exception("[compute_scores] failed")
        return {"status": "FAILED", "error": str(exc)[:500], "composite_score": 0.0}


# ── PL scoring ────────────────────────────────────────────────────────────────


def _score_pl(rows: List[Dict]) -> Dict[str, Any]:
    revenues  = _extract_series(rows, "Revenue", "Sales", "Net Sales")
    profits   = _extract_series(rows, "Net Profit", "PAT")
    eps_vals  = _extract_series(rows, "EPS", "EPS in Rs")

    revenue_cagr = _cagr(revenues, years=5)
    eps_growth   = _cagr(eps_vals, years=5)
    pat_margin   = _latest_ratio(profits, revenues)
    consistency  = _consistency(profits)

    # Score each sub-component 0–10
    growth_score = _score_cagr(revenue_cagr)
    margin_score = _score_margin(pat_margin)
    eps_score    = _score_cagr(eps_growth)
    cons_score   = round(consistency * 10, 2)

    pl_score = round(
        growth_score * 0.30
        + margin_score * 0.30
        + eps_score * 0.25
        + cons_score * 0.15,
        3,
    )

    return {
        "pl_score":          _clamp(pl_score),
        "growth_score":      _clamp(growth_score),
        "margin_score":      _clamp(margin_score),
        "eps_score":         _clamp(eps_score),
        "consistency_score": _clamp(cons_score),
        "revenue_cagr":      revenue_cagr,
        "pat_margin_latest": pat_margin,
        "eps_cagr":          eps_growth,
        "profitability_consistency": consistency,
    }


# ── BS scoring ────────────────────────────────────────────────────────────────


def _score_bs(rows: List[Dict]) -> Dict[str, Any]:
    debts    = _extract_series(rows, "Total Debt", "Borrowings")
    equities = _extract_series(rows, "Total Equity", "Shareholders Equity", "Equity Capital")
    assets   = _extract_series(rows, "Total Assets", "Balance Sheet Size")

    # Debt / Equity: lower is better
    de_series = [_safe_div(d, e) for d, e in zip(debts, equities) if d is not None and e and e > 0]
    latest_de = de_series[-1] if de_series else None
    de_trend  = _trend(de_series)

    # Networth growth
    nw_growth = _cagr(equities, years=5)

    # Current ratio — not always available, use equity/debt proxy
    leverage_score = _score_de(latest_de)
    liquidity_score = 5.0  # placeholder — need current/quick ratio data
    asset_score    = _score_cagr(_cagr(assets, years=5))
    networth_score = _score_cagr(nw_growth)

    bs_score = round(
        leverage_score * 0.35
        + liquidity_score * 0.20
        + asset_score * 0.25
        + networth_score * 0.20,
        3,
    )

    return {
        "bs_score":        _clamp(bs_score),
        "leverage_score":  _clamp(leverage_score),
        "liquidity_score": _clamp(liquidity_score),
        "asset_score":     _clamp(asset_score),
        "networth_score":  _clamp(networth_score),
        "latest_de":       latest_de,
        "de_trend":        de_trend,
        "networth_cagr":   nw_growth,
    }


# ── CF scoring ────────────────────────────────────────────────────────────────


def _score_cf(rows: List[Dict]) -> Dict[str, Any]:
    cfos    = _extract_series(rows, "Cash from Operations", "Operating Cash Flow")
    profits = _extract_series(rows, "Net Profit", "PAT")
    capexes = _extract_series(rows, "Capex", "Capital Expenditure")

    # CFO / PAT
    cfo_pat_ratios = [
        _safe_div(c, p)
        for c, p in zip(cfos, profits)
        if c is not None and p and p != 0
    ]
    avg_cfo_pat = sum(cfo_pat_ratios) / len(cfo_pat_ratios) if cfo_pat_ratios else None

    # FCF = CFO - Capex
    fcf_list = [c - abs(x) for c, x in zip(cfos, capexes) if c is not None and x is not None]
    pct_positive_fcf = sum(1 for f in fcf_list if f > 0) / len(fcf_list) if fcf_list else 0.5

    operating_score  = _score_cfo_pat(avg_cfo_pat)
    capex_score      = round(pct_positive_fcf * 10, 2)  # % years with positive FCF
    financing_score  = 5.0  # placeholder — financing CF direction
    cf_score = round(
        operating_score * 0.50
        + capex_score * 0.35
        + financing_score * 0.15,
        3,
    )

    return {
        "cf_score":        _clamp(cf_score),
        "operating_score": _clamp(operating_score),
        "capex_score":     _clamp(capex_score),
        "financing_score": _clamp(financing_score),
        "avg_cfo_to_pat":  avg_cfo_pat,
        "pct_positive_fcf": pct_positive_fcf,
    }


# ── Utility helpers ───────────────────────────────────────────────────────────


def _extract_series(rows: List[Dict], *keys) -> List[Optional[float]]:
    """Extract a numeric series from statement rows by trying multiple key names."""
    result = []
    for row in rows:
        val = None
        for key in keys:
            raw = row.get(key)
            if raw is not None:
                try:
                    val = float(raw)
                    break
                except (TypeError, ValueError):
                    pass
        result.append(val)
    return result


def _cagr(series: List[Optional[float]], years: int = 5) -> Optional[float]:
    """Compute CAGR over `years` from the series."""
    vals = [v for v in series if v is not None and v > 0]
    if len(vals) < 2:
        return None
    start = vals[max(0, len(vals) - years - 1)]
    end   = vals[-1]
    n     = min(len(vals) - 1, years)
    if start <= 0 or n <= 0:
        return None
    return round((end / start) ** (1 / n) - 1, 4) * 100  # as %


def _latest_ratio(numerator: List, denominator: List) -> Optional[float]:
    for n, d in zip(reversed(numerator), reversed(denominator)):
        if n is not None and d and d > 0:
            return round(n / d * 100, 2)
    return None


def _consistency(profits: List[Optional[float]]) -> float:
    """Fraction of years with positive profit."""
    valid = [p for p in profits if p is not None]
    if not valid:
        return 0.5
    return sum(1 for p in valid if p > 0) / len(valid)


def _trend(series: List[Optional[float]]) -> Optional[str]:
    """Return 'improving', 'deteriorating', or 'stable' based on last 3 values."""
    vals = [v for v in series if v is not None]
    if len(vals) < 3:
        return None
    recent = vals[-3:]
    if recent[-1] < recent[0] * 0.9:
        return "improving"
    if recent[-1] > recent[0] * 1.1:
        return "deteriorating"
    return "stable"


def _safe_div(a, b) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _clamp(v: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, v))


# ── Individual component scorers ──────────────────────────────────────────────


def _score_cagr(cagr: Optional[float]) -> float:
    if cagr is None:
        return 5.0
    if cagr >= 25:   return 10.0
    if cagr >= 18:   return 8.5
    if cagr >= 12:   return 7.0
    if cagr >= 8:    return 6.0
    if cagr >= 3:    return 5.0
    if cagr >= 0:    return 3.5
    return 1.5


def _score_margin(margin: Optional[float]) -> float:
    if margin is None:
        return 5.0
    if margin >= 25:   return 10.0
    if margin >= 18:   return 8.5
    if margin >= 12:   return 7.0
    if margin >= 8:    return 6.0
    if margin >= 4:    return 4.5
    if margin >= 0:    return 3.0
    return 1.0


def _score_de(de: Optional[float]) -> float:
    if de is None:
        return 5.0
    if de < 0.1:   return 10.0
    if de < 0.5:   return 8.5
    if de < 1.0:   return 7.0
    if de < 2.0:   return 5.5
    if de < 3.5:   return 3.5
    return 1.0


def _score_cfo_pat(ratio: Optional[float]) -> float:
    if ratio is None:
        return 5.0
    if ratio >= 1.2:   return 10.0
    if ratio >= 1.0:   return 8.5
    if ratio >= 0.8:   return 7.0
    if ratio >= 0.5:   return 5.5
    if ratio >= 0.2:   return 3.5
    return 1.5
