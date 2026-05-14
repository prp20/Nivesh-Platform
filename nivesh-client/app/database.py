"""
Async SQLAlchemy engine for SQLite.

Uses aiosqlite driver with WAL journal mode for concurrent reads
(APScheduler and FastAPI both access the DB simultaneously).
"""

from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import event, text

from .config import settings

# Ensure ~/.nivesh/ exists before SQLite tries to create the file
Path(settings.SQLITE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.SQLITE_DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=settings.DEBUG,
)


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite(dbapi_conn, _):
    """
    Apply SQLite pragmas on every new connection.

    WAL mode: allows one writer and multiple concurrent readers —
    critical because APScheduler and FastAPI both access the DB.
    synchronous=NORMAL: faster than FULL, still safe with WAL.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency: yield an async DB session with rollback on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
