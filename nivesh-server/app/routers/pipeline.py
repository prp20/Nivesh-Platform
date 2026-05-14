"""
Admin trigger endpoints for the stock data pipeline.

All endpoints require admin-level authentication (require_admin).
In dev mode (ENABLE_AUTH=False), requires ADMIN_TOKEN environment variable.
In production (ENABLE_AUTH=True), requires JWT token with admin role.

Trigger categories:
  /pipeline/prices/*    — OHLCV price ingestion (yfinance)
  /pipeline/metrics/*   — Price-dependent ratio refresh (PE/PB/PS)
  /pipeline/screener/*  — Screener.in fundamental scraping
  /pipeline/technical/* — Technical analysis (ta-lib)
  /pipeline/ratings/*   — Stock rating computation
  /pipeline/status      — Overall pipeline health

All sensitive operations are audited and logged.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.security import require_admin
from app.audit_log import AuditLog
from app.database import get_db, raw_connection, AsyncSessionLocal
from schemas.stocks import (
    FundamentalScoreRunRequest,
    BulkFundamentalScoreRequest,
    FundamentalScoreRead,
)
from app.schemas import ScoringStateSchema  # LangGraph internal state — kept local


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["Pipeline Triggers"])


# ─── Price Ingestion ──────────────────────────────────────────────────────────

@router.post("/prices/all", summary="Trigger daily price ingestion for all stocks")
async def trigger_price_ingestion(
    background_tasks: BackgroundTasks,
    admin: str = Depends(require_admin),
):
    """
    Fetches the last 5 trading days of OHLCV data for all active non-index stocks.
    Runs as a background task. Safe to re-run (uses ON CONFLICT DO UPDATE).

    Requires admin authentication. Operation is audited.
    """
    from pipeline.price_ingestion import run_daily_price_ingestion

    # Log the admin action
    await AuditLog.log_action(
        action=AuditLog.PIPELINE_TRIGGER,
        user=admin,
        resource="pipeline/prices/all",
        details={"job": "price_daily_ingestion"},
    )

    background_tasks.add_task(run_daily_price_ingestion)
    return {
        "message": "Price ingestion started in background",
        "job": "price_daily_ingestion",
    }


@router.post("/prices/indices", summary="Trigger price ingestion for indices only")
async def trigger_index_ingestion(
    background_tasks: BackgroundTasks,
    admin: str = Depends(require_admin),
):
    """
    Fetches the last 5 trading days for all active index instruments (is_index=TRUE).

    Requires admin authentication. Operation is audited.
    """
    from pipeline.price_ingestion import run_index_ingestion

    await AuditLog.log_action(
        action=AuditLog.PIPELINE_TRIGGER,
        user=admin,
        resource="pipeline/prices/indices",
        details={"job": "index_daily_ingestion"},
    )

    background_tasks.add_task(run_index_ingestion)
    return {
        "message": "Index ingestion started in background",
        "job": "index_daily_ingestion",
    }


@router.post("/prices/backfill", summary="Trigger 5-year price history backfill")
async def trigger_price_backfill(
    background_tasks: BackgroundTasks,
    period: str = Query("5y", regex="^(1y|2y|3y|5y)$"),
    admin: str = Depends(require_admin),
):
    """
    Backfills full price history for all active stocks.
    Use only for initial setup or after adding new stocks.
    This is a long-running operation (~10–30 minutes for 500 stocks).

    Requires admin authentication. Operation is audited. Be cautious about running
    during business hours as it consumes significant bandwidth.
    """
    from pipeline.price_ingestion import run_backfill

    await AuditLog.log_action(
        action=AuditLog.PIPELINE_TRIGGER,
        user=admin,
        resource="pipeline/prices/backfill",
        details={"period": period, "warning": "Long-running operation"},
    )

    background_tasks.add_task(run_backfill, period)
    return {
        "message": f"Price backfill ({period}) started in background",
        "job": "price_backfill",
        "warning": "This is a long-running operation. Monitor etl_runs table for status.",
    }


@router.post("/prices/refresh/{symbol}", summary="Trigger deep price sync for one stock")
async def trigger_price_refresh_one(
    symbol: str,
    period: str = Query("1y", regex="^(1mo|6mo|1y|2y|5y|max)$"),
    admin: str = Depends(require_admin),
):
    """
    Synchronously fetches historical price data for a single stock.
    Useful for correcting historical data errors or filling gaps.

    Requires admin authentication. Operation is audited.
    """
    from pipeline.price_ingestion import run_price_sync_one

    await AuditLog.log_action(
        action=AuditLog.PIPELINE_TRIGGER,
        user=admin,
        resource=f"pipeline/prices/refresh/{symbol}",
        details={"symbol": symbol.upper(), "period": period},
    )

    count = await run_price_sync_one(symbol, period)
    return {"symbol": symbol.upper(), "period": period, "records_upserted": count}


# ─── Price-Dependent Metrics ──────────────────────────────────────────────────

@router.post("/metrics/price-refresh/all", summary="Refresh PE/PB/PS for all stocks")
async def trigger_price_ratio_refresh_all(
    background_tasks: BackgroundTasks,
    admin: str = Depends(require_admin),
):
    """
    Recomputes price-dependent ratios (PE, PB, PS, dividend yield) for all active stocks.
    Reads latest close from price_data; reads EPS/book_value from stored financial_ratios.
    Does NOT touch quarterly metrics (ROE, ROCE, margins, etc.).
    """
    from pipeline.metric_recompute import recompute_price_dependent_ratios_all
    background_tasks.add_task(recompute_price_dependent_ratios_all)
    return {"message": "Price ratio refresh started in background", "job": "price_ratio_refresh_all"}


@router.post("/metrics/price-refresh/{symbol}", summary="Refresh PE/PB/PS for one stock")
async def trigger_price_ratio_refresh_one(
    symbol: str,
    admin: str = Depends(require_admin),
):
    """Synchronously refresh price-dependent ratios for a single stock. Returns updated values."""
    from pipeline.metric_recompute import recompute_price_dependent_ratios, _get_latest_close, _fetch_stocks_with_ratios
    from app.database import raw_connection

    sym = symbol.upper()
    async with raw_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM stocks WHERE symbol=$1 AND is_active=TRUE", sym
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Stock '{sym}' not found or inactive")

    stock_id = row["id"]
    close = await _get_latest_close(stock_id)
    if close is None:
        raise HTTPException(status_code=422, detail=f"No price data found for '{sym}'")

    result = await recompute_price_dependent_ratios(stock_id, close)
    return {"symbol": sym, "latest_close": close, "updated_ratios": result}


# ─── Screener.in Fundamental Scraping ─────────────────────────────────────────

@router.post("/screener/all", summary="Trigger screener.in scrape for all overdue stocks")
async def trigger_screener_scrape_all(
    background_tasks: BackgroundTasks,
    days_since_last: int = Query(90, ge=1, le=365),
    admin: str = Depends(require_admin),
):
    """
    Scrapes screener.in fundamentals for all stocks not updated in `days_since_last` days.
    Default: 90 days. Uses checksum deduplication — skips unchanged data.
    This is a slow operation (2–5 sec delay per stock to be polite to screener.in).
    After completion, triggers financial ratio recompute automatically.
    """
    from pipeline.fundamental_scraper import run_fundamental_scrape_all

    async def _scrape_then_ratios():
        await run_fundamental_scrape_all(days_since_last=days_since_last)
        from pipeline.ratio_engine import run_ratio_compute_all
        await run_ratio_compute_all()

    background_tasks.add_task(_scrape_then_ratios)
    return {
        "message": f"Screener scrape started (threshold: {days_since_last}d). Ratio recompute will follow automatically.",
        "job": "fundamental_scrape_all",
    }


@router.post("/screener/{symbol}", summary="Trigger screener.in scrape for a single stock")
async def trigger_screener_scrape_one(
    symbol: str,
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Bypass checksum and force re-scrape"),
    admin: str = Depends(require_admin),
):
    """
    Starts a screener.in scrape for a single stock as a background task.
    Returns immediately — poll GET /pipeline/status to track progress.
    Set force=true to bypass the checksum deduplication check.
    After a successful scrape, ratio recompute is triggered automatically.
    """
    from app.database import raw_connection

    sym = symbol.upper()
    async with raw_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM stocks WHERE symbol=$1 AND is_active=TRUE", sym
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Stock '{sym}' not found or inactive")

    stock_id = row["id"]

    async def _run_scrape_and_ratios():
        from pipeline.fundamental_scraper import run_fundamental_scrape_one
        from pipeline.ratio_engine import compute_ratios_for_stock
        from pipeline.metric_recompute import _get_latest_close
        try:
            await run_fundamental_scrape_one(sym, force=force)
            close = await _get_latest_close(stock_id)
            await compute_ratios_for_stock(stock_id, close)
        except Exception as e:
            logger.error(f"Background screener scrape failed for {sym}: {e}")

    background_tasks.add_task(_run_scrape_and_ratios)
    return {
        "symbol": sym,
        "message": "Fundamental scrape started in background. Poll GET /pipeline/status to track progress.",
        "job_name": "fundamental_scrape_single",
        "status": "STARTED",
        "force_rescrape": force,
    }


@router.get("/screener/status", summary="Show last scrape date and overdue stocks")
async def get_screener_status(
    overdue_days: int = Query(90, ge=1),
    admin: str = Depends(require_admin),
):
    """Returns last scrape date per stock and flags stocks overdue for scraping."""
    from app.database import raw_connection
    sql = """
        SELECT
            s.symbol,
            s.company_name,
            MAX(fs.scraped_at)::date AS last_scraped,
            CASE
                WHEN MAX(fs.scraped_at) IS NULL THEN 'NEVER'
                WHEN MAX(fs.scraped_at) < NOW() - ($1 || ' days')::INTERVAL THEN 'OVERDUE'
                ELSE 'OK'
            END AS scrape_status
        FROM stocks s
        LEFT JOIN financial_statements fs ON fs.stock_id = s.id
        WHERE s.is_active = TRUE AND s.is_index = FALSE
        GROUP BY s.id, s.symbol, s.company_name
        ORDER BY last_scraped ASC NULLS FIRST
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql, str(overdue_days))
    data = [dict(r) for r in rows]
    overdue = [r for r in data if r["scrape_status"] in ("OVERDUE", "NEVER")]
    return {
        "total_stocks": len(data),
        "overdue_count": len(overdue),
        "threshold_days": overdue_days,
        "stocks": data,
    }


