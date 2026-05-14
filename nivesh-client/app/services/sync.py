"""
Background sync utilities.

ping_server(): Called by APScheduler every 60s — updates server_config.is_online.
sync_fund_list(): Refresh the main fund list cache if stale.
sync_benchmark_list(): Refresh benchmark master list if stale.
run_startup_sync(): Warm the cache on app startup.
cleanup_expired(): Delete expired cache rows (called by scheduler hourly).
"""

import logging

import httpx
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.auth import ServerConfig
from ..services.cache import cleanup_expired, get_cached, set_cached
from ..services.http_client import OfflineError, ServerClient

logger = logging.getLogger(__name__)


async def ping_server(db: AsyncSession) -> bool:
    """
    GET {server}/health and update server_config.is_online.
    Returns True if server responded OK.
    """
    try:
        async with httpx.AsyncClient(
            base_url=settings.NIVESH_SERVER_URL, timeout=10
        ) as client:
            resp = await client.get("/health")
            resp.raise_for_status()
            health = resp.json()
            is_online = health.get("status") in ("ok", "healthy")
    except Exception:
        is_online = False

    value = "true" if is_online else "false"
    stmt = sqlite_insert(ServerConfig).values(key="is_online", value=value)
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"], set_={"value": value}
    )
    await db.execute(stmt)
    await db.commit()
    return is_online


async def sync_fund_list(db: AsyncSession) -> bool:
    """Refresh the main fund list cache. Returns True if a fresh fetch occurred."""
    cache_key = "funds:list:default"
    _, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return False

    try:
        async with ServerClient(db) as client:
            data = await client.get(
                "/api/v1/funds", params={"limit": 100, "is_active": True}
            )
        await set_cached(db, cache_key, data, ttl_seconds=settings.CACHE_TTL_FUND_LIST)
        logger.info("Synced fund list")
        return True
    except OfflineError:
        logger.warning("sync_fund_list: server offline — using stale cache")
        return False


async def sync_benchmark_list(db: AsyncSession) -> bool:
    """Refresh benchmark master list."""
    cache_key = "benchmarks:list"
    _, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return False

    try:
        async with ServerClient(db) as client:
            data = await client.get(
                "/api/v1/benchmarks", params={"is_active": True}
            )
        await set_cached(db, cache_key, data, ttl_seconds=settings.CACHE_TTL_BENCHMARKS)
        logger.info("Synced benchmark list")
        return True
    except OfflineError:
        return False


async def run_startup_sync(db: AsyncSession) -> None:
    """
    Runs once on client startup (in background).
    Warms the cache with the most commonly accessed data.
    """
    logger.info("[startup] Warming cache...")
    await sync_fund_list(db)
    await sync_benchmark_list(db)
    logger.info("[startup] Cache warm complete")


# Re-export cleanup_expired so main.py can import it from here
__all__ = [
    "ping_server",
    "sync_fund_list",
    "sync_benchmark_list",
    "run_startup_sync",
    "cleanup_expired",
]
