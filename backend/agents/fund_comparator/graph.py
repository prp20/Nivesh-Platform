"""Fund comparator LangGraph workflow — 2 to 4 funds side-by-side."""
import uuid
from functools import partial
import logging
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from .state import FundComparisonState
from .nodes.fetch_nodes import validate_inputs, fetch_all_funds
from .nodes.compute_nodes import build_metrics_matrix, rank_funds
from .nodes.llm_nodes import generate_comparison
from .nodes.persist_nodes import persist_comparison

logger = logging.getLogger(__name__)


def _should_continue(state: FundComparisonState) -> str:
    return "end" if state.get("status") == "FAILED" else "continue"


def build_fund_comparator_graph(session: AsyncSession):
    wf = StateGraph(FundComparisonState)

    wf.add_node("validate_inputs", partial(validate_inputs, session=session))
    wf.add_node("fetch_all_funds", partial(fetch_all_funds, session=session))
    wf.add_node("build_metrics_matrix", build_metrics_matrix)
    wf.add_node("rank_funds", rank_funds)
    wf.add_node("generate_comparison", generate_comparison)
    wf.add_node("persist_comparison", partial(persist_comparison, session=session))

    wf.set_entry_point("validate_inputs")
    wf.add_conditional_edges(
        "validate_inputs", _should_continue, {"end": END, "continue": "fetch_all_funds"}
    )
    wf.add_conditional_edges(
        "fetch_all_funds", _should_continue, {"end": END, "continue": "build_metrics_matrix"}
    )
    wf.add_edge("build_metrics_matrix", "rank_funds")
    wf.add_edge("rank_funds", "generate_comparison")
    wf.add_edge("generate_comparison", "persist_comparison")
    wf.add_edge("persist_comparison", END)

    return wf.compile()


async def run_fund_comparator(fund_codes: list[str], session: AsyncSession) -> dict:
    comparison_id = str(uuid.uuid4())
    initial_state: FundComparisonState = {
        "fund_codes": fund_codes,
        "funds_data": {},
        "metrics_matrix": {},
        "rankings": {},
        "winner_code": "",
        "ranked_verdict": [],
        "narrative": "",
        "comparison_id": comparison_id,
        "status": "PENDING",
        "error": None,
        "logs": [f"Starting comparison for {fund_codes}"],
    }

    graph = build_fund_comparator_graph(session)
    try:
        return await graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Fund comparator graph failed: {e}")
        return {"status": "FAILED", "error": str(e), "comparison_id": comparison_id}
