"""Stock recommender LangGraph workflow — BUY / HOLD / SELL recommendation.

Requires a completed stock analysis to already exist in agent_stock_analysis.

Flow:
  fetch_analysis → fetch_momentum → decision_node → generate_recommendation
  → persist_recommendation → END
"""
from functools import partial
import logging
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from .state import StockRecommendationState
from .nodes.fetch_nodes import fetch_analysis, fetch_momentum
from .nodes.decision_node import decision_node
from .nodes.llm_nodes import generate_recommendation
from .nodes.persist_nodes import persist_recommendation

logger = logging.getLogger(__name__)


def _should_continue(state: StockRecommendationState) -> str:
    return "end" if state.get("status") == "FAILED" else "continue"


def build_stock_recommender_graph(session: AsyncSession):
    wf = StateGraph(StockRecommendationState)

    wf.add_node("fetch_analysis", partial(fetch_analysis, session=session))
    wf.add_node("fetch_momentum", partial(fetch_momentum, session=session))
    wf.add_node("decision_node", decision_node)
    wf.add_node("generate_recommendation", generate_recommendation)
    wf.add_node("persist_recommendation", partial(persist_recommendation, session=session))

    wf.set_entry_point("fetch_analysis")
    wf.add_conditional_edges(
        "fetch_analysis", _should_continue, {"end": END, "continue": "fetch_momentum"}
    )
    wf.add_edge("fetch_momentum", "decision_node")
    wf.add_edge("decision_node", "generate_recommendation")
    wf.add_edge("generate_recommendation", "persist_recommendation")
    wf.add_edge("persist_recommendation", END)

    return wf.compile()


async def run_stock_recommender(symbol: str, session: AsyncSession) -> dict:
    initial_state: StockRecommendationState = {
        "symbol": symbol.upper(),
        "stock_analysis": {},
        "stock_rating": {},
        "latest_price": 0.0,
        "pre_signal": "HOLD",
        "pre_confidence": "LOW",
        "signal": "",
        "confidence": "",
        "time_horizon": "",
        "entry_price_low": None,
        "entry_price_high": None,
        "target_price": None,
        "stop_loss": None,
        "key_catalysts": [],
        "key_risks": [],
        "recommendation_text": "",
        "stock_analysis_id": None,
        "status": "PENDING",
        "error": None,
        "logs": [f"Starting recommendation for {symbol}"],
    }

    graph = build_stock_recommender_graph(session)
    try:
        return await graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Stock recommender graph failed for {symbol}: {e}")
        return {"status": "FAILED", "error": str(e), "symbol": symbol}
