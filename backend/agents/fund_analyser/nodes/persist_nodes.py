"""Persist node — saves fund analysis result to agent_fund_analysis table."""
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def persist_result(state: dict, session: AsyncSession) -> dict:
    """Upsert the analysis result into agent_fund_analysis."""
    if state.get("status") == "FAILED":
        return {}

    try:
        metrics = state.get("fund_metrics", {})
        # Build a lightweight snapshot of key metrics
        raw_snapshot = {
            k: (float(metrics[k]) if metrics.get(k) is not None else None)
            for k in [
                "current_nav", "cagr_3year", "cagr_5year", "sharpe_ratio",
                "sortino_ratio", "alpha", "beta", "maximum_drawdown",
                "tracking_error", "information_ratio", "expense_ratio", "aum_in_crores",
            ]
        }

        import json
        await session.execute(
            text("""
                INSERT INTO agent_fund_analysis
                    (scheme_code, composite_score, peer_percentile, category_rank,
                     category_size, verdict_label, verdict_text, key_strengths,
                     key_risks, raw_metrics, status)
                VALUES
                    (:scheme_code, :composite_score, :peer_percentile, :category_rank,
                     :category_size, :verdict_label, :verdict_text, :key_strengths,
                     :key_risks, :raw_metrics, 'COMPLETED')
            """),
            {
                "scheme_code": state["scheme_code"],
                "composite_score": state.get("composite_score"),
                "peer_percentile": state.get("peer_percentile"),
                "category_rank": state.get("category_rank"),
                "category_size": state.get("category_size"),
                "verdict_label": state.get("verdict_label"),
                "verdict_text": state.get("verdict_text"),
                "key_strengths": json.dumps(state.get("key_strengths", [])),
                "key_risks": json.dumps(state.get("key_risks", [])),
                "raw_metrics": json.dumps(raw_snapshot),
            },
        )
        await session.commit()

        return {
            "status": "PERSISTED",
            "logs": state["logs"] + ["Analysis persisted to agent_fund_analysis"],
        }

    except Exception as e:
        logger.error(f"Failed to persist fund analysis for {state['scheme_code']}: {e}")
        await session.rollback()
        return {
            "status": "FAILED",
            "error": f"Persist failed: {e}",
            "logs": state["logs"] + [f"Persist error: {e}"],
        }
