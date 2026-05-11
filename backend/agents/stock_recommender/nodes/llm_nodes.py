"""LLM node — generate structured BUY/HOLD/SELL recommendation."""
import json
import logging
from agents.shared.llm import get_llm
from agents.shared.formatters import ratio, pct, price as fmt_price

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a SEBI-registered senior equity advisor at Nivesh. "
    "Based on the quantitative analysis provided, generate a structured investment recommendation. "
    "Output ONLY valid JSON — no markdown fences, no extra keys. "
    "For SELL signals with low health score, set price targets to null."
)


def _build_recommendation_prompt(state: dict) -> str:
    analysis = state.get("stock_analysis", {})
    rating = state.get("stock_rating", {})
    price = state.get("latest_price", 0.0)

    return f"""Generate a structured investment recommendation for this stock.

STOCK: {state["symbol"]}
CURRENT PRICE: {fmt_price(price)}

QUANTITATIVE ANALYSIS SUMMARY
- Overall health score: {ratio(analysis.get("overall_health_score"))}/100
- Fundamental signal: {analysis.get("fundamental_signal")} — {analysis.get("fundamental_reasoning", "N/A")}
- Technical signal: {analysis.get("technical_signal")} — {analysis.get("technical_reasoning", "N/A")}
- Valuation signal: {analysis.get("valuation_signal")} — {analysis.get("valuation_reasoning", "N/A")}
- Full narrative: {analysis.get("full_narrative", "N/A")}

COMPOSITE RATING
- Rating label: {rating.get("rating_label", "N/A")}
- Total score: {ratio(rating.get("total_score"))}/100
- Momentum score: {ratio(rating.get("momentum_score"))}/100
- Fundamental score: {ratio(rating.get("fundamental_score"))}/100
- Technical score: {ratio(rating.get("technical_score"))}/100

RULE-BASED PRE-SIGNAL: {state.get("pre_signal")} ({state.get("pre_confidence")} confidence)

Required JSON output schema:
{{
  "signal": "BUY" | "HOLD" | "SELL",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "time_horizon": "SHORT" | "MEDIUM" | "LONG",
  "entry_price_low": <number or null>,
  "entry_price_high": <number or null>,
  "target_price": <number or null>,
  "stop_loss": <number or null>,
  "key_catalysts": ["<catalyst 1>", "<catalyst 2>"],
  "key_risks": ["<risk 1>", "<risk 2>"],
  "recommendation_text": "<5-6 sentence investment recommendation>"
}}

Note: entry/target/stop_loss should be based on technical support/resistance relative to current price {fmt_price(price)}.
For SELL + LOW confidence, set all price fields to null."""


async def generate_recommendation(state: dict) -> dict:
    if state.get("status") == "FAILED":
        return {}

    prompt = _build_recommendation_prompt(state)
    pre_signal = state.get("pre_signal", "HOLD")
    pre_conf = state.get("pre_confidence", "LOW")
    price = state.get("latest_price", 0.0)

    try:
        llm = get_llm(temperature=0.2)
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

        def _safe_price(v):
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        return {
            "signal": parsed.get("signal", pre_signal),
            "confidence": parsed.get("confidence", pre_conf),
            "time_horizon": parsed.get("time_horizon", "MEDIUM"),
            "entry_price_low": _safe_price(parsed.get("entry_price_low")),
            "entry_price_high": _safe_price(parsed.get("entry_price_high")),
            "target_price": _safe_price(parsed.get("target_price")),
            "stop_loss": _safe_price(parsed.get("stop_loss")),
            "key_catalysts": parsed.get("key_catalysts", []),
            "key_risks": parsed.get("key_risks", []),
            "recommendation_text": parsed.get("recommendation_text", ""),
            "status": "ANALYSED",
            "logs": state["logs"] + ["LLM recommendation generated"],
        }

    except Exception as e:
        logger.warning(f"LLM failed for recommendation {state['symbol']}: {e}")
        # Fallback: use pre_signal + basic price math
        entry_low = round(price * 0.99, 2) if price and pre_signal == "BUY" else None
        entry_high = round(price * 1.01, 2) if price and pre_signal == "BUY" else None
        target = round(price * 1.15, 2) if price and pre_signal == "BUY" else None
        stop_loss = round(price * 0.92, 2) if price and pre_signal == "BUY" else None

        return {
            "signal": pre_signal,
            "confidence": pre_conf,
            "time_horizon": "MEDIUM",
            "entry_price_low": entry_low,
            "entry_price_high": entry_high,
            "target_price": target,
            "stop_loss": stop_loss,
            "key_catalysts": ["Rule-based signal applied"],
            "key_risks": ["AI synthesis unavailable"],
            "recommendation_text": f"{pre_signal} recommendation based on quantitative scoring. AI synthesis unavailable.",
            "status": "ANALYSED",
            "logs": state["logs"] + [f"LLM failed ({e}); fallback used"],
        }
