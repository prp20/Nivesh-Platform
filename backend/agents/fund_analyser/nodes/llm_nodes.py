"""LLM synthesis node for fund analysis."""
import json
import logging
from agents.shared.llm import get_llm
from agents.fund_analyser.prompts import build_fund_prompt, fallback_verdict

logger = logging.getLogger(__name__)


async def generate_analysis(state: dict) -> dict:
    """Call the LLM to produce verdict_label, verdict_text, key_strengths, key_risks."""
    if state.get("status") == "FAILED":
        return {}

    prompt = build_fund_prompt(state)
    composite = state.get("composite_score", 50.0)

    try:
        llm = get_llm(temperature=0.3)
        from langchain_core.messages import HumanMessage, SystemMessage
        from agents.fund_analyser.prompts import SYSTEM_PROMPT

        response = await llm.ainvoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        content = response.content.strip()

        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        parsed = json.loads(content)
        return {
            "verdict_label": parsed.get("verdict_label", ""),
            "verdict_text": parsed.get("verdict_text", ""),
            "key_strengths": parsed.get("key_strengths", []),
            "key_risks": parsed.get("key_risks", []),
            "status": "ANALYSED",
            "logs": state["logs"] + ["LLM analysis generated successfully"],
        }

    except Exception as e:
        logger.warning(f"LLM failed for fund {state['scheme_code']}: {e} — using fallback")
        fb = fallback_verdict(composite)
        return {
            "verdict_label": fb["verdict_label"],
            "verdict_text": fb["verdict_text"],
            "key_strengths": fb["key_strengths"],
            "key_risks": fb["key_risks"],
            "status": "ANALYSED",
            "logs": state["logs"] + [f"LLM failed ({e}); fallback verdict applied"],
        }