# ─── Technical Analysis ───────────────────────────────────────────────────────

@router.post("/technical/all", summary="Run technical analysis for all stocks")
async def trigger_technical_analysis_all(
    background_tasks: BackgroundTasks,
    admin: str = Depends(require_admin),
):
    """
    Computes all TA indicators (SMA, EMA, RSI, MACD, Bollinger, ATR, ADX, Stochastic)
    for all active stocks from price_data and stores in technical_indicators.
    Runs as a background task. Safe to re-run.
    """
    from pipeline.technical_analysis import run_technical_analysis_all
    background_tasks.add_task(run_technical_analysis_all)
    return {"message": "Technical analysis started for all stocks", "job": "technical_analysis_all"}


@router.post("/technical/{symbol}", summary="Run technical analysis for a single stock")
async def trigger_technical_analysis_one(
    symbol: str,
    admin: str = Depends(require_admin),
):
    """
    Synchronously computes TA indicators for a single stock.
    Returns the computed indicator values on success.
    Requires at least 20 rows in price_data (200 recommended for full SMA-200).
    """
    from pipeline.technical_analysis import run_technical_analysis_one
    sym = symbol.upper()
    try:
        result = await run_technical_analysis_one(sym)
        if not result:
            raise HTTPException(
                status_code=422,
                detail=f"Insufficient price data for '{sym}'. Run a price backfill first."
            )
        return {"symbol": sym, "indicators": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"TA failed for {sym}: {e}")
        raise HTTPException(status_code=500, detail=f"Technical analysis failed: {e}")


