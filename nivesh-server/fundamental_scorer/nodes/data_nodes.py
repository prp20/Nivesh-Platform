"""
fundamental_scorer/nodes/data_nodes.py — Fetch and Persist nodes.

Functions:
    fetch_statements(stock_id, period_type, db)     — Node 1: load financial statements
    persist_scores_node(state_dict, db)             — Node 4: save scores to DB
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FinancialStatement
from app.crud import upsert_fundamental_score

logger = logging.getLogger(__name__)


async def fetch_statements(
    stock_id: int,
    period_type: str,
    db: AsyncSession,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load financial statements for a stock from the database.

    Returns:
        {
          "PL": [{"period_end": "...", ...data fields...}, ...],
          "BS": [...],
          "CF": [...],
        }

    Raises:
        ValueError: if no annual financial statements found.
    """
    result = await db.execute(
        select(FinancialStatement)
        .where(
            FinancialStatement.stock_id == stock_id,
            FinancialStatement.period_type == period_type,
        )
        .order_by(FinancialStatement.period_end)
    )
    stmts = list(result.scalars().all())

    if not stmts:
        raise ValueError(
            f"No {period_type} financial statements found for stock_id={stock_id}"
        )

    statements_data: Dict[str, List[Dict[str, Any]]] = {"PL": [], "BS": [], "CF": []}
    for s in stmts:
        entry = {"period_end": s.period_end.isoformat(), **(s.data or {})}
        stmt_type = s.statement_type.upper()
        if stmt_type in statements_data:
            statements_data[stmt_type].append(entry)

    return statements_data


async def persist_scores_node(
    state_dict: Dict[str, Any],
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Persist scoring results from state_dict into the fundamental_scores table.

    Maps state_dict fields to FundamentalScore columns.
    Returns a dict with status='PERSISTED' or 'FAILED'.
    """
    try:
        pl  = state_dict.get("pl_results") or {}
        bs  = state_dict.get("bs_results") or {}
        cf  = state_dict.get("cf_results") or {}

        # Determine period_end from the latest PL statement
        stmts = state_dict.get("statements_data", {})
        pl_periods = [s.get("period_end") for s in stmts.get("PL", []) if s.get("period_end")]
        period_end_str = pl_periods[-1] if pl_periods else date.today().isoformat()
        period_end = date.fromisoformat(period_end_str)

        row = {
            "stock_id":       state_dict["stock_id"],
            "period_end":     period_end,
            "period_type":    state_dict.get("period_type", "annual"),
            "score_version":  state_dict.get("score_version", "v1.0"),

            # Statement-level scores
            "pl_score": pl.get("pl_score"),
            "bs_score": bs.get("bs_score"),
            "cf_score": cf.get("cf_score"),

            # PL sub-scores
            "pl_growth_score":      pl.get("growth_score"),
            "pl_margin_score":      pl.get("margin_score"),
            "pl_eps_score":         pl.get("eps_score"),
            "pl_consistency_score": pl.get("consistency_score"),

            # BS sub-scores
            "bs_leverage_score":  bs.get("leverage_score"),
            "bs_liquidity_score": bs.get("liquidity_score"),
            "bs_asset_score":     bs.get("asset_score"),
            "bs_networth_score":  bs.get("networth_score"),

            # CF sub-scores
            "cf_operating_score":  cf.get("operating_score"),
            "cf_capex_score":      cf.get("capex_score"),
            "cf_financing_score":  cf.get("financing_score"),

            # Composite
            "composite_fundamental_score": state_dict.get("composite_score"),
            "reasoning_label": state_dict.get("reasoning_label"),
            "reasoning_text":  state_dict.get("reasoning_text"),
        }

        await upsert_fundamental_score(db, row)
        logger.info(
            f"[persist_scores] stock_id={state_dict['stock_id']} "
            f"period={period_end} score={state_dict.get('composite_score')}"
        )
        return {"status": "PERSISTED"}

    except Exception as exc:
        logger.exception("[persist_scores] failed")
        return {"status": "FAILED", "error": str(exc)[:500]}
