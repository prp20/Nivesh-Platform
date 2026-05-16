"""
Proxy router — /proxy/* → Render server API.

Pattern for every endpoint:
  1. Build cache_key for this request
  2. Check local cache — return immediately if fresh
  3. Try server — on success, update cache, return data
  4. On OfflineError — return stale cache with _offline flag, or 503

The response shapes are exactly what the server returns — no transformation.
The React UI already knows these shapes from the shared schemas package.

IMPORTANT: Route ordering matters in FastAPI.
  /proxy/funds/compare  MUST be declared BEFORE /proxy/funds/{scheme_code}
  /proxy/stocks/screener MUST be declared BEFORE /proxy/stocks/{symbol}
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..services.cache import get_cached, invalidate, make_cache_key, set_cached
from ..services.http_client import OfflineError, ServerClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/proxy", tags=["proxy"])


def _offline_wrap(data: dict) -> dict:
    """Attach an offline flag to any cached response served stale."""
    if isinstance(data, dict):
        return {**data, "_offline": True, "_stale": True}
    return data


# ── Mutual Funds ──────────────────────────────────────────────────────────────

@router.get("/funds/compare")
async def proxy_fund_compare(
    scheme_codes: str = Query(..., description="Comma-separated scheme codes"),
    db: AsyncSession = Depends(get_db),
):
    """
    Fund comparison — ComparisonResponse shape.
    Cache key uses sorted codes so AAAA,BBBB == BBBB,AAAA.
    Declared BEFORE /funds/{scheme_code} to avoid route shadowing.
    """
    codes_sorted = ",".join(sorted(scheme_codes.split(",")))
    cache_key = f"funds:compare:{codes_sorted}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get(
                "/api/v1/funds/compare",
                params={"scheme_codes": scheme_codes},
            )
        await set_cached(db, cache_key, data, settings.CACHE_TTL_FUND_DETAIL)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline and no cached data available")


@router.get("/funds/amcs")
async def proxy_fund_amcs(db: AsyncSession = Depends(get_db)):
    cache_key = "funds:amcs"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached
    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/v1/funds/amcs")
        await set_cached(db, cache_key, data, 86400)
        return data
    except OfflineError:
        return cached if cached else []


@router.get("/funds/categories")
async def proxy_fund_categories(db: AsyncSession = Depends(get_db)):
    cache_key = "funds:categories"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached
    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/v1/funds/categories")
        await set_cached(db, cache_key, data, 86400)
        return data
    except OfflineError:
        return cached if cached else []


@router.get("/funds/categories/{category}/subcategories")
async def proxy_fund_subcategories(
    category: str, db: AsyncSession = Depends(get_db)
):
    cache_key = f"funds:subcategories:{category}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached
    try:
        async with ServerClient(db) as client:
            data = await client.get(
                f"/api/v1/funds/categories/{category}/subcategories"
            )
        await set_cached(db, cache_key, data, 86400)
        return data
    except OfflineError:
        return cached if cached else []


@router.get("/funds")
async def proxy_fund_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """GET /api/v1/funds — all query params forwarded, result cached by param hash."""
    params = dict(request.query_params)
    cache_key = make_cache_key("funds:list", params)

    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/v1/funds", params=params)
        await set_cached(db, cache_key, data, settings.CACHE_TTL_FUND_LIST)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline and no cached data available")


@router.get("/funds/{scheme_code}/nav")
async def proxy_fund_nav(
    scheme_code: str,
    limit: int = Query(default=365),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"funds:nav:{scheme_code}:{limit}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get(
                f"/api/v1/funds/{scheme_code}/nav",
                params={"limit": limit},
            )
        await set_cached(db, cache_key, data, settings.CACHE_TTL_FUND_NAV)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


@router.get("/funds/{scheme_code}")
async def proxy_fund_detail(
    scheme_code: str, db: AsyncSession = Depends(get_db)
):
    cache_key = f"funds:detail:{scheme_code}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get(f"/api/v1/funds/{scheme_code}")
        await set_cached(db, cache_key, data, settings.CACHE_TTL_FUND_DETAIL)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


@router.get("/funds/{scheme_code}/similar")
async def proxy_fund_similar(
    scheme_code: str, db: AsyncSession = Depends(get_db)
):
    cache_key = f"funds:similar:{scheme_code}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached
    try:
        async with ServerClient(db) as client:
            data = await client.get(f"/api/v1/funds/{scheme_code}/similar")
        await set_cached(db, cache_key, data, 3600)
        return data
    except OfflineError:
        return cached if cached else []


# ── Benchmarks ────────────────────────────────────────────────────────────────

@router.get("/benchmarks")
async def proxy_benchmarks(
    request: Request, db: AsyncSession = Depends(get_db)
):
    params = dict(request.query_params)
    cache_key = make_cache_key("benchmarks:list", params)
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/v1/benchmarks", params=params)
        await set_cached(db, cache_key, data, settings.CACHE_TTL_BENCHMARKS)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


@router.get("/benchmarks/{code}")
async def proxy_benchmark_detail(
    code: str, db: AsyncSession = Depends(get_db)
):
    cache_key = f"benchmarks:detail:{code}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached
    try:
        async with ServerClient(db) as client:
            data = await client.get(f"/api/v1/benchmarks/{code}")
        await set_cached(db, cache_key, data, settings.CACHE_TTL_BENCHMARKS)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


@router.get("/benchmarks/{code}/nav")
async def proxy_benchmark_nav(
    code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    params = dict(request.query_params)
    cache_key = make_cache_key(f"benchmarks:nav:{code}", params)
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get(f"/api/v1/benchmark-navs/{code}", params=params)
        await set_cached(db, cache_key, data, settings.CACHE_TTL_BENCHMARKS)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


# ── Stocks ────────────────────────────────────────────────────────────────────

@router.get("/stocks/screener")
async def proxy_screener(
    request: Request, db: AsyncSession = Depends(get_db)
):
    """
    Stock screener — ScreenerResponse shape.
    Short TTL (15 min) because screener results are filter-sensitive.
    Declared BEFORE /stocks/{symbol} to avoid route shadowing.
    """
    params = dict(request.query_params)
    cache_key = make_cache_key("stocks:screener", params)
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/v1/stocks/screener", params=params)
        await set_cached(db, cache_key, data, settings.CACHE_TTL_SCREENER)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


@router.get("/stocks")
async def proxy_stock_list(
    request: Request, db: AsyncSession = Depends(get_db)
):
    params = dict(request.query_params)
    cache_key = make_cache_key("stocks:list", params)
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/v1/stocks", params=params)
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")

    try:
        await set_cached(db, cache_key, data, settings.CACHE_TTL_STOCK_LIST)
    except Exception as exc:
        logger.warning("[cache] failed to cache stocks:list — %s", exc)

    return data


@router.get("/stocks/search")
async def proxy_stock_search(
    q: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Stock symbol/name search. Declared BEFORE /stocks/{symbol} to avoid route shadowing."""
    cache_key = f"stocks:search:{q.upper()}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached
    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/v1/stocks/search", params={"q": q})
        await set_cached(db, cache_key, data, 300)
        return data
    except OfflineError:
        return cached if cached else {"results": []}


