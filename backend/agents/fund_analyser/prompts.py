from agents.shared.formatters import pct, ratio, crore, na

SYSTEM_PROMPT = (
    "You are a SEBI-registered senior mutual fund analyst at Nivesh, a premium "
    "investment analysis platform. Analyze fund metrics objectively. "
    "Output ONLY valid JSON — no markdown fences, no extra keys."
)

OUTPUT_SCHEMA = """
{
  "verdict_label": "<3-5 word label capturing the fund's character>",
  "verdict_text": "<3-5 sentence analysis covering risk-adjusted performance, benchmark comparison, and suitability>",
  "key_strengths": ["<strength 1>", "<strength 2>"],
  "key_risks": ["<risk 1>", "<risk 2>"]
}
"""


def build_fund_prompt(state: dict) -> str:
    m = state["fund_metrics"]
    fm = state["fund_master"]
    return f"""Analyze this mutual fund and return a JSON object matching the schema below.

FUND IDENTITY
- Name: {fm.get("scheme_name")}
- Category: {fm.get("scheme_category")} / {fm.get("scheme_subcategory", "N/A")}
- AMC: {fm.get("amc_name")}
- Plan type: {fm.get("plan_type")}

PERFORMANCE METRICS
- CAGR 3Y / 5Y: {pct(m.get("cagr_3year"))} / {pct(m.get("cagr_5year"))}
- Absolute return 1Y / 3Y / 5Y: {pct(m.get("absolute_return_1y"))} / {pct(m.get("absolute_return_3y"))} / {pct(m.get("absolute_return_5y"))}

RISK METRICS
- Sharpe ratio: {ratio(m.get("sharpe_ratio"))}
- Sortino ratio: {ratio(m.get("sortino_ratio"))}
- Alpha / Beta: {ratio(m.get("alpha"))} / {ratio(m.get("beta"))}
- Standard deviation: {ratio(m.get("standard_deviation"))}
- Maximum drawdown: {pct(m.get("maximum_drawdown"))}
- Tracking error: {ratio(m.get("tracking_error"))}
- Information ratio: {ratio(m.get("information_ratio"))}
- Upside / Downside capture: {ratio(m.get("upside_capture"))} / {ratio(m.get("downside_capture"))}

COST & SIZE
- Expense ratio: {pct(m.get("expense_ratio"))}
- AUM: {crore(m.get("aum_in_crores"))}

PEER CONTEXT
- Composite score: {ratio(state.get("composite_score"))}/100
- Peer percentile: {ratio(state.get("peer_percentile"))}th (higher = better)
- Category rank: {na(state.get("category_rank"))} of {na(state.get("category_size"))} funds

REQUIRED OUTPUT SCHEMA:
{OUTPUT_SCHEMA}"""


# Fallback verdict when LLM fails
def fallback_verdict(composite_score: float) -> dict:
    if composite_score >= 70:
        label, text = "Strong Performer", "This fund demonstrates consistently strong risk-adjusted returns, outperforming the majority of its category peers. Its Sharpe ratio and alpha suggest disciplined portfolio management."
    elif composite_score >= 50:
        label, text = "Consistent Performer", "This fund delivers steady returns in line with category expectations. Risk metrics are balanced, making it suitable for medium-term investors."
    elif composite_score >= 30:
        label, text = "Underperformer", "This fund lags behind category peers on key risk-adjusted metrics. Investors should review allocation and consider alternatives."
    else:
        label, text = "High Risk Fund", "This fund carries elevated risk with below-average returns. Exercise caution and assess suitability against your risk profile."

    return {
        "verdict_label": label,
        "verdict_text": text,
        "key_strengths": ["Diversified portfolio", "Regulated structure"],
        "key_risks": ["Market volatility risk", "Below-average peer performance"],
    }
