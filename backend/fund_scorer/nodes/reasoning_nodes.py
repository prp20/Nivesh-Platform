from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from ..state import FundScoringState
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

async def generate_fund_reasoning_node(state: FundScoringState) -> Dict[str, Any]:
    """
    LLM synthesis layer for mutual funds.
    """
    if state.get("status") == "FAILED":
        return {}

    try:
        # Initialize LLM
        model = ChatGroq(
            model_name="llama-3.3-70b-versatile",
            temperature=0.7
        )
        
        prompt = ChatPromptTemplate.from_template("""
        You are a Senior Mutual Fund Analyst for 'Nivesh', a premium investment analysis platform. 
        Analyze the performance and risk metrics for the mutual fund '{scheme_name}' ({category}) and provide a high-fidelity synthesis.
        
        DETERMINISTIC METRICS:
        - Composite Alpha Score: {composite_score}/100
        - Sharpe Ratio: {sharpe_ratio}
        - Alpha: {alpha}
        - Beta: {beta}
        - Tracking Error: {tracking_error}
        - Information Ratio: {info_ratio}
        - CAGR (3Y/5Y): {cagr_3y} / {cagr_5y}
        - Upside/Downside Capture: {upside_capture} / {downside_capture}
        - Expense Ratio: {expense_ratio}
        - AUM: {aum} Cr
        
        YOUR TASK:
        1. Create a 1-3 word LABEL that captures the fund's current character (e.g., "Steady Compounder", "Aggressive Alpha Seeker", "Risk-Managed Core").
        2. Write a 2-3 sentence SUMMARY explaining the analysis. Mention key risk-adjusted metrics (Sharpe/Alpha) and how it compares to its peers or benchmark based on capture ratios.
        
        Tone: Professional, Crisp, Institutional, Visionary.
        
        FORMAT:
        LABEL: <Label Text>
        SUMMARY: <Summary Text>
        """)
        
        # Build chain
        chain = prompt | model
        
        # Prepare context
        m = state["metrics"]
        context = {
            "scheme_name": state["scheme_name"],
            "category": state["category"],
            "composite_score": state["composite_score"],
            "sharpe_ratio": m.get("sharpe_ratio", "N/A"),
            "alpha": m.get("alpha", "N/A"),
            "beta": m.get("beta", "N/A"),
            "tracking_error": m.get("tracking_error", "N/A"),
            "info_ratio": m.get("information_ratio", "N/A"),
            "cagr_3y": f"{float(m.get('cagr_3year')*100):.2f}%" if m.get("cagr_3year") else "N/A",
            "cagr_5y": f"{float(m.get('cagr_5year')*100):.2f}%" if m.get("cagr_5year") else "N/A",
            "upside_capture": m.get("upside_capture", "N/A"),
            "downside_capture": m.get("downside_capture", "N/A"),
            "expense_ratio": f"{float(m.get('expense_ratio')*100):.2f}%" if m.get("expense_ratio") else "N/A",
            "aum": m.get("aum_in_crores", "N/A"),
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
            "logs": state.get("logs", []) + ["LLM reasoning for fund synthesized successfully"]
        }
    except Exception as e:
        logger.error(f"Error in LLM reasoning node for fund: {e}")
        return {
            "reasoning_label": "Analysis Pending",
            "reasoning_text": f"Metric analysis is available, but AI synthesis failed: {str(e)}",
            "status": "REASONED", 
            "logs": state.get("logs", []) + [f"LLM failure: {e}"]
        }
