# nivesh-client/app/routers/sync.py
"""
Sync router — /sync/*

Endpoints:
  GET  /sync/client-status  → Cache health stats for React SyncStatusBar.
                               Reads local SQLite only — no server call.
  POST /sync/force           → Clear cache by resource type and immediately re-fetch.
                               resource: "funds"|"stocks"|"benchmarks"|"portfolio"|"watchlist"|"all"
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.auth import AuthToken, ServerConfig
from ..models.cache import CacheEntry
from ..models.user_data import PortfolioHolding, Watchlist
from ..services.cache import get_cached, invalidate
from ..services.portfolio_sync import sync_portfolio_prices, sync_watchlist_prices
from ..services.sync import run_startup_sync, sync_benchmark_list, sync_fund_list

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])

VALID_RESOURCES = {"funds", "stocks", "benchmarks", "portfolio", "watchlist", "all"}


class ForceSyncRequest(BaseModel):
    resource: str


@router.get("/client-status")
async def client_sync_status(db: AsyncSession = Depends(get_db)):
    """
    Cache health stats consumed by the React SyncStatusBar.
    All reads are local SQLite — no server call.
    """
    # ── Server connectivity state ─────────────────────────────────────────────
    cfg_result = await db.execute(
        select(ServerConfig).where(
            ServerConfig.key.in_(["is_online", "last_connected_at"])
        )
    )
    config = {r.key: r.value for r in cfg_result.scalars().all()}

    # ── Token expiry ──────────────────────────────────────────────────────────
    token_result = await db.execute(select(AuthToken).where(AuthToken.id == 1))
    token_row = token_result.scalar_one_or_none()
    token_expires_in: int | None = None
    if token_row and token_row.expires_at:
        exp = token_row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        token_expires_in = int((exp - datetime.now(timezone.utc)).total_seconds())

    # ── Cache entry counts ────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    all_entries = (await db.execute(select(CacheEntry))).scalars().all()
    total = len(all_entries)
    fresh = 0
    for e in all_entries:
        fetched = e.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        if (now - fetched).total_seconds() < e.ttl_seconds:
            fresh += 1

    # ── Holdings cache coverage ───────────────────────────────────────────────
    holdings = (await db.execute(select(PortfolioHolding))).scalars().all()
    holdings_cached = 0
    for h in holdings:
        sym = h.symbol.upper()
        key = f"stocks:detail:{sym}" if h.asset_type == "STOCK" else f"funds:detail:{sym}"
        _, is_fresh = await get_cached(db, key)
        if is_fresh:
            holdings_cached += 1

    # ── Watchlist cache coverage ──────────────────────────────────────────────
    watchlist = (await db.execute(select(Watchlist))).scalars().all()
    watchlist_cached = 0
    for w in watchlist:
        sym = w.symbol.upper()
        key = f"stocks:detail:{sym}" if w.asset_type == "STOCK" else f"funds:detail:{sym}"
        _, is_fresh = await get_cached(db, key)
        if is_fresh:
            watchlist_cached += 1

    return {
        "is_online": config.get("is_online") == "true",
        "last_connected_at": config.get("last_connected_at"),
        "token_expires_in_seconds": token_expires_in,
        "cache_entries_total": total,
        "cache_entries_fresh": fresh,
        "holdings_cached": holdings_cached,
        "holdings_total": len(holdings),
        "watchlist_cached": watchlist_cached,
        "watchlist_total": len(watchlist),
    }


@router.post("/force")
async def force_sync(body: ForceSyncRequest, db: AsyncSession = Depends(get_db)):
    """
    Clear cache for a resource type and immediately re-fetch from the server.

    resource="funds"       → clear funds:* cache + re-fetch fund list
    resource="stocks"      → clear stocks:* cache (re-fetched on next proxy request)
    resource="benchmarks"  → clear benchmarks:* cache + re-fetch
    resource="portfolio"   → clear cache for each held symbol + re-fetch prices
    resource="watchlist"   → clear cache for each watchlist symbol + re-fetch prices
    resource="all"         → clear all cache entries + full startup sync
    """
    if body.resource not in VALID_RESOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown resource '{body.resource}'. Valid: {sorted(VALID_RESOURCES)}",
        )

    cleared = 0
    refreshed = 0
    message = ""

    try:
        resource = body.resource

        if resource == "funds":
            cleared = await invalidate(db, "funds:")
            refreshed = 1 if await sync_fund_list(db) else 0
            message = f"Funds cache cleared ({cleared} entries) and refreshed"

        elif resource == "stocks":
            cleared = await invalidate(db, "stocks:")
            message = (
                f"Stocks cache cleared ({cleared} entries) — "
                "data re-fetches on next proxy request"
            )

        elif resource == "benchmarks":
            cleared = await invalidate(db, "benchmarks:")
            refreshed = 1 if await sync_benchmark_list(db) else 0
            message = f"Benchmarks cache cleared ({cleared} entries) and refreshed"

        elif resource == "portfolio":
            holdings = (await db.execute(select(PortfolioHolding))).scalars().all()
            for h in holdings:
                sym = h.symbol.upper()
                prefix = (
                    f"stocks:detail:{sym}"
                    if h.asset_type == "STOCK"
                    else f"funds:detail:{sym}"
                )
                cleared += await invalidate(db, prefix)
            refreshed = await sync_portfolio_prices(db)
            message = f"Portfolio: {cleared} cache entries cleared, {refreshed} symbols refreshed"

        elif resource == "watchlist":
            watchlist = (await db.execute(select(Watchlist))).scalars().all()
            for w in watchlist:
                sym = w.symbol.upper()
                prefix = (
                    f"stocks:detail:{sym}"
                    if w.asset_type == "STOCK"
                    else f"funds:detail:{sym}"
                )
                cleared += await invalidate(db, prefix)
            refreshed = await sync_watchlist_prices(db)
            message = f"Watchlist: {cleared} cache entries cleared, {refreshed} symbols refreshed"

        elif resource == "all":
            # invalidate("") matches LIKE "%" — clears every cache_entry row
            cleared = await invalidate(db, "")
            await run_startup_sync(db)
            p = await sync_portfolio_prices(db)
            w = await sync_watchlist_prices(db)
            refreshed = p + w
            message = (
                f"Full cache cleared ({cleared} entries). "
                f"Re-fetched: {refreshed} portfolio+watchlist symbols"
            )

    except Exception as exc:
        logger.error("force_sync failed for resource=%s: %s", body.resource, exc)
        return {
            "cleared": cleared,
            "refreshed": 0,
            "message": (
                f"Server offline — cache cleared ({cleared} entries), "
                "re-fetch pending on next request"
            ),
        }

    return {"cleared": cleared, "refreshed": refreshed, "message": message}
