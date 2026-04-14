from contextlib import asynccontextmanager
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings


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
engine = create_async_engine(_async_db_url, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
session_factory = AsyncSessionLocal
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def raw_connection():
    """Get a raw asyncpg connection for direct SQL operations."""
    conn = await asyncpg.connect(_sync_db_url, statement_cache_size=0)
    try:
        yield conn
    finally:
        await conn.close()
