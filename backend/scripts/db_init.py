import asyncio
import sys
import os
import argparse

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import engine, Base
from app.models import (
    SyncJob, FundMaster, BenchmarkMaster,
    FundNavHistory, BenchmarkNavHistory,
    BenchmarkMetrics, FundMetrics
)


async def init_db(force_delete: bool = False):
    print("Connecting to database and ensuring table structures exist...")
    async with engine.begin() as conn:
        from sqlalchemy import text
        
        if force_delete:
            print("Force delete engaged. Wiping public schema...")
            # Drop the public schema and everything in it to get a completely fresh state
            await conn.execute(text("DROP SCHEMA public CASCADE;"))
            await conn.execute(text("CREATE SCHEMA public;"))
            await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
            print("Public schema wiped successfully.")
        
        # Ensure required extensions exist
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        # Create all tables defined in Base metadata (MF + Stock models)
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialization complete.")


def stamp_alembic():
    """Stamp alembic_version to head without running migrations.

    Tables are already created by create_all above; we just need to tell
    Alembic the schema is current so future migrations chain correctly.
    """
    try:
        from alembic.config import Config
        from alembic import command as alembic_command

        # Locate alembic.ini relative to the backend root
        ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'alembic.ini'))
        if not os.path.exists(ini_path):
            print(f"  [WARN] alembic.ini not found at {ini_path} — skipping stamp.")
            return

        cfg = Config(ini_path)
        alembic_command.stamp(cfg, "head")
        print("Alembic version stamped at head.")
    except Exception as exc:
        print(f"  [WARN] Could not stamp Alembic version: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the database.")
    parser.add_argument("--force-delete", action="store_true", help="Wipes all existing database tables entirely to start fresh.")
    args = parser.parse_args()

    asyncio.run(init_db(force_delete=args.force_delete))
    stamp_alembic()
