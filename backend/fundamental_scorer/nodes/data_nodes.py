import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from app.models import FinancialStatement, FundamentalScore
from ..state import ScoringState
import logging

logger = logging.getLogger(__name__)

async def fetch_statements(stock_id: int, period_type: str, db: AsyncSession) -> Dict[str, List[Dict[str, Any]]]:
    """Pure helper to fetch statements from DB."""
    query = sa.select(FinancialStatement).where(
        FinancialStatement.stock_id == stock_id,
        FinancialStatement.period_type == period_type
    ).order_by(FinancialStatement.period_end.asc())
    
    result = await db.execute(query)
    statements = result.scalars().all()
    
    grouped_data = {"PL": [], "BS": [], "CF": []}
    for stmt in statements:
        if stmt.statement_type in grouped_data:
            grouped_data[stmt.statement_type].append({
                **stmt.data,
                "period_end": stmt.period_end
            })
    return grouped_data

async def fetch_financials_node(state: ScoringState, db: AsyncSession) -> Dict[str, Any]:
    """LangGraph node for fetching financials."""
    stock_id = state['stock_id']
    period_type = state.get('period_type', 'annual')
    
    try:
        grouped_data = await fetch_statements(stock_id, period_type, db)
        total_count = sum(len(v) for v in grouped_data.values())
        
        if total_count == 0:
            return {
                "status": "FAILED",
                "error": f"No {period_type} financial statements found in database for stock_id {stock_id}. Run a fundamental scrape first.",
                "logs": state.get("logs", []) + ["Fetch failed: 0 statements found"]
            }

        return {
            "statements_data": grouped_data,
            "status": "FETCHED",
            "logs": state.get("logs", []) + [f"Fetched {total_count} statements"]
        }
    except Exception as e:
        logger.error(f"Error fetching financials: {e}")
        return {
            "status": "FAILED",
            "error": str(e),
            "logs": state.get("logs", []) + [f"Fetch failed: {e}"]
        }

async def upsert_score(values: Dict[str, Any], db: AsyncSession):
    """Pure helper to upsert fundamental score."""
    stmt = insert(FundamentalScore).values(**values)
    on_conflict_stmt = stmt.on_conflict_do_update(
        constraint='uq_stock_period_version',
        set_={
            k: v for k, v in values.items() 
            if k not in ['stock_id', 'period_end', 'score_version']
        }
    )
    await db.execute(on_conflict_stmt)
    await db.commit()

async def persist_scores_node(state: ScoringState, db: AsyncSession) -> Dict[str, Any]:
    """LangGraph node for persisting scores."""
    if state.get("status") == "FAILED":
        return {}

    all_dates = []
    for stmts in state["statements_data"].values():
        for s in stmts:
            if "period_end" in s:
                all_dates.append(s["period_end"])
    
    latest_date = max(all_dates) if all_dates else None
    
    if not latest_date:
        return {"status": "FAILED", "error": "No period_end found to anchor score"}

    try:
        values = {
            "stock_id": state["stock_id"],
            "period_end": latest_date,
            "period_type": state["period_type"],
            "score_version": state["score_version"],
            
            "pl_score": state["pl_results"].get("score"),
            "bs_score": state["bs_results"].get("score"),
            "cf_score": state["cf_results"].get("score"),
            
            "pl_growth_score": state["pl_results"].get("sub_scores", {}).get("growth"),
            "pl_margin_score": state["pl_results"].get("sub_scores", {}).get("margin"),
            "pl_eps_score": state["pl_results"].get("sub_scores", {}).get("eps"),
            "pl_consistency_score": state["pl_results"].get("sub_scores", {}).get("consistency"),
            
            "bs_leverage_score": state["bs_results"].get("sub_scores", {}).get("leverage"),
            "bs_liquidity_score": state["bs_results"].get("sub_scores", {}).get("liquidity"),
            "bs_asset_score": state["bs_results"].get("sub_scores", {}).get("asset"),
            "bs_networth_score": state["bs_results"].get("sub_scores", {}).get("networth"),
            
            "cf_operating_score": state["cf_results"].get("sub_scores", {}).get("operating"),
            "cf_capex_score": state["cf_results"].get("sub_scores", {}).get("capex"),
            "cf_financing_score": state["cf_results"].get("sub_scores", {}).get("financing"),
            
            "composite_fundamental_score": state["composite_score"],
            "reasoning_label": state["reasoning_label"],
            "reasoning_text": state["reasoning_text"]
        }
        
        await upsert_score(values, db)
        
        return {
            "status": "COMPLETED",
            "logs": state.get("logs", []) + ["Scores persisted to database via upsert"]
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error persisting scores: {e}")
        return {
            "status": "FAILED",
            "error": str(e),
            "logs": state.get("logs", []) + [f"Persistence failed: {e}"]
        }