@router.get("/technical/status", summary="Show TA computation status per stock")
async def get_technical_status(admin: str = Depends(require_admin)):
    """Returns last TA computation date per stock; flags MISSING or STALE (>2 days old)."""
    from pipeline.technical_analysis import get_ta_status
    data = await get_ta_status()
    missing = [r for r in data if r["status"] == "MISSING"]
    stale   = [r for r in data if r["status"] == "STALE"]
    return {
        "total_stocks": len(data),
        "missing_count": len(missing),
        "stale_count": len(stale),
        "stocks": data,
    }


# ─── Ratings ─────────────────────────────────────────────────────────────────

@router.post("/ratings/all", summary="Recompute stock ratings for all stocks")
async def trigger_rating_compute_all(
    background_tasks: BackgroundTasks,
    admin: str = Depends(require_admin),
):
    """
    Recomputes composite stock ratings (fundamental + valuation + technical + momentum + shareholding).
    Runs as a background task. Requires financial_ratios and/or technical_indicators to be populated.
    """
    from pipeline.rating_engine import run_rating_compute_all
    background_tasks.add_task(run_rating_compute_all)
    return {"message": "Rating computation started for all stocks", "job": "rating_compute_all"}


@router.post("/ratings/{symbol}", summary="Recompute rating for a single stock")
async def trigger_rating_compute_one(
    symbol: str,
    admin: str = Depends(require_admin),
):
    """Synchronously recomputes the composite rating for one stock. Returns score breakdown."""
    from pipeline.rating_engine import compute_rating_for_stock
    from app.database import raw_connection

    sym = symbol.upper()
    async with raw_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM stocks WHERE symbol=$1 AND is_active=TRUE", sym
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Stock '{sym}' not found or inactive")

    try:
        result = await compute_rating_for_stock(row["id"], sym)
        return result
    except Exception as e:
        logger.error(f"Rating compute failed for {sym}: {e}")
        raise HTTPException(status_code=500, detail=f"Rating compute failed: {e}")


