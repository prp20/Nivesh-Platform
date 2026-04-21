from langgraph.graph import StateGraph, END
from .state import ScoringState
from .nodes.data_nodes import fetch_financials_node, persist_scores_node
from .nodes.compute_nodes import compute_scores_node
from .nodes.reasoning_nodes import generate_reasoning_node
from sqlalchemy.ext.asyncio import AsyncSession
from functools import partial
from langsmith import traceable
import logging

logger = logging.getLogger(__name__)

async def create_scorer_graph(db: AsyncSession):
    """
    Constructs and compiles the LangGraph workflow.
    
    The workflow follows this linear path:
    Fetch -> Score (Math) -> Reason (AI) -> Persist
    """
    # Initialize Graph with our State schema
    workflow = StateGraph(ScoringState)
    
    # 1. Add Nodes
    # We wrap nodes that require DB access using partial
    workflow.add_node("fetch_data", partial(fetch_financials_node, db=db))
    workflow.add_node("compute_scores", compute_scores_node)
    workflow.add_node("generate_reasoning", generate_reasoning_node)
    workflow.add_node("persist_results", partial(persist_scores_node, db=db))
    
    # 2. Define Edges (Linear Pipeline)
    workflow.set_entry_point("fetch_data")
    
    # Check for early failure logic could be added here with conditional edges
    # For now, we follow the sequence and nodes handle status internally
    workflow.add_edge("fetch_data", "compute_scores")
    workflow.add_edge("compute_scores", "generate_reasoning")
    workflow.add_edge("generate_reasoning", "persist_results")
    workflow.add_edge("persist_results", END)
    
    # 3. Compile the graph
    app = workflow.compile()
    return app

@traceable(
    name="Fundamental Scorer Workflow",
    run_type="chain",
    metadata={"version": "1.0.0"}
)
async def run_fundamental_scorer(stock_id: int, symbol: str, db: AsyncSession, period_type: str = "annual", score_version: str = "v1.0"):
    """
    Convenience entry point to run the scorer for a specific stock.
    """
    # Initial State
    initial_state = {
        "stock_id": stock_id,
        "symbol": symbol,
        "period_type": period_type,
        "score_version": score_version,
        "statements_data": {},
        "status": "PENDING",
        "logs": [f"Starting scoring for {symbol}"]
    }
    
    # Create graph instance
    graph = await create_scorer_graph(db)
    
    # Execute
    try:
        final_state = await graph.ainvoke(initial_state)
        return final_state
    except Exception as e:
        logger.error(f"Graph execution failed for {symbol}: {e}")
        return {
            "status": "FAILED",
            "error": str(e),
            "logs": [f"Execution error: {e}"]
        }
