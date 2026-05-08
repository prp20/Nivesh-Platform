from langgraph.graph import StateGraph, END
from .state import FundScoringState
from .nodes.data_nodes import fetch_fund_data_node
from .nodes.reasoning_nodes import generate_fund_reasoning_node
from sqlalchemy.ext.asyncio import AsyncSession
from functools import partial
import logging

logger = logging.getLogger(__name__)

async def create_fund_scorer_graph(db: AsyncSession):
    """
    Constructs and compiles the LangGraph workflow for mutual funds.
    """
    workflow = StateGraph(FundScoringState)
    
    # 1. Add Nodes
    workflow.add_node("fetch_fund_data", partial(fetch_fund_data_node, db=db))
    workflow.add_node("generate_reasoning", generate_fund_reasoning_node)
    
    # 2. Define Edges
    workflow.set_entry_point("fetch_fund_data")
    workflow.add_edge("fetch_fund_data", "generate_reasoning")
    workflow.add_edge("generate_reasoning", END)
    
    # 3. Compile
    app = workflow.compile()
    return app

async def run_fund_scorer(scheme_code: str, db: AsyncSession):
    """
    Entry point to run the agentic analysis for a specific fund.
    """
    initial_state = {
        "scheme_code": scheme_code,
        "scheme_name": "",
        "category": "",
        "metrics": {},
        "composite_score": 0.0,
        "reasoning_label": "",
        "reasoning_text": "",
        "status": "PENDING",
        "error": None,
        "logs": [f"Starting agentic analysis for fund {scheme_code}"]
    }
    
    graph = await create_fund_scorer_graph(db)
    
    try:
        final_state = await graph.ainvoke(initial_state)
        return final_state
    except Exception as e:
        logger.error(f"Fund graph execution failed for {scheme_code}: {e}")
        return {
            "status": "FAILED",
            "error": str(e),
            "logs": [f"Execution error: {e}"]
        }
