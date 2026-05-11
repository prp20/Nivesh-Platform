"""Persist node — saves comparison result to agent_fund_comparison table."""
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def persist_comparison(state: dict, session: AsyncSession) -> dict:
    if state.get("status") == "FAILED":
        return {}

    try:
        await session.execute(
            text("""
                INSERT INTO agent_fund_comparison
                    (comparison_id, fund_codes, metrics_matrix, rankings,
                     winner_scheme_code, ranked_verdict, narrative, status)
                VALUES
                    (:cid, :codes, :matrix, :rankings,
                     :winner, :verdict, :narrative, 'COMPLETED')
            """),
            {
                "cid": state["comparison_id"],
                "codes": json.dumps(state["fund_codes"]),
                "matrix": json.dumps(state["metrics_matrix"]),
                "rankings": json.dumps(state["rankings"]),
                "winner": state.get("winner_code"),
                "verdict": json.dumps(state.get("ranked_verdict", [])),
                "narrative": state.get("narrative", ""),
            },
        )
        await session.commit()
        return {
            "status": "PERSISTED",
            "logs": state["logs"] + [f"Comparison {state['comparison_id']} persisted"],
        }

    except Exception as e:
        logger.error(f"Failed to persist comparison: {e}")
        await session.rollback()
        return {
            "status": "FAILED",
            "error": f"Persist failed: {e}",
            "logs": state["logs"] + [f"Persist error: {e}"],
        }
