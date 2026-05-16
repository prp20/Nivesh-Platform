"""
Nivesh Client — FastAPI entry point.

Lifespan order:
  1. Run alembic upgrade head (auto-migrate SQLite on every startup)
  2. Verify SQLite is writable
  3. Register APScheduler: health_ping (60s) + cache_cleanup (hourly)
  4. Start scheduler + background cache warm task
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import AsyncSessionLocal, engine, get_db
from .models.auth import ServerConfig
from .models.cache import CacheEntry
from .routers import agent, auth, local, proxy, sync as sync_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 1. Run Alembic migrations (auto on every startup) ─────────────────────
    # Run in a thread executor: alembic.command.upgrade() is synchronous and
    # env.py uses engine_from_config (sync driver). Calling it directly from
    # an async context would block the event loop; run_in_executor avoids that.
    try:
        import functools
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, functools.partial(command.upgrade, alembic_cfg, "head")
        )
        logger.info("[startup] SQLite migrations up to date")
    except Exception as e:
        logger.error(f"[startup] Migration failed: {e}")
        raise

    # ── 2. Verify SQLite is writable ──────────────────────────────────────────
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info(f"[startup] SQLite DB ready: {settings.SQLITE_DB_PATH}")

    # ── 3. Register background scheduler jobs ─────────────────────────────────
    from .services.sync import cleanup_expired, ping_server

    async def _ping():
        async with AsyncSessionLocal() as db:
            online = await ping_server(db)
            logger.debug(f"[health_ping] {'online' if online else 'offline'}")

    async def _cleanup():
        async with AsyncSessionLocal() as db:
            count = await cleanup_expired(db)
            if count:
                logger.info(f"[cache_cleanup] Removed {count} expired entries")

    scheduler.add_job(
        _ping, "interval",
        seconds=settings.HEALTH_PING_INTERVAL_S,
        id="health_ping",
        replace_existing=True,
    )
    scheduler.add_job(
        _cleanup, "interval",
        seconds=settings.CACHE_CLEANUP_INTERVAL_S,
        id="cache_cleanup",
        replace_existing=True,
    )

    # ── Token refresh job ──────────────────────────────────────────────────────
    from .services.token_refresh import refresh_if_expiring_soon
    from .services.http_client import SessionExpiredError

    async def _token_refresh():
        async with AsyncSessionLocal() as db:
            try:
                refreshed = await refresh_if_expiring_soon(db, window_seconds=300)
                if refreshed:
                    logger.info("[token_refresh] Access token refreshed proactively")
            except SessionExpiredError:
                logger.warning(
                    "[token_refresh] Refresh token expired — user must log in again"
                )
            except Exception as exc:
                logger.error("[token_refresh] Unexpected error: %s", exc)

    scheduler.add_job(
        _token_refresh,
        "interval",
        minutes=5,
        id="token_refresh",
        replace_existing=True,
    )

    # ── Portfolio price enrichment job (market hours) ──────────────────────────
    from apscheduler.triggers.cron import CronTrigger
    from .services.portfolio_sync import sync_portfolio_prices, sync_watchlist_prices

    IST = pytz.timezone("Asia/Kolkata")

    async def _portfolio_sync():
        async with AsyncSessionLocal() as db:
            try:
                p = await sync_portfolio_prices(db)
                w = await sync_watchlist_prices(db)
                logger.info(
                    "[portfolio_sync] Scheduled run: %d holdings, %d watchlist refreshed",
                    p, w,
                )
            except Exception as exc:
                logger.error("[portfolio_sync] Scheduled run failed: %s", exc)

    scheduler.add_job(
        _portfolio_sync,
        CronTrigger(
            day_of_week="mon-fri",
            hour="9-16",
            minute="*/30",
            timezone=IST,
        ),
        id="portfolio_sync",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "[startup] APScheduler started "
        "(health_ping, cache_cleanup, token_refresh, portfolio_sync)"
    )

    # ── 4. Warm cache in background (non-blocking) ────────────────────────────
    async def _warm():
        await asyncio.sleep(2)  # Let the app finish starting first
        from .services.sync import run_startup_sync
        async with AsyncSessionLocal() as db:
            await run_startup_sync(db)

    asyncio.create_task(_warm())

    logger.info(f"[startup] Nivesh Client ready — port {settings.CLIENT_PORT}")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    await engine.dispose()
    logger.info("[shutdown] Nivesh Client stopped")


app = FastAPI(
    title="Nivesh Client API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",    # Always available — local dev tool
)

# CORS: allow the React dev server and any localhost origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(local.router)
app.include_router(proxy.router)
app.include_router(agent.router)
app.include_router(sync_router.router)


# ── System endpoints ──────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def client_health():
    """Lightweight health check. Always returns 200."""
    return {"status": "ok", "port": settings.CLIENT_PORT}


@app.get("/status", tags=["system"])
async def client_status(db: AsyncSession = Depends(get_db)):
    """
    Client health + connectivity summary.
    Consumed by the React UI to show the sync status bar.
    """
    result = await db.execute(
        select(ServerConfig).where(
            ServerConfig.key.in_(["is_online", "last_connected_at", "server_version"])
        )
    )
    config = {r.key: r.value for r in result.scalars().all()}

    count_result = await db.execute(
        select(func.count()).select_from(CacheEntry)
    )
    cache_count = count_result.scalar() or 0

    return {
        "client_version": "0.1.0",
        "is_online": config.get("is_online") == "true",
        "last_connected_at": config.get("last_connected_at"),
        "server_url": settings.NIVESH_SERVER_URL,
        "cached_resources": cache_count,
        "db_path": settings.SQLITE_DB_PATH,
    }
