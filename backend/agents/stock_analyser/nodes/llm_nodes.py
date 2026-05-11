"""LLM node — synthesize all three sub-agent outputs into a full narrative."""
import json
import logging
from agents.shared.llm import get_llm
from agents.shared.formatters import ratio, pct, price as fmt_price, na

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a senior equity research analyst at Nivesh. "
    "Synthesize the sub-agent analysis into a concise, institutional-grade narrative. "
    "Output ONLY valid JSON — no markdown fences, no extra keys."
)


def _build_stock_prompt(state: dict) -> str:
    sm = state["stock_master"]
    lp = state.get("latest_price", {})
    r = state.get("financial_ratios", {})

    return f"""Synthesize this stock analysis into a comprehensive equity research narrative.

COMPANY
- Name: {sm.get("company_name")}
- Symbol: {sm.get("symbol")}
- Sector: {sm.get("sector")} | Industry: {sm.get("industry")}
- Market cap category: {sm.get("market_cap_cat")}
- Latest close: {fmt_price(lp.get("close"))}

FUNDAMENTAL AGENT OUTPUT (weight 40%)
- Signal: {state.get("fundamental_signal")}
- Score: {ratio(state.get("fundamental_score"))}/100
- Reasoning: {state.get("fundamental_reasoning")}

TECHNICAL AGENT OUTPUT (weight 30%)
- Signal: {state.get("technical_signal")}
- Reasoning: {state.get("technical_reasoning")}

VALUATION AGENT OUTPUT (weight 30%)
- Signal: {state.get("valuation_signal")}
- Reasoning: {state.get("valuation_reasoning")}

OVERALL HEALTH SCORE: {ratio(state.get("overall_health_score"))}/100

KEY RATIOS
- PE / PB / PS: {ratio(r.get("pe_ratio"))} / {ratio(r.get("pb_ratio"))} / {ratio(r.get("ps_ratio"))}
- ROE / ROCE: {pct(r.get("roe"))} / {pct(r.get("roce"))}
- Net Debt/EBITDA: {ratio(r.get("net_debt_ebitda"))}
- FCF Yield: {pct(r.get("fcf_yield"))}

Required output:
{{
  "full_narrative": "<6-8 sentence comprehensive equity analysis covering fundamentals, technicals, valuation, and overall outlook>"
}}"""


async def generate_narrative(state: dict) -> dict:
    if state.get("status") == "FAILED":
        return {}

    prompt = _build_stock_prompt(state)
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
            "full_narrative": parsed.get("full_narrative", ""),
            "status": "ANALYSED",
            "logs": state["logs"] + ["LLM narrative generated"],
        }
    except Exception as e:
        logger.warning(f"LLM failed for stock {state['symbol']}: {e}")
        # Simple rule-based fallback
        score = state.get("overall_health_score", 50)
        narrative = (
            f"{state['stock_master'].get('company_name')} shows a composite health score of "
            f"{score:.1f}/100. Fundamental signal: {state.get('fundamental_signal')}. "
            f"Technical momentum: {state.get('technical_signal')}. "
            f"Valuation vs peers: {state.get('valuation_signal')}. "
            "AI narrative unavailable — metrics-based assessment applied."
        )
        return {
            "full_narrative": narrative,
            "status": "ANALYSED",
            "logs": state["logs"] + [f"LLM failed ({e}); fallback narrative used"],
        }
