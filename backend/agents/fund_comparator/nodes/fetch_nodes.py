"""Fetch nodes for the fund comparator graph."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from agents.shared import db as agentdb

logger = logging.getLogger(__name__)


async def validate_inputs(state: dict, session: AsyncSession) -> dict:
    """Validate that 2-4 fund codes are provided and all exist."""
    codes = state.get("fund_codes", [])
    if not (2 <= len(codes) <= 4):
        return {
            "status": "FAILED",
            "error": f"Provide 2-4 fund codes (got {len(codes)})",
            "logs": state["logs"] + [f"Validation failed: {len(codes)} codes provided"],
        }
    missing = []
    for code in codes:
        master = await agentdb.fetch_fund_master(session, code)
        if not master:
            missing.append(code)
    if missing:
        return {
            "status": "FAILED",
            "error": f"Fund codes not found: {missing}",
            "logs": state["logs"] + [f"Missing funds: {missing}"],
        }
    return {
        "status": "VALIDATED",
        "logs": state["logs"] + [f"All {len(codes)} funds validated"],
    }


async def fetch_all_funds(state: dict, session: AsyncSession) -> dict:
    """Load master + metrics for each fund sequentially."""
    funds_data: dict = {}
    for code in state["fund_codes"]:
        master = await agentdb.fetch_fund_master(session, code)
        metrics = await agentdb.fetch_fund_metrics(session, code)
        if not metrics:
            return {
                "status": "FAILED",
                "error": f"No metrics for fund {code} — run sync first",
                "logs": state["logs"] + [f"Missing metrics for {code}"],
            }
        funds_data[code] = {"master": master, "metrics": metrics}

    return {
        "funds_data": funds_data,
        "logs": state["logs"] + [f"Loaded data for {len(funds_data)} funds"],
    }
