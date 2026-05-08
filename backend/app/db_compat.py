"""
db_compat.py — Database dialect abstraction layer.

Provides a unified async API for raw SQL operations that works with both
PostgreSQL (asyncpg) and SQLite (aiosqlite). All dialect-specific translation
(parameter style, upsert syntax) is handled here so callers stay clean.
"""
import re
import importlib
import logging
from contextlib import asynccontextmanager
from typing import Any

# Reload app.config so that any DATABASE_URL set via environment variable
# (e.g. via monkeypatch in tests) is picked up when this module is reloaded.
import app.config as _config_module
importlib.reload(_config_module)
from app.config import settings  # noqa: E402 — intentional post-reload import

logger = logging.getLogger(__name__)


def is_sqlite() -> bool:
    """Return True if DATABASE_URL points to a SQLite database."""
    return settings.DATABASE_URL.startswith("sqlite")


def _sqlite_path() -> str:
    """Extract the file path from a sqlite+aiosqlite:///./path URL."""
    # sqlite+aiosqlite:///./foo.db  →  ./foo.db
    # sqlite:///./foo.db           →  ./foo.db
    return re.sub(r'^sqlite(?:\+aiosqlite)?:///', '', settings.DATABASE_URL)


def translate_sql(sql: str) -> str:
    """
    Rewrite PostgreSQL-flavoured SQL to be SQLite-compatible.

    Translations applied (SQLite only):
      1. Positional params  $1, $2, ...  →  ?, ?, ...
      2. Upsert             INSERT INTO ... ON CONFLICT (...) DO UPDATE SET ...
                            →  INSERT OR REPLACE INTO ...  (ON CONFLICT stripped)
    PostgreSQL: returned unchanged.
    """
    if not is_sqlite():
        return sql

    # 1. Translate positional parameters
    sql = re.sub(r'\$\d+', '?', sql)

    # 2. Translate ON CONFLICT upsert to INSERT OR REPLACE
    if re.search(r'\bON\s+CONFLICT\b', sql, flags=re.IGNORECASE):
        # Strip everything from ON CONFLICT onwards
        sql = re.sub(
            r'\s+ON\s+CONFLICT\b.*',
            '',
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # Change INSERT INTO → INSERT OR REPLACE INTO
        sql = re.sub(
            r'\bINSERT\s+INTO\b',
            'INSERT OR REPLACE INTO',
            sql,
            count=1,
            flags=re.IGNORECASE,
        )

    return sql.strip()


@asynccontextmanager
async def raw_connection():
    """
    Async context manager that yields a raw DB connection.

    PostgreSQL: acquires from the asyncpg pool (initialises pool on first call).
    SQLite:     opens a per-call aiosqlite connection (thread-safe, no pool needed).
    """
    if is_sqlite():
        import aiosqlite
        path = _sqlite_path()
        async with aiosqlite.connect(path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn
    else:
        from app.database import _db_pool, init_db_pool
        pool = _db_pool
        if pool is None:
            pool = await init_db_pool()
        if pool is None:
            raise RuntimeError(
                "asyncpg pool is not initialized. "
                "Raw connection operations are unavailable."
            )
        async with pool.acquire() as conn:
            yield conn


async def db_execute(conn: Any, sql: str, params: tuple = ()) -> None:
    """Execute a write statement (INSERT / UPDATE / DELETE)."""
    sql = translate_sql(sql)
    if is_sqlite():
        await conn.execute(sql, params)
        await conn.commit()
    else:
        await conn.execute(sql, *params)


async def db_executemany(conn: Any, sql: str, rows: list) -> None:
    """Execute a write statement for each row in rows (bulk insert/upsert)."""
    sql = translate_sql(sql)
    if is_sqlite():
        await conn.executemany(sql, rows)
        await conn.commit()
    else:
        await conn.executemany(sql, rows)


async def db_fetch(conn: Any, sql: str, params: tuple = ()) -> list:
    """Fetch all matching rows as a list of dicts."""
    sql = translate_sql(sql)
    if is_sqlite():
        async with conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    else:
        rows = await conn.fetch(sql, *params)
        return [dict(row) for row in rows]


async def db_fetchrow(conn: Any, sql: str, params: tuple = ()) -> dict | None:
    """Fetch a single row as a dict, or None if not found."""
    sql = translate_sql(sql)
    if is_sqlite():
        async with conn.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
    else:
        row = await conn.fetchrow(sql, *params)
        return dict(row) if row else None
