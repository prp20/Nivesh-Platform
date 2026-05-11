"""Stock analyser LangGraph workflow.

Flow:
  validate_stock → fetch_stock_master → fetch_all_data
  → fundamental_node → technical_node → valuation_node
  → aggregate_node → generate_narrative → persist_analysis → END
"""
from functools import partial
import logging
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from .state import StockAnalysisState
from .nodes.fetch_nodes import validate_stock, fetch_stock_master, fetch_all_data
from .nodes.fundamental_node import fundamental_node
from .nodes.technical_node import technical_node
from .nodes.valuation_node import valuation_node
from .nodes.aggregate_node import aggregate_node
from .nodes.llm_nodes import generate_narrative
from .nodes.persist_nodes import persist_analysis

logger = logging.getLogger(__name__)


def _should_continue(state: StockAnalysisState) -> str:
    return "end" if state.get("status") == "FAILED" else "continue"


def build_stock_analyser_graph(session: AsyncSession):
    wf = StateGraph(StockAnalysisState)

    wf.add_node("validate_stock", partial(validate_stock, session=session))
    wf.add_node("fetch_stock_master", partial(fetch_stock_master, session=session))
    wf.add_node("fetch_all_data", partial(fetch_all_data, session=session))
    wf.add_node("fundamental_node", fundamental_node)
    wf.add_node("technical_node", technical_node)
    wf.add_node("valuation_node", valuation_node)
    wf.add_node("aggregate_node", aggregate_node)
    wf.add_node("generate_narrative", generate_narrative)
    wf.add_node("persist_analysis", partial(persist_analysis, session=session))

    wf.set_entry_point("validate_stock")
    wf.add_conditional_edges(
        "validate_stock", _should_continue, {"end": END, "continue": "fetch_stock_master"}
    )
    wf.add_edge("fetch_stock_master", "fetch_all_data")
    wf.add_edge("fetch_all_data", "fundamental_node")
    wf.add_edge("fundamental_node", "technical_node")
    wf.add_edge("technical_node", "valuation_node")
    wf.add_edge("valuation_node", "aggregate_node")
    wf.add_edge("aggregate_node", "generate_narrative")
    wf.add_edge("generate_narrative", "persist_analysis")
    wf.add_edge("persist_analysis", END)

    return wf.compile()


async def run_stock_analyser(symbol: str, session: AsyncSession) -> dict:
    initial_state: StockAnalysisState = {
        "symbol": symbol.upper(),
        "stock_master": {},
        "latest_price": {},
        "financial_ratios": {},
        "financial_statements": {},
        "technical_indicators": {},
        "sector_medians": {},
        "fundamental_score": 0.0,
        "fundamental_signal": "WEAK",
        "fundamental_reasoning": "",
        "technical_signal": "NEUTRAL",
        "technical_reasoning": "",
        "valuation_signal": "FAIR",
        "valuation_reasoning": "",
        "overall_health_score": 0.0,
        "full_narrative": "",
        "stock_analysis_id": None,
        "status": "PENDING",
        "error": None,
        "logs": [f"Starting stock analysis for {symbol}"],
    }

    graph = build_stock_analyser_graph(session)
    try:
        return await graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Stock analyser graph failed for {symbol}: {e}")
        return {"status": "FAILED", "error": str(e), "symbol": symbol}
