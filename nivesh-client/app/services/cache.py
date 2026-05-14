"""
TTL cache backed by the cache_entries SQLite table.

All server API responses are stored here as raw JSON strings.
The proxy router checks the cache before making a server call.
If the cache is stale (or missing), the proxy fetches fresh data,
updates the cache, then returns the response.

If the server is offline, the proxy returns the stale cache
with an '_offline: true' flag in the response.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.cache import CacheEntry

logger = logging.getLogger(__name__)


def make_cache_key(prefix: str, params: dict = None) -> str:
    """
    Build a deterministic cache key from a prefix and optional params dict.
    Params dict is sorted before hashing so {a:1, b:2} == {b:2, a:1}.
    """
    if not params:
        return prefix
    param_str = json.dumps(params, sort_keys=True, default=str)
    hash_suffix = hashlib.md5(param_str.encode()).hexdigest()[:8]
    return f"{prefix}:{hash_suffix}"


async def get_cached(
    db: AsyncSession, cache_key: str
) -> tuple[Optional[Any], bool]:
    """
    Returns (data, is_fresh).
    data: parsed JSON from cache, or None if not cached at all
    is_fresh: True if within TTL, False if stale (serve anyway if offline)
    """
    result = await db.execute(
        select(CacheEntry).where(CacheEntry.cache_key == cache_key)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None, False

    fetched = row.fetched_at
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)

    age_seconds = (datetime.now(timezone.utc) - fetched).total_seconds()
    is_fresh = age_seconds < row.ttl_seconds

    try:
        data = json.loads(row.data_json)
    except (json.JSONDecodeError, TypeError):
        return None, False

    return data, is_fresh


async def set_cached(
    db: AsyncSession,
    cache_key: str,
    data: Any,
    ttl_seconds: int,
    server_generated_at: Optional[str] = None,
) -> None:
    """Write or overwrite a cache entry."""
    data_str = json.dumps(data, default=str)
    now = datetime.now(timezone.utc)

    stmt = sqlite_insert(CacheEntry).values(
        cache_key=cache_key,
        data_json=data_str,
        fetched_at=now,
        ttl_seconds=ttl_seconds,
        server_generated_at=server_generated_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["cache_key"],
        set_={
            "data_json":            data_str,
            "fetched_at":           now,
            "ttl_seconds":          ttl_seconds,
            "server_generated_at":  server_generated_at,
        },
    )
    await db.execute(stmt)
    await db.commit()


async def invalidate(db: AsyncSession, prefix: str) -> int:
    """Delete all cache entries whose key starts with prefix."""
    result = await db.execute(
        delete(CacheEntry).where(CacheEntry.cache_key.like(f"{prefix}%"))
    )
    await db.commit()
    return result.rowcount


async def cleanup_expired(db: AsyncSession) -> int:
    """
    Delete all cache entries past their TTL.
    Called by the APScheduler cleanup job every hour.
    """
    result = await db.execute(select(CacheEntry))
    rows = result.scalars().all()
    now = datetime.now(timezone.utc)
    expired_keys = []
    for row in rows:
        fetched = row.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        age = (now - fetched).total_seconds()
        if age >= row.ttl_seconds:
            expired_keys.append(row.cache_key)

    if expired_keys:
        await db.execute(
            delete(CacheEntry).where(CacheEntry.cache_key.in_(expired_keys))
        )
        await db.commit()
        logger.info(f"Cache cleanup: deleted {len(expired_keys)} expired entries")

    return len(expired_keys)
