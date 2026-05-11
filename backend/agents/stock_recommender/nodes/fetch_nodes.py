"""Fetch nodes — load prior analysis and momentum rating."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from agents.shared import db as agentdb

logger = logging.getLogger(__name__)


async def fetch_analysis(state: dict, session: AsyncSession) -> dict:
    """Load latest completed stock analysis. Fails if none exists."""
    analysis = await agentdb.fetch_latest_stock_analysis(session, state["symbol"])
    if not analysis:
        return {
            "status": "FAILED",
            "error": f"No completed analysis for '{state['symbol']}'. Run /agents/stock/{state['symbol']}/analyse first.",
            "logs": state["logs"] + ["No prior analysis found"],
        }

    # Also fetch latest price
    stock = await agentdb.fetch_stock(session, state["symbol"])
    price = None
    if stock:
        price_row = await agentdb.fetch_latest_price(session, stock["id"])
        price = float(price_row["close"]) if price_row and price_row.get("close") else None

    return {
        "stock_analysis": dict(analysis),
        "latest_price": price or 0.0,
        "stock_analysis_id": analysis.get("id"),
        "logs": state["logs"] + [f"Prior analysis loaded (id={analysis.get('id')})"],
    }


async def fetch_momentum(state: dict, session: AsyncSession) -> dict:
    """Load latest StockRating (composite momentum/quality rating)."""
    stock = await agentdb.fetch_stock(session, state["symbol"])
    rating = {}
    if stock:
        rating = await agentdb.fetch_stock_rating(session, stock["id"]) or {}

    return {
        "stock_rating": rating,
        "logs": state["logs"] + [f"Stock rating: {rating.get('rating_label', 'N/A')} ({rating.get('total_score', 'N/A')}/100)"],
    }