@router.get("/stocks/{symbol}/price")
async def proxy_stock_price(
    symbol: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """OHLCV price history. Supports interval=1d|1w|1mo and limit. 30-min TTL.
    Cache also invalidated when pipeline price triggers run for this symbol."""
    params = dict(request.query_params)
    cache_key = make_cache_key(f"stocks:price:{symbol.upper()}", params)
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get(f"/api/v1/stocks/{symbol.upper()}/price", params=params)
        await set_cached(db, cache_key, data, 1800)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


@router.get("/stocks/{symbol}/fundamentals")
async def proxy_stock_fundamentals(
    symbol: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Financial statements (PL/BS/CF). 12-hour TTL — changes only after screener scrape."""
    params = dict(request.query_params)
    cache_key = make_cache_key(f"stocks:fundamentals:{symbol.upper()}", params)
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get(f"/api/v1/stocks/{symbol.upper()}/fundamentals", params=params)
        await set_cached(db, cache_key, data, 43200)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")


@router.get("/stocks/{symbol}")
async def proxy_stock_detail(
    symbol: str, db: AsyncSession = Depends(get_db)
):
    cache_key = f"stocks:detail:{symbol.upper()}"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get(f"/api/v1/stocks/{symbol.upper()}")
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        raise HTTPException(503, "Server offline")

    try:
        await set_cached(db, cache_key, data, settings.CACHE_TTL_STOCK_DETAIL)
    except Exception as exc:
        logger.warning("[cache] failed to cache stocks:detail:%s — %s", symbol.upper(), exc)

    return data


# ── ETL / Pipeline Status ─────────────────────────────────────────────────────

@router.get("/sync/status")
async def proxy_sync_status(db: AsyncSession = Depends(get_db)):
    """Pipeline run status — short TTL, always try server first."""
    cache_key = "etl:status"
    cached, is_fresh = await get_cached(db, cache_key)
    if is_fresh:
        return cached

    try:
        async with ServerClient(db) as client:
            data = await client.get("/api/v1/sync/status")
        await set_cached(db, cache_key, data, settings.CACHE_TTL_ETL_STATUS)
        return data
    except OfflineError:
        if cached:
            return _offline_wrap(cached)
        return {"runs": [], "total": 0, "_offline": True}


# ── Pipeline Triggers (admin operations forwarded to server) ──────────────────
#
# After each successful trigger the stock detail cache for that symbol is
# invalidated so the next GET /proxy/stocks/{symbol} fetches fresh data from
# the server instead of serving stale SQLite cache.


async def _invalidate_stock_cache(db: AsyncSession, symbol: str) -> None:
    """Remove stock detail + price cache entries so next read hits server."""
    try:
        await invalidate(db, f"stocks:detail:{symbol.upper()}")
        await invalidate(db, f"stocks:price:{symbol.upper()}")
        logger.debug("[cache] invalidated stocks:detail + price for %s", symbol.upper())
    except Exception as exc:
        logger.warning("[cache] invalidation failed for %s: %s", symbol.upper(), exc)


@router.post("/pipeline/prices/refresh/{symbol}")
async def proxy_price_sync(symbol: str, db: AsyncSession = Depends(get_db)):
    """Deep price history sync for a single stock. Invalidates stock detail cache."""
    async with ServerClient(db) as client:
        result = await client.post(f"/api/v1/pipeline/prices/refresh/{symbol.upper()}")
    await _invalidate_stock_cache(db, symbol)
    return result


@router.post("/pipeline/metrics/price-refresh/{symbol}")
async def proxy_price_refresh(symbol: str, db: AsyncSession = Depends(get_db)):
    """Recompute PE/PB/PS ratios for a single stock. Invalidates stock detail cache."""
    async with ServerClient(db) as client:
        result = await client.post(f"/api/v1/pipeline/metrics/price-refresh/{symbol.upper()}")
    await _invalidate_stock_cache(db, symbol)
    return result


@router.post("/pipeline/technical/{symbol}")
async def proxy_technical_analysis(symbol: str, db: AsyncSession = Depends(get_db)):
    """Run technical analysis (RSI, MACD, etc.) for a single stock. Invalidates stock detail cache."""
    async with ServerClient(db) as client:
        result = await client.post(f"/api/v1/pipeline/technical/{symbol.upper()}")
    await _invalidate_stock_cache(db, symbol)
    return result


@router.post("/pipeline/screener/{symbol}")
async def proxy_screener_scrape(symbol: str, db: AsyncSession = Depends(get_db)):
    """Trigger screener.in fundamental scrape for a single stock. Invalidates stock detail cache."""
    async with ServerClient(db) as client:
        result = await client.post(f"/api/v1/pipeline/screener/{symbol.upper()}")
    await _invalidate_stock_cache(db, symbol)
    return result


@router.post("/pipeline/ratings/{symbol}")
async def proxy_rating_compute(symbol: str, db: AsyncSession = Depends(get_db)):
    """Recompute composite rating for a single stock. Invalidates stock detail cache."""
    async with ServerClient(db) as client:
        result = await client.post(f"/api/v1/pipeline/ratings/{symbol.upper()}")
    await _invalidate_stock_cache(db, symbol)
    return result
