import logging
import asyncpg
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings
 
logger = logging.getLogger(__name__)



def _async_url(url: str) -> str:
    """Ensure the URL always uses the asyncpg driver, regardless of what is set in .env."""
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return url.replace("://", "+asyncpg://", 1)
    return url


def _sync_url(url: str) -> str:
    """Strip the asyncpg driver prefix for use with raw asyncpg.connect()."""
    return url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres+asyncpg://", "postgres://")


_async_db_url = _async_url(settings.DATABASE_URL)
_sync_db_url = _sync_url(_async_db_url)

# Using Supabase Session Pooler (port 5432) which supports prepared statements.
engine = create_async_engine(
    _async_db_url,
    # Tuned for Supabase free tier: 60 direct / 200 pooler → 20 backend connections.
    # Keep pool small so restarts don't exhaust the limit.
    pool_size=5,
    max_overflow=3,
    pool_pre_ping=True,    # Drop stale connections before use
    pool_recycle=300,      # Recycle connections every 5 minutes
    echo=False,
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
session_factory = AsyncSessionLocal
Base = declarative_base()

_db_pool = None

async def init_db_pool():
    global _db_pool
    if _db_pool is None:
        # Check if we are in a PostgreSQL environment. asyncpg only supports postgres.
        # Tests often use SQLite which would cause asyncpg.create_pool to hang or fail.
        if not _sync_db_url.startswith(("postgresql://", "postgres://")):
            logger.warning(f"Skipping asyncpg pool initialization: Unsupported protocol in {_sync_db_url.split('://')[0]}")
            return None
            
        try:
            _db_pool = await asyncpg.create_pool(_sync_db_url, min_size=5, max_size=20, timeout=10)
        except Exception as e:
            logger.error(
                "Failed to initialize asyncpg pool: %s: %s",
                type(e).__name__, repr(e),
                exc_info=True,
            )
            _db_pool = None
    return _db_pool


async def close_db_pool():
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None



async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def raw_connection():
    """Get a raw asyncpg connection for direct SQL operations (from pool)."""
    if _db_pool is None:
        await init_db_pool()
    
    if _db_pool is None:
        raise RuntimeError("Database connection pool is not initialized. Raw connection operations are unavailable.")

    async with _db_pool.acquire() as conn:

        try:
            yield conn
        finally:
            # Connection is returned to pool by 'acquire' context manager
            pass

