"""Persist node — saves recommendation to agent_stock_recommendation."""
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def persist_recommendation(state: dict, session: AsyncSession) -> dict:
    if state.get("status") == "FAILED":
        return {}

    try:
        await session.execute(
            text("""
                INSERT INTO agent_stock_recommendation
                    (symbol, signal, confidence, time_horizon,
                     entry_price_low, entry_price_high, target_price, stop_loss,
                     key_catalysts, key_risks, recommendation_text,
                     stock_analysis_id, status)
                VALUES
                    (:symbol, :signal, :confidence, :horizon,
                     :ep_low, :ep_high, :target, :stop,
                     :catalysts, :risks, :rec_text,
                     :analysis_id, 'COMPLETED')
            """),
            {
                "symbol": state["symbol"],
                "signal": state.get("signal"),
                "confidence": state.get("confidence"),
                "horizon": state.get("time_horizon"),
                "ep_low": state.get("entry_price_low"),
                "ep_high": state.get("entry_price_high"),
                "target": state.get("target_price"),
                "stop": state.get("stop_loss"),
                "catalysts": json.dumps(state.get("key_catalysts", [])),
                "risks": json.dumps(state.get("key_risks", [])),
                "rec_text": state.get("recommendation_text"),
                "analysis_id": state.get("stock_analysis_id"),
            },
        )
        await session.commit()

        return {
            "status": "PERSISTED",
            "logs": state["logs"] + ["Recommendation persisted to agent_stock_recommendation"],
        }

    except Exception as e:
        logger.error(f"Failed to persist recommendation for {state['symbol']}: {e}")
        await session.rollback()
        return {
            "status": "FAILED",
            "error": f"Persist failed: {e}",
            "logs": state["logs"] + [f"Persist error: {e}"],
        }