# ─── Fundamental Scoring (LangGraph) ──────────────────────────────────────────

@router.post("/fundamentals/stage/fetch/{symbol}", response_model=ScoringStateSchema, summary="Fetch: Trigger only the Fetch agent")
async def trigger_fetch_stage(
    symbol: str,
    period_type: str = "annual",
    admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Fetches raw financial statements for a stock. First stage of fundamental scoring."""
    from fundamental_scorer.nodes.data_nodes import fetch_statements
    
    sym = symbol.upper()
    row = await db.execute(sa.text("SELECT id FROM stocks WHERE symbol=:sym AND is_active=TRUE"), {"sym": sym})
    stock = row.fetchone()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{sym}' not found")

    try:
        data = await fetch_statements(stock.id, period_type, db)
        return {
            "stock_id": stock.id,
            "symbol": sym,
            "period_type": period_type,
            "score_version": "v1.0",
            "statements_data": data,
            "status": "FETCHED",
            "logs": [f"Granular fetch triggered for {sym}"]
        }
    except Exception as e:
        logger.error(f"Fetch stage failed for {sym}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fundamentals/stage/compute", response_model=ScoringStateSchema, summary="Compute: Trigger only the Scoring engine")
async def trigger_compute_stage(
    state: ScoringStateSchema,
    admin: str = Depends(require_admin)
):
    """Runs deterministic calculations on provided financial statements."""
    from fundamental_scorer.nodes.compute_nodes import compute_scores_node
    # Convert Pydantic model to dict for node consumption (TypedDict)
    state_dict = state.model_dump()
    result = compute_scores_node(state_dict)
    return {**state_dict, **result}


@router.post("/fundamentals/stage/reason", response_model=ScoringStateSchema, summary="Reason: Trigger only the AI Reasoning agent")
async def trigger_reason_stage(
    state: ScoringStateSchema,
    admin: str = Depends(require_admin)
):
    """Generates qualitative AI reasoning based on computed scores."""
    from fundamental_scorer.nodes.reasoning_nodes import generate_reasoning_node
    state_dict = state.model_dump()
    result = await generate_reasoning_node(state_dict)
    return {**state_dict, **result}


@router.post("/fundamentals/stage/persist", response_model=ScoringStateSchema, summary="Persist: Save results to database")
async def trigger_persist_stage(
    state: ScoringStateSchema,
    admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Saves the scoring results to the database."""
    from fundamental_scorer.nodes.data_nodes import persist_scores_node
    state_dict = state.model_dump()
    result = await persist_scores_node(state_dict, db)
    return {**state_dict, **result}


@router.post("/fundamentals/run/{symbol}", summary="Full Run: Trigger end-to-end scoring pipeline")
async def trigger_fundamental_scoring_one(
    symbol: str,
    period_type: str = "annual",
    score_version: str = "v1.0",
    admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Synchronously runs the full Fetch -> Compute -> Reason -> Persist pipeline."""
    from fundamental_scorer.graph import run_fundamental_scorer
    
    sym = symbol.upper()
    row = await db.execute(sa.text("SELECT id FROM stocks WHERE symbol=:sym AND is_active=TRUE"), {"sym": sym})
    stock = row.fetchone()
    
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{sym}' not found")

    result = await run_fundamental_scorer(stock.id, sym, db, period_type=period_type, score_version=score_version)
    
    if result.get("status") == "FAILED":
        error_msg = result.get("error", "Unknown error")
        # Distinguish between data issues (422) and code/infra issues (500)
        status_code = 422 if any(msg in error_msg for msg in ["No annual financial", "Insufficient history"]) else 500
        raise HTTPException(status_code=status_code, detail=f"Scoring failed: {error_msg}")
        
    return result


@router.post("/funds/run/{scheme_code}", summary="Fund Run: Trigger end-to-end fund scoring pipeline")
async def trigger_fund_scoring_one(
    scheme_code: str,
    admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Synchronously runs the Fund Fetch -> Reason pipeline."""
    from fund_scorer.graph import run_fund_scorer
    
    result = await run_fund_scorer(scheme_code, db)
    
    if result.get("status") == "FAILED":
        error_msg = result.get("error", "Unknown error")
        raise HTTPException(status_code=422, detail=f"Fund scoring failed: {error_msg}")
        
    return result


@router.post("/fundamentals/bulk-run", summary="Bulk Run: Trigger scoring for multiple stocks")
async def trigger_fundamental_scoring_bulk(
    req: BulkFundamentalScoreRequest,
    background_tasks: BackgroundTasks,
    admin: str = Depends(require_admin)
):
    """Starts fundamental scoring for multiple stocks in the background."""
    from fundamental_scorer.graph import run_fundamental_scorer

    async def _run_bulk():
        async with AsyncSessionLocal() as db:
            if req.symbols:
                rows = await db.execute(
                    sa.text("SELECT id, symbol FROM stocks WHERE symbol = ANY(:symbols)"), 
                    {"symbols": list(req.symbols)}
                )
            else:
                rows = await db.execute(sa.text("SELECT id, symbol FROM stocks WHERE is_active=TRUE"))
            
            stocks = rows.fetchall()
            
            for stock in stocks:
                try:
                    # Reuse the existing session for all stocks in this bulk run
                    await run_fundamental_scorer(
                        stock.id, stock.symbol, db, 
                        period_type=req.period_type, 
                        score_version=req.score_version
                    )
                    # Commit after each stock to persist progress
                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    logger.error(f"Bulk scoring failed for {stock.symbol}: {e}")


    background_tasks.add_task(_run_bulk)
    return {
        "message": f"Bulk scoring started for {len(req.symbols) if req.symbols else 'all active'} stocks",
        "period_type": req.period_type,
        "score_version": req.score_version
    }


# ─── Overall Pipeline Status ──────────────────────────────────────────────────

@router.get("/status", summary="Overall pipeline health and live progress polling")
async def get_pipeline_status(admin: str = Depends(require_admin)):
    """Shows last run time, status, and live record counts (progress) for all pipeline jobs."""
    from app.database import raw_connection
    sql = """
        SELECT DISTINCT ON (pipeline_name)
            pipeline_name AS job_name,
            entity_id,
            status,
            started_at,
            ended_at,
            records_in,
            records_out,
            EXTRACT(EPOCH FROM (COALESCE(ended_at, NOW()) - started_at))::int AS duration_sec,
            error_msg
        FROM etl_runs
        ORDER BY pipeline_name, started_at DESC
    """
    rows = []
    try:
        async with raw_connection() as conn:
            rows = await conn.fetch(sql)
    except Exception as e:
        # Graceful fallback for any connection/pool issues
        logger.error(f"Failed to fetch pipeline status: {str(e)}", exc_info=True)
    
    jobs = []


    for r in rows:
        job = dict(r)
        # Calculate progress percentage if records_in is known
        if job["records_in"] and job["records_in"] > 0:
            job["progress_pct"] = round((job["records_out"] / job["records_in"]) * 100, 1)
        else:
            job["progress_pct"] = None if job["status"] == "RUNNING" else 100.0
        jobs.append(job)

    return {"jobs": jobs}

