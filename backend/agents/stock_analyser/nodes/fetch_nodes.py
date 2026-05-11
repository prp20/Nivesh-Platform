"""Fetch nodes for the stock analyser graph."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from agents.shared import db as agentdb

logger = logging.getLogger(__name__)


async def validate_stock(state: dict, session: AsyncSession) -> dict:
    stock = await agentdb.fetch_stock(session, state["symbol"])
    if not stock:
        return {
            "status": "FAILED",
            "error": f"Stock '{state['symbol']}' not found or inactive",
            "logs": state["logs"] + [f"Validation failed: {state['symbol']} not found"],
        }
    return {
        "stock_master": stock,
        "status": "VALIDATED",
        "logs": state["logs"] + [f"Stock validated: {stock.get('company_name')}"],
    }


async def fetch_stock_master(state: dict, session: AsyncSession) -> dict:
    stock_id = state["stock_master"]["id"]
    price = await agentdb.fetch_latest_price(session, stock_id)
    return {
        "latest_price": price or {},
        "logs": state["logs"] + [f"Latest price fetched: {price.get('close') if price else 'N/A'}"],
    }


async def fetch_all_data(state: dict, session: AsyncSession) -> dict:
    """Single node that loads ratios, financials, TA, and sector medians."""
    stock_id = state["stock_master"]["id"]
    sector = state["stock_master"].get("sector", "")

    ratios = await agentdb.fetch_latest_ratios(session, stock_id) or {}
    financials = await agentdb.fetch_latest_financials(session, stock_id)
    technical = await agentdb.fetch_latest_technical(session, stock_id) or {}
    sector_medians = await agentdb.fetch_sector_median_ratios(session, sector, stock_id)

    return {
        "financial_ratios": ratios,
        "financial_statements": financials,
        "technical_indicators": technical,
        "sector_medians": sector_medians,
        "logs": state["logs"] + [
            f"Data loaded: ratios={'yes' if ratios else 'empty'}, "
            f"financials={list(financials.keys())}, "
            f"TA={'yes' if technical else 'empty'}"
        ],
    }
