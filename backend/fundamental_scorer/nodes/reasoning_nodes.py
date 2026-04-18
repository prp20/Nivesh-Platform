from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from ..state import ScoringState
from typing import Dict, Any
from dotenv import load_dotenv

import logging
load_dotenv()
logger = logging.getLogger(__name__)

async def generate_reasoning_node(state: ScoringState) -> Dict[str, Any]:
    """
    LLM synthesis layer. 
    Uses Gemini to provide a premium narrative for the deterministic scores.
    """
    if state.get("status") == "FAILED":
        return {}

    try:
        # Initialize Gemini
        model = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=0.7
        )
        
        prompt = ChatPromptTemplate.from_template("""
        You are a Senior Equity Analyst for 'Nivesh', a premium fundamental analysis platform. 
        Analyze the deterministic scores for {symbol} and provide a high-fidelity synthesis.
        
        DETERMINISTIC DATA (Out of 10):
        - Composite Score: {composite_score}
        - P&L Score: {pl_score}
        - Balance Sheet Score: {bs_score}
        - Cash Flow Score: {cf_score}
        
        KEY METRICS:
        - P&L: {pl_metrics}
        - Balance Sheet: {bs_metrics}
        - Cash Flow: {cf_metrics}
        
        YOUR TASK:
        1. Create a 1-3 word LABEL that captures the essence (e.g., "Consistent Compounder", "Leveraged Risky", "Cash Cow").
        2. Write a 2-3 sentence SUMMARY explaining the rating. Be objective and mention specific metrics if they are significant.
        
        Tone: Professional, Crisp, Institutional.
        
        FORMAT:
        LABEL: <Label Text>
        SUMMARY: <Summary Text>
        """)
        
        # Build chain
        chain = prompt | model
        
        # Prepare context
        context = {
            "symbol": state["symbol"],
            "composite_score": state["composite_score"],
            "pl_score": state["pl_results"].get("score"),
            "pl_metrics": state["pl_results"].get("metrics"),
            "bs_score": state["bs_results"].get("score"),
            "bs_metrics": state["bs_results"].get("metrics"),
            "cf_score": state["cf_results"].get("score"),
            "cf_metrics": state["cf_results"].get("metrics"),
        }
        
        # Invoke LLM
        response = await chain.ainvoke(context)
        content = response.content
        
        # Simple parsing logic
        label = "N/A"
        summary = content
        
        if "LABEL:" in content and "SUMMARY:" in content:
            parts = content.split("SUMMARY:")
            label = parts[0].replace("LABEL:", "").strip()
            summary = parts[1].strip()
        elif "LABEL:" in content:
            label = content.replace("LABEL:", "").split("\n")[0].strip()
            
        return {
            "reasoning_label": label,
            "reasoning_text": summary,
            "status": "REASONED",
            "logs": state.get("logs", []) + ["LLM reasoning synthesized successfully"]
        }
    except Exception as e:
        logger.error(f"Error in LLM reasoning node: {e}")
        return {
            "reasoning_label": "Analysis Pending",
            "reasoning_text": f"Deterministic score is available, but AI synthesis failed: {str(e)}",
            "status": "REASONED", 
            "logs": state.get("logs", []) + [f"LLM failure: {e}"]
        }
