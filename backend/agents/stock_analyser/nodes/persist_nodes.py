"""Persist node — saves stock analysis to agent_stock_analysis."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def persist_analysis(state: dict, session: AsyncSession) -> dict:
    if state.get("status") == "FAILED":
        return {}

    try:
        result = await session.execute(
            text("""
                INSERT INTO agent_stock_analysis
                    (symbol, fundamental_score, fundamental_signal, fundamental_reasoning,
                     technical_signal, technical_reasoning,
                     valuation_signal, valuation_reasoning,
                     overall_health_score, full_narrative, status)
                VALUES
                    (:symbol, :fund_score, :fund_signal, :fund_reason,
                     :tech_signal, :tech_reason,
                     :val_signal, :val_reason,
                     :health, :narrative, 'COMPLETED')
            """),
            {
                "symbol": state["symbol"],
                "fund_score": state.get("fundamental_score"),
                "fund_signal": state.get("fundamental_signal"),
                "fund_reason": state.get("fundamental_reasoning"),
                "tech_signal": state.get("technical_signal"),
                "tech_reason": state.get("technical_reasoning"),
                "val_signal": state.get("valuation_signal"),
                "val_reason": state.get("valuation_reasoning"),
                "health": state.get("overall_health_score"),
                "narrative": state.get("full_narrative"),
            },
        )
        await session.commit()

        # Retrieve the inserted row ID
        row = await session.execute(
            text("""
                SELECT id FROM agent_stock_analysis
                WHERE symbol = :sym ORDER BY analysed_at DESC LIMIT 1
            """),
            {"sym": state["symbol"]},
        )
        r = row.fetchone()
        analysis_id = r[0] if r else None

        return {
            "stock_analysis_id": analysis_id,
            "status": "PERSISTED",
            "logs": state["logs"] + [f"Stock analysis persisted (id={analysis_id})"],
        }

    except Exception as e:
        logger.error(f"Failed to persist stock analysis for {state['symbol']}: {e}")
        await session.rollback()
        return {
            "status": "FAILED",
            "error": f"Persist failed: {e}",
            "logs": state["logs"] + [f"Persist error: {e}"],
        }
