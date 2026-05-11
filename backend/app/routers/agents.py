"""Agent analysis endpoints.

POST endpoints run the LangGraph workflow synchronously and return the result.
GET endpoints return the latest persisted result from the DB.

Routes:
  POST /agents/fund/{scheme_code}/analyse
  GET  /agents/fund/{scheme_code}/analysis
  POST /agents/fund/compare
  GET  /agents/fund/compare/{comparison_id}
  POST /agents/stock/{symbol}/analyse
  GET  /agents/stock/{symbol}/analysis
  POST /agents/stock/{symbol}/recommend
  GET  /agents/stock/{symbol}/recommendation
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class FundCompareRequest(BaseModel):
    fund_codes: list[str] = Field(..., min_length=2, max_length=4)


class AgentRunResponse(BaseModel):
    status: str
    error: Optional[str] = None
    logs: list[str] = []
    data: dict[str, Any] = {}


def _coerce_json_field(val: Any) -> Any:
    """DB may return JSON columns as strings (SQLite) or dicts (PostgreSQL)."""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    d = dict(row._mapping)
    # Coerce JSON string columns
    for k, v in d.items():
        if isinstance(v, str) and v and v[0] in ("{", "["):
            d[k] = _coerce_json_field(v)
    return d


# ---------------------------------------------------------------------------
# Fund analysis endpoints
# ---------------------------------------------------------------------------

@router.post("/fund/{scheme_code}/analyse", response_model=AgentRunResponse)
async def analyse_fund(
    scheme_code: str,
    force: bool = Query(False, description="Re-run even if recent analysis exists"),
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    """Run the multi-agent fund analysis pipeline."""
    # Check for recent analysis (within 24 hours) unless force=true
    if not force:
        existing = await db.execute(
            text("""
                SELECT id FROM agent_fund_analysis
                WHERE scheme_code = :code AND status = 'COMPLETED'
                  AND analysed_at > datetime('now', '-24 hours')
                ORDER BY analysed_at DESC LIMIT 1
            """),
            {"code": scheme_code},
        )
        if existing.fetchone():
            return AgentRunResponse(
                status="SKIPPED",
                data={"message": "Recent analysis exists. Use ?force=true to re-run."},
            )

    from agents.fund_analyser.graph import run_fund_analyser
    result = await run_fund_analyser(scheme_code, db)

    return AgentRunResponse(
        status=result.get("status", "UNKNOWN"),
        error=result.get("error"),
        logs=result.get("logs", []),
        data={
            "scheme_code": scheme_code,
            "composite_score": result.get("composite_score"),
            "peer_percentile": result.get("peer_percentile"),
            "category_rank": result.get("category_rank"),
            "category_size": result.get("category_size"),
            "verdict_label": result.get("verdict_label"),
            "verdict_text": result.get("verdict_text"),
            "key_strengths": result.get("key_strengths", []),
            "key_risks": result.get("key_risks", []),
        },
    )


@router.get("/fund/{scheme_code}/analysis")
async def get_fund_analysis(
    scheme_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the latest persisted fund analysis."""
    row = await db.execute(
        text("""
            SELECT * FROM agent_fund_analysis
            WHERE scheme_code = :code AND status = 'COMPLETED'
            ORDER BY analysed_at DESC LIMIT 1
        """),
        {"code": scheme_code},
    )
    result = row.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail=f"No analysis found for fund {scheme_code}")
    return _row_to_dict(result)


# ---------------------------------------------------------------------------
# Fund comparison endpoints
# ---------------------------------------------------------------------------

