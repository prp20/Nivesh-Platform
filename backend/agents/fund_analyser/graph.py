"""Fund analyser LangGraph workflow."""
from functools import partial
import logging
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from .state import FundAnalysisState
from .nodes.fetch_nodes import validate_fund, fetch_fund_metrics, fetch_peers
from .nodes.compute_nodes import rank_among_peers
from .nodes.llm_nodes import generate_analysis
from .nodes.persist_nodes import persist_result

logger = logging.getLogger(__name__)


def _should_continue(state: FundAnalysisState) -> str:
    """Route to END immediately if validation or any step failed."""
    return "end" if state.get("status") == "FAILED" else "continue"


def build_fund_analyser_graph(session: AsyncSession) -> StateGraph:
    wf = StateGraph(FundAnalysisState)

    # Bind DB session to nodes that need it
    wf.add_node("validate_fund", partial(validate_fund, session=session))
    wf.add_node("fetch_fund_metrics", partial(fetch_fund_metrics, session=session))
    wf.add_node("fetch_peers", partial(fetch_peers, session=session))
    wf.add_node("rank_among_peers", rank_among_peers)
    wf.add_node("generate_analysis", generate_analysis)
    wf.add_node("persist_result", partial(persist_result, session=session))

    wf.set_entry_point("validate_fund")
    wf.add_conditional_edges(
        "validate_fund",
        _should_continue,
        {"end": END, "continue": "fetch_fund_metrics"},
    )
    wf.add_conditional_edges(
        "fetch_fund_metrics",
        _should_continue,
        {"end": END, "continue": "fetch_peers"},
    )
    wf.add_edge("fetch_peers", "rank_among_peers")
    wf.add_edge("rank_among_peers", "generate_analysis")
    wf.add_edge("generate_analysis", "persist_result")
    wf.add_edge("persist_result", END)

    return wf.compile()


async def run_fund_analyser(scheme_code: str, session: AsyncSession) -> dict:
    """Entry point — run the full fund analysis graph."""
    initial_state: FundAnalysisState = {
        "scheme_code": scheme_code,
        "fund_master": {},
        "fund_metrics": {},
        "peer_metrics": [],
        "composite_score": 0.0,
        "peer_percentile": 50.0,
        "category_rank": 0,
        "category_size": 0,
        "verdict_label": "",
        "verdict_text": "",
        "key_strengths": [],
        "key_risks": [],
        "status": "PENDING",
        "error": None,
        "logs": [f"Starting fund analysis for {scheme_code}"],
    }

    graph = build_fund_analyser_graph(session)
    try:
        return await graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Fund analyser graph failed for {scheme_code}: {e}")
        return {"status": "FAILED", "error": str(e), "scheme_code": scheme_code}
