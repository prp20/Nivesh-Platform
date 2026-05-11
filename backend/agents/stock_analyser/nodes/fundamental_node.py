"""ONE JOB: Score fundamentals → fundamental_score + fundamental_signal + fundamental_reasoning.

Uses Piotroski F-Score, ROE, ROCE, FCF margin, Debt/Equity from financial_ratios table.
No LLM call — pure rule-based scoring.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


async def fundamental_node(state: dict) -> dict:
    r = state.get("financial_ratios", {})
    score_parts = []

    # 1. Piotroski F-Score (0-9). Map to 0-30 contribution.
    piotroski = _f(r.get("piotroski_f_score"), -1)
    if piotroski >= 0:
        p_score = min((piotroski / 9) * 30, 30)
        score_parts.append(p_score)
    else:
        score_parts.append(15.0)  # neutral default if missing

    # 2. ROE (return on equity). Good > 15%, excellent > 20%. Contribution 0-20.
    roe = _f(r.get("roe"))
    if roe >= 0.20:
        score_parts.append(20.0)
    elif roe >= 0.15:
        score_parts.append(15.0)
    elif roe >= 0.08:
        score_parts.append(8.0)
    elif roe > 0:
        score_parts.append(4.0)
    else:
        score_parts.append(0.0)

    # 3. ROCE. Good > 12%. Contribution 0-20.
    roce = _f(r.get("roce"))
    if roce >= 0.20:
        score_parts.append(20.0)
    elif roce >= 0.12:
        score_parts.append(14.0)
    elif roce >= 0.08:
        score_parts.append(8.0)
    else:
        score_parts.append(3.0)

    # 4. FCF margin (FCF / revenue proxy). Positive FCF is healthy. Contribution 0-15.
    fcf_margin = _f(r.get("fcf_margin"))
    if fcf_margin >= 0.15:
        score_parts.append(15.0)
    elif fcf_margin >= 0.05:
        score_parts.append(10.0)
    elif fcf_margin > 0:
        score_parts.append(5.0)
    else:
        score_parts.append(0.0)

    # 5. Net Debt/EBITDA (leverage). Lower is safer. Contribution 0-15.
    nd_ebitda = _f(r.get("net_debt_ebitda"), default=3.0)
    if nd_ebitda <= 0:
        score_parts.append(15.0)   # net cash
    elif nd_ebitda <= 1.0:
        score_parts.append(12.0)
    elif nd_ebitda <= 2.5:
        score_parts.append(7.0)
    elif nd_ebitda <= 4.0:
        score_parts.append(3.0)
    else:
        score_parts.append(0.0)

    total = min(sum(score_parts), 100.0)
    total = round(total, 2)

    if total >= 70:
        signal, reason = "STRONG", (
            f"Strong fundamentals: ROE {roe*100:.1f}%, ROCE {roce*100:.1f}%, "
            f"Piotroski {int(piotroski) if piotroski >= 0 else 'N/A'}/9, "
            f"FCF margin {fcf_margin*100:.1f}%."
        )
    elif total >= 50:
        signal, reason = "GOOD", (
            f"Decent fundamentals with ROE {roe*100:.1f}% and ROCE {roce*100:.1f}%. "
            f"Some metrics need monitoring."
        )
    elif total >= 30:
        signal, reason = "WEAK", (
            f"Below-average fundamentals. ROE {roe*100:.1f}%, leverage concerns possible."
        )
    else:
        signal, reason = "POOR", (
            f"Weak fundamentals across profitability and leverage metrics. High caution advised."
        )

    return {
        "fundamental_score": total,
        "fundamental_signal": signal,
        "fundamental_reasoning": reason,
        "logs": state["logs"] + [f"Fundamental agent: {signal} ({total}/100)"],
    }
