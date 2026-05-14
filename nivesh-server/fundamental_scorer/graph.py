"""
fundamental_scorer/graph.py — LangGraph orchestration for fundamental scoring.

Public interface:
    run_fundamental_scorer(stock_id, symbol, db, period_type, score_version) → dict

Pipeline stages:
    Fetch → Compute → Reason → Persist

The graph uses a simple linear execution (not parallel) since each stage
depends on the previous one.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def run_fundamental_scorer(
    stock_id: int,
    symbol: str,
    db: AsyncSession,
    period_type: str = "annual",
    score_version: str = "v1.0",
) -> Dict[str, Any]:
    """
    Run the full Fetch → Compute → Reason → Persist pipeline for a stock.

    Returns the final state dict, which is compatible with ScoringStateSchema.
    On failure, returns a dict with status='FAILED' and error message.
    """
    from fundamental_scorer.nodes.data_nodes import fetch_statements, persist_scores_node
    from fundamental_scorer.nodes.compute_nodes import compute_scores_node
    from fundamental_scorer.nodes.reasoning_nodes import generate_reasoning_node

    # Initial state
    state: Dict[str, Any] = {
        "stock_id":       stock_id,
        "symbol":         symbol,
        "period_type":    period_type,
        "score_version":  score_version,
        "statements_data": {},
        "pl_results":     None,
        "bs_results":     None,
        "cf_results":     None,
        "composite_score": 0.0,
        "reasoning_label": None,
        "reasoning_text":  None,
        "status":          "STARTED",
        "error":           None,
        "logs":            [f"Starting fundamental scoring for {symbol}"],
    }

    # ── Stage 1: Fetch ────────────────────────────────────────────────────────
    try:
        statements_data = await fetch_statements(stock_id, period_type, db)
        state["statements_data"] = statements_data
        state["logs"].append(f"Fetched statements: {list(statements_data.keys())}")
    except Exception as exc:
        logger.exception(f"[scorer] {symbol} fetch failed")
        state["status"] = "FAILED"
        state["error"]  = str(exc)[:500]
        return state

    # ── Stage 2: Compute ──────────────────────────────────────────────────────
    compute_result = compute_scores_node(state)
    if compute_result.get("status") == "FAILED":
        state["status"] = "FAILED"
        state["error"]  = compute_result.get("error", "Compute stage failed")
        return state

    state.update(compute_result)
    state["logs"].append(f"Computed composite_score={state['composite_score']:.2f}")

    # ── Stage 3: Reason ───────────────────────────────────────────────────────
    reason_result = await generate_reasoning_node(state)
    state.update(reason_result)
    state["logs"].append(f"Reasoning label: {state.get('reasoning_label')}")

    # ── Stage 4: Persist ──────────────────────────────────────────────────────
    persist_result = await persist_scores_node(state, db)
    state.update(persist_result)

    if state.get("status") == "FAILED":
        logger.error(f"[scorer] {symbol} persist failed: {state.get('error')}")
        return state

    state["status"] = "COMPLETED"
    state["logs"].append("Persisted to fundamental_scores")
    logger.info(f"[scorer] {symbol} completed — score={state['composite_score']:.2f} label={state.get('reasoning_label')}")

    return state
