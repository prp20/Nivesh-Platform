"""Fetch nodes for the fund analyser graph — each does exactly one DB query."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from agents.shared import db as agentdb

logger = logging.getLogger(__name__)


async def validate_fund(state: dict, session: AsyncSession) -> dict:
    """Check the fund exists in fund_master."""
    master = await agentdb.fetch_fund_master(session, state["scheme_code"])
    if not master:
        return {
            "status": "FAILED",
            "error": f"Fund {state['scheme_code']} not found in fund_master",
            "logs": state["logs"] + [f"Validation failed: fund {state['scheme_code']} not found"],
        }
    return {
        "fund_master": master,
        "status": "FETCHED",
        "logs": state["logs"] + [f"Fund validated: {master.get('scheme_name')}"],
    }


async def fetch_fund_metrics(state: dict, session: AsyncSession) -> dict:
    """Load FundMetrics row."""
    metrics = await agentdb.fetch_fund_metrics(session, state["scheme_code"])
    if not metrics:
        return {
            "status": "FAILED",
            "error": f"No metrics for fund {state['scheme_code']} — run sync first",
            "logs": state["logs"] + ["fetch_fund_metrics: no metrics row found"],
        }
    return {
        "fund_metrics": metrics,
        "logs": state["logs"] + ["Fund metrics fetched"],
    }


async def fetch_peers(state: dict, session: AsyncSession) -> dict:
    """Load same-category peers (top 50 by CAGR_3year)."""
    category = state["fund_master"].get("scheme_category", "")
    peers = await agentdb.fetch_peers(session, category, state["scheme_code"])
    return {
        "peer_metrics": peers,
        "logs": state["logs"] + [f"Fetched {len(peers)} peer funds in category '{category}'"],
    }
