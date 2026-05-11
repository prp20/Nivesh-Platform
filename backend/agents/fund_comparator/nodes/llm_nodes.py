"""LLM node — generates comparison narrative and ranked verdict."""
import json
import logging
from agents.shared.llm import get_llm
from agents.shared.formatters import pct, ratio, na

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a senior mutual fund comparison analyst at Nivesh. "
    "Compare funds objectively based on risk-adjusted metrics. "
    "Output ONLY valid JSON — no markdown fences, no extra keys."
)


def _build_comparison_prompt(state: dict) -> str:
    matrix = state["metrics_matrix"]
    rankings = state["rankings"]
    funds_data = state["funds_data"]

    # Build formatted table
    lines = ["FUND COMPARISON MATRIX", ""]
    metric_labels = {
        "cagr_3year": "CAGR 3Y", "cagr_5year": "CAGR 5Y",
        "sharpe_ratio": "Sharpe", "sortino_ratio": "Sortino",
        "alpha": "Alpha", "beta": "Beta",
        "maximum_drawdown": "Max Drawdown", "tracking_error": "Tracking Error",
        "information_ratio": "Info Ratio", "upside_capture": "Upside Capture",
        "downside_capture": "Downside Capture", "expense_ratio": "Expense Ratio",
    }
    pct_metrics = {"cagr_3year", "cagr_5year", "maximum_drawdown", "expense_ratio",
                   "upside_capture", "downside_capture"}

    codes = list(matrix.keys())
    header = "Metric         | " + " | ".join(
        f"{funds_data[c]['master'].get('scheme_name', c)[:20]:<20}" for c in codes
    )
    lines.append(header)
    lines.append("-" * len(header))

    for metric, label in metric_labels.items():
        row_vals = []
        for code in codes:
            v = matrix[code].get(metric)
            rank = rankings[code].get(metric, "N/A")
            fmt = pct(v) if metric in pct_metrics else ratio(v)
            row_vals.append(f"{fmt} (#{rank})")
        lines.append(f"{label:<15}| " + " | ".join(f"{rv:<20}" for rv in row_vals))

    lines.append("")
    lines.append(f"Overall ranking: " + ", ".join(
        f"#{rankings[c]['overall_rank']} {funds_data[c]['master'].get('scheme_name', c)}"
        for c in sorted(codes, key=lambda c: rankings[c]["overall_rank"])
    ))

    table = "\n".join(lines)

    schema = """
{
  "narrative": "<4-6 sentence comparison covering performance differences, risk profiles, cost, and suitability>",
  "ranked_verdict": [
    {"rank": 1, "code": "<scheme_code>", "name": "<scheme_name>", "one_liner": "<15-word max summary>"},
    ...
  ]
}"""

    return f"{table}\n\nBased on the above, provide a JSON response matching this schema:\n{schema}"


async def generate_comparison(state: dict) -> dict:
    """LLM call — produce narrative and ranked_verdict."""
    if state.get("status") == "FAILED":
        return {}

    prompt = _build_comparison_prompt(state)
    try:
        llm = get_llm(temperature=0.3)
        from langchain_core.messages import HumanMessage, SystemMessage
        response = await llm.ainvoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        parsed = json.loads(content)
        return {
            "narrative": parsed.get("narrative", ""),
            "ranked_verdict": parsed.get("ranked_verdict", []),
            "status": "ANALYSED",
            "logs": state["logs"] + ["LLM comparison narrative generated"],
        }

    except Exception as e:
        logger.warning(f"LLM failed for comparison: {e} — using basic fallback")
        funds_data = state["funds_data"]
        rankings = state["rankings"]
        codes = sorted(funds_data.keys(), key=lambda c: rankings[c]["overall_rank"])
        ranked = [
            {
                "rank": rankings[c]["overall_rank"],
                "code": c,
                "name": funds_data[c]["master"].get("scheme_name", c),
                "one_liner": "Ranked by composite risk-adjusted metrics",
            }
            for c in codes
        ]
        return {
            "narrative": "Comparison based on quantitative metrics. AI synthesis unavailable.",
            "ranked_verdict": ranked,
            "status": "ANALYSED",
            "logs": state["logs"] + [f"LLM failed ({e}); fallback used"],
        }
