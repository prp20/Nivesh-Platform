"""
Alembic env.py for nivesh-client SQLite database.

Key settings:
  - render_as_batch=True: REQUIRED for SQLite ALTER TABLE support.
    SQLite cannot drop/rename columns natively. Alembic's batch mode
    rewrites the table in a temp copy. Without this, future migrations fail.
  - Uses synchronous SQLite driver (sqlite:///) intentionally.
    Alembic command.upgrade() is called from an async lifespan context via
    run_in_executor, so the env.py must NOT call asyncio.run() — that would
    raise "This event loop is already running". The sync driver avoids this.
"""

import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure the nivesh-client directory is on sys.path so app.* imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import Base

# Import all models so Alembic can detect them for autogenerate
from app.models.user_data import Watchlist, PortfolioHolding, Transaction, UserPreference
from app.models.cache import CacheEntry
from app.models.auth import AuthToken, ServerConfig
from app.models.agent import AgentSession, AgentMessage, AgentMemory

# Alembic config object
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Use synchronous SQLite URL (no aiosqlite) — Alembic is always sync
_sync_url = f"sqlite:///{settings.SQLITE_DB_PATH}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
    context.configure(
        url=_sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against the SQLite DB."""
    # Override the URL from alembic.ini with the settings-derived URL
    config.set_main_option("sqlalchemy.url", _sync_url)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
