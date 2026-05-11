# backend/tests/test_db_compat.py
"""Unit tests for db_compat SQL translation and dialect detection."""
import os
import pytest


def _patch_db_url(monkeypatch, url: str):
    """
    Patch the DATABASE_URL seen by db_compat.  Because db_compat reads from
    pydantic-settings (not os.environ directly), we monkeypatch the `settings`
    attribute on the config module so that is_sqlite() / _database_url() pick
    up the test value without needing to reload the module.
    """
    from app import config
    monkeypatch.setattr(config.settings, "DATABASE_URL", url)


# ---------------------------------------------------------------------------
# translate_sql tests (pure function, no DB needed)
# ---------------------------------------------------------------------------

def test_translate_positional_params_no_op_for_postgres(monkeypatch):
    """PostgreSQL URL → translate_sql is a no-op."""
    _patch_db_url(monkeypatch, "postgresql+asyncpg://u:p@localhost:5432/db")
    from app import db_compat as dc
    sql = "SELECT * FROM t WHERE id = $1 AND name = $2"
    assert dc.translate_sql(sql) == sql


def test_translate_positional_params_sqlite(monkeypatch):
    """SQLite URL → $1,$2 become ?."""
    _patch_db_url(monkeypatch, "sqlite+aiosqlite:///./test.db")
    from app import db_compat as dc
    result = dc.translate_sql("SELECT * FROM t WHERE id = $1 AND name = $2")
    assert result == "SELECT * FROM t WHERE id = ? AND name = ?"


def test_translate_upsert_sqlite(monkeypatch):
    """ON CONFLICT DO UPDATE → INSERT OR REPLACE on SQLite."""
    _patch_db_url(monkeypatch, "sqlite+aiosqlite:///./test.db")
    from app import db_compat as dc
    sql = (
        "INSERT INTO price_data (stock_id, price_date, close) "
        "VALUES ($1, $2, $3) "
        "ON CONFLICT (stock_id, price_date) DO UPDATE SET close = EXCLUDED.close"
    )
    result = dc.translate_sql(sql)
    assert "INSERT OR REPLACE INTO" in result
    assert "ON CONFLICT" not in result
    assert "?" in result  # params also translated


def test_translate_no_upsert_unchanged_sqlite(monkeypatch):
    """Regular INSERT (no ON CONFLICT) stays as INSERT, not INSERT OR REPLACE."""
    _patch_db_url(monkeypatch, "sqlite+aiosqlite:///./test.db")
    from app import db_compat as dc
    sql = "INSERT INTO t (a, b) VALUES ($1, $2)"
    result = dc.translate_sql(sql)
    assert result.startswith("INSERT INTO")
    assert "OR REPLACE" not in result


def test_is_sqlite_true(monkeypatch):
    _patch_db_url(monkeypatch, "sqlite+aiosqlite:///./test.db")
    from app import db_compat as dc
    assert dc.is_sqlite() is True


def test_is_sqlite_false(monkeypatch):
    _patch_db_url(monkeypatch, "postgresql+asyncpg://u:p@localhost/db")
    from app import db_compat as dc
    assert dc.is_sqlite() is False


# ---------------------------------------------------------------------------
# Round-trip test — db_execute / db_fetch over a real in-memory SQLite DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_execute_and_fetch(monkeypatch, tmp_path):
    """db_execute inserts a row; db_fetch retrieves it."""
    db_path = str(tmp_path / "roundtrip.db")
    _patch_db_url(monkeypatch, f"sqlite+aiosqlite:///{db_path}")
    from app import db_compat as dc

    import aiosqlite
    async with aiosqlite.connect(db_path) as setup_conn:
        await setup_conn.execute(
            "CREATE TABLE test_items (id INTEGER PRIMARY KEY, name TEXT)"
        )
        await setup_conn.commit()

    async with dc.raw_connection() as conn:
        await dc.db_execute(conn, "INSERT INTO test_items (name) VALUES ($1)", ("hello",))
        rows = await dc.db_fetch(conn, "SELECT name FROM test_items WHERE name = $1", ("hello",))

    assert len(rows) == 1
    assert rows[0]["name"] == "hello"


@pytest.mark.asyncio
async def test_sqlite_fetchrow(monkeypatch, tmp_path):
    """db_fetchrow returns a single dict or None."""
    db_path = str(tmp_path / "fetchrow.db")
    _patch_db_url(monkeypatch, f"sqlite+aiosqlite:///{db_path}")
    from app import db_compat as dc

    import aiosqlite
    async with aiosqlite.connect(db_path) as setup_conn:
        await setup_conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v INTEGER)")
        await setup_conn.execute("INSERT INTO kv VALUES ('x', 42)")
        await setup_conn.commit()

    async with dc.raw_connection() as conn:
        row = await dc.db_fetchrow(conn, "SELECT v FROM kv WHERE k = $1", ("x",))
        missing = await dc.db_fetchrow(conn, "SELECT v FROM kv WHERE k = $1", ("z",))

    assert row is not None
    assert row["v"] == 42
    assert missing is None


def test_translate_strips_pg_type_casts(monkeypatch):
    """PostgreSQL type casts like ::jsonb are stripped on SQLite."""
    _patch_db_url(monkeypatch, "sqlite+aiosqlite:///./test.db")
    from app import db_compat as dc
    sql = "INSERT INTO t (data) VALUES ($1::jsonb)"
    result = dc.translate_sql(sql)
    assert "::" not in result
    assert "?" in result