@router.post("/fund/compare", response_model=AgentRunResponse)
async def compare_funds(
    body: FundCompareRequest,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    """Run multi-fund comparison (2–4 funds)."""
    from agents.fund_comparator.graph import run_fund_comparator
    result = await run_fund_comparator(body.fund_codes, db)

    return AgentRunResponse(
        status=result.get("status", "UNKNOWN"),
        error=result.get("error"),
        logs=result.get("logs", []),
        data={
            "comparison_id": result.get("comparison_id"),
            "fund_codes": result.get("fund_codes", []),
            "winner_code": result.get("winner_code"),
            "ranked_verdict": result.get("ranked_verdict", []),
            "narrative": result.get("narrative"),
            "metrics_matrix": result.get("metrics_matrix", {}),
            "rankings": result.get("rankings", {}),
        },
    )


@router.get("/fund/compare/{comparison_id}")
async def get_fund_comparison(
    comparison_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific fund comparison by UUID."""
    row = await db.execute(
        text("""
            SELECT * FROM agent_fund_comparison
            WHERE comparison_id = :cid
        """),
        {"cid": comparison_id},
    )
    result = row.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail=f"Comparison {comparison_id} not found")
    return _row_to_dict(result)


# ---------------------------------------------------------------------------
# Stock analysis endpoints
# ---------------------------------------------------------------------------

@router.post("/stock/{symbol}/analyse", response_model=AgentRunResponse)
async def analyse_stock(
    symbol: str,
    force: bool = Query(False, description="Re-run even if recent analysis exists"),
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    """Run the multi-agent stock analysis pipeline."""
    symbol = symbol.upper()

    if not force:
        existing = await db.execute(
            text("""
                SELECT id FROM agent_stock_analysis
                WHERE symbol = :sym AND status = 'COMPLETED'
                  AND analysed_at > datetime('now', '-24 hours')
                ORDER BY analysed_at DESC LIMIT 1
            """),
            {"sym": symbol},
        )
        if existing.fetchone():
            return AgentRunResponse(
                status="SKIPPED",
                data={"message": "Recent analysis exists. Use ?force=true to re-run."},
            )

    from agents.stock_analyser.graph import run_stock_analyser
    result = await run_stock_analyser(symbol, db)

    return AgentRunResponse(
        status=result.get("status", "UNKNOWN"),
        error=result.get("error"),
        logs=result.get("logs", []),
        data={
            "symbol": symbol,
            "fundamental_score": result.get("fundamental_score"),
            "fundamental_signal": result.get("fundamental_signal"),
            "fundamental_reasoning": result.get("fundamental_reasoning"),
            "technical_signal": result.get("technical_signal"),
            "technical_reasoning": result.get("technical_reasoning"),
            "valuation_signal": result.get("valuation_signal"),
            "valuation_reasoning": result.get("valuation_reasoning"),
            "overall_health_score": result.get("overall_health_score"),
            "full_narrative": result.get("full_narrative"),
            "stock_analysis_id": result.get("stock_analysis_id"),
        },
    )


@router.get("/stock/{symbol}/analysis")
async def get_stock_analysis(
    symbol: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the latest persisted stock analysis."""
    symbol = symbol.upper()
    row = await db.execute(
        text("""
            SELECT * FROM agent_stock_analysis
            WHERE symbol = :sym AND status = 'COMPLETED'
            ORDER BY analysed_at DESC LIMIT 1
        """),
        {"sym": symbol},
    )
    result = row.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail=f"No analysis found for stock {symbol}")
    return _row_to_dict(result)


# ---------------------------------------------------------------------------
# Stock recommendation endpoints
# ---------------------------------------------------------------------------

@router.post("/stock/{symbol}/recommend", response_model=AgentRunResponse)
async def recommend_stock(
    symbol: str,
    force: bool = Query(False, description="Re-run even if recent recommendation exists"),
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
):
    """Run the stock BUY/HOLD/SELL recommendation pipeline."""
    symbol = symbol.upper()

    if not force:
        existing = await db.execute(
            text("""
                SELECT id FROM agent_stock_recommendation
                WHERE symbol = :sym AND status = 'COMPLETED'
                  AND recommended_at > datetime('now', '-24 hours')
                ORDER BY recommended_at DESC LIMIT 1
            """),
            {"sym": symbol},
        )
        if existing.fetchone():
            return AgentRunResponse(
                status="SKIPPED",
                data={"message": "Recent recommendation exists. Use ?force=true to re-run."},
            )

    from agents.stock_recommender.graph import run_stock_recommender
    result = await run_stock_recommender(symbol, db)

    return AgentRunResponse(
        status=result.get("status", "UNKNOWN"),
        error=result.get("error"),
        logs=result.get("logs", []),
        data={
            "symbol": symbol,
            "signal": result.get("signal"),
            "confidence": result.get("confidence"),
            "time_horizon": result.get("time_horizon"),
            "entry_price_low": result.get("entry_price_low"),
            "entry_price_high": result.get("entry_price_high"),
            "target_price": result.get("target_price"),
            "stop_loss": result.get("stop_loss"),
            "key_catalysts": result.get("key_catalysts", []),
            "key_risks": result.get("key_risks", []),
            "recommendation_text": result.get("recommendation_text"),
        },
    )


@router.get("/stock/{symbol}/recommendation")
async def get_stock_recommendation(
    symbol: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the latest persisted stock recommendation."""
    symbol = symbol.upper()
    row = await db.execute(
        text("""
            SELECT * FROM agent_stock_recommendation
            WHERE symbol = :sym AND status = 'COMPLETED'
            ORDER BY recommended_at DESC LIMIT 1
        """),
        {"sym": symbol},
    )
    result = row.fetchone()
    if not result:
        raise HTTPException(status_code=404, detail=f"No recommendation found for stock {symbol}")
    return _row_to_dict(result)
