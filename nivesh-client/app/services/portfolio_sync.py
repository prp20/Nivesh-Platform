# nivesh-client/app/services/portfolio_sync.py
"""
Portfolio and watchlist price enrichment.

sync_portfolio_prices(db):
    Reads all portfolio_holdings rows.
    For each holding, fetches the stock/fund detail from the server
    and writes it into the same cache key the proxy router uses.
    Skips symbols whose cache is already fresh.
    Aborts immediately on OfflineError — no point retrying if server is down.
    Per-symbol errors (404, bad data) are logged and skipped.
    Returns count of symbols successfully refreshed.

sync_watchlist_prices(db):
    Same pattern for watchlist items.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.user_data import PortfolioHolding, Watchlist
from ..services.cache import get_cached, set_cached
from ..services.http_client import OfflineError, ServerClient

logger = logging.getLogger(__name__)


async def sync_portfolio_prices(db: AsyncSession) -> int:
    """
    Pre-warm cache for all portfolio holdings.

    Cache keys used (same as proxy router):
      STOCK → 'stocks:detail:{SYMBOL}'
      FUND  → 'funds:detail:{SYMBOL}'   (symbol = scheme_code for funds)

    Returns count of symbols successfully refreshed.
    """
    result = await db.execute(select(PortfolioHolding))
    holdings = result.scalars().all()
    if not holdings:
        logger.debug("[portfolio_sync] No holdings — nothing to sync")
        return 0

    refreshed = 0
    for holding in holdings:
        sym = holding.symbol.upper()
        is_stock = holding.asset_type == "STOCK"
        cache_key = f"stocks:detail:{sym}" if is_stock else f"funds:detail:{sym}"
        server_path = f"/api/v1/stocks/{sym}" if is_stock else f"/api/v1/funds/{sym}"
        ttl = (
            settings.CACHE_TTL_STOCK_DETAIL
            if is_stock
            else settings.CACHE_TTL_FUND_DETAIL
        )

        # Skip if cache is already fresh — avoid redundant server calls
        _, is_fresh = await get_cached(db, cache_key)
        if is_fresh:
            logger.debug("[portfolio_sync] %s already cached — skipping", sym)
            continue

        try:
            async with ServerClient(db) as client:
                data = await client.get(server_path)
            await set_cached(db, cache_key, data, ttl)
            refreshed += 1
            logger.debug(
                "[portfolio_sync] Cached %s (%s)", sym, "stock" if is_stock else "fund"
            )
        except OfflineError:
            logger.warning(
                "[portfolio_sync] Server offline — aborting after %d/%d refreshed",
                refreshed,
                len(holdings),
            )
            break  # Don't hammer an offline server
        except Exception as exc:
            logger.warning(
                "[portfolio_sync] Failed to fetch %s: %s — continuing", sym, exc
            )
            # Per-symbol errors (404, parse error) don't abort the loop

    logger.info(
        "[portfolio_sync] Done — refreshed %d of %d holdings", refreshed, len(holdings)
    )
    return refreshed


async def sync_watchlist_prices(db: AsyncSession) -> int:
    """
    Pre-warm cache for all watchlist items.
    Same pattern as sync_portfolio_prices.

    Returns count of symbols successfully refreshed.
    """
    result = await db.execute(select(Watchlist))
    items = result.scalars().all()
    if not items:
        logger.debug("[watchlist_sync] Watchlist empty — nothing to sync")
        return 0

    refreshed = 0
    for item in items:
        sym = item.symbol.upper()
        is_stock = item.asset_type == "STOCK"
        cache_key = f"stocks:detail:{sym}" if is_stock else f"funds:detail:{sym}"
        server_path = f"/api/v1/stocks/{sym}" if is_stock else f"/api/v1/funds/{sym}"
        ttl = (
            settings.CACHE_TTL_STOCK_DETAIL
            if is_stock
            else settings.CACHE_TTL_FUND_DETAIL
        )

        _, is_fresh = await get_cached(db, cache_key)
        if is_fresh:
            logger.debug("[watchlist_sync] %s already cached — skipping", sym)
            continue

        try:
            async with ServerClient(db) as client:
                data = await client.get(server_path)
            await set_cached(db, cache_key, data, ttl)
            refreshed += 1
            logger.debug("[watchlist_sync] Cached %s", sym)
        except OfflineError:
            logger.warning(
                "[watchlist_sync] Server offline — aborting after %d/%d refreshed",
                refreshed,
                len(items),
            )
            break
        except Exception as exc:
            logger.warning(
                "[watchlist_sync] Failed to fetch %s: %s — continuing", sym, exc
            )

    logger.info(
        "[watchlist_sync] Done — refreshed %d of %d watchlist items",
        refreshed,
        len(items),
    )
    return refreshed
