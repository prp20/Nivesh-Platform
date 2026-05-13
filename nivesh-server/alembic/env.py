"""
Alembic env.py — Phase 1 (Supabase / raw SQL)

Connection: reads ALEMBIC_URL from environment.
Use the direct Supabase URL (port 5432), NOT the Supavisor pooler.
No SQLAlchemy models imported — migrations use op.execute() with raw SQL.

Usage:
    export ALEMBIC_URL="postgresql://postgres:[pwd]@db.[ref].supabase.co:5432/postgres"
    alembic upgrade head
"""
import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No target_metadata — we use raw SQL, not autogenerate
target_metadata = None


def get_url() -> str:
    url = os.environ.get("ALEMBIC_URL")
    if not url:
        raise RuntimeError(
            "ALEMBIC_URL environment variable is not set.\n"
            "Set it to the Supabase direct connection URL (port 5432):\n"
            "  export ALEMBIC_URL='postgresql://postgres:[pwd]@db.[ref].supabase.co:5432/postgres'"
        )
    # Ensure sync driver (psycopg2), not asyncpg
    return url.replace("postgresql+asyncpg://", "postgresql://")


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting — useful for review."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect and apply migrations directly."""
    engine = create_engine(get_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
