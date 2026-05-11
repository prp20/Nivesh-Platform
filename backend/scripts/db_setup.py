"""
Database setup utilities for the Nivesh Platform setup scripts.

Usage:
  python scripts/db_setup.py --check          # Exit 0 if tables exist, 1 if none
  python scripts/db_setup.py --drop-all       # Drop ALL tables (+ alembic_version)
  python scripts/db_setup.py --drop-mf        # Drop Mutual Fund tables only
  python scripts/db_setup.py --drop-stocks    # Drop Stock tables only (+ alembic_version)
"""

import asyncio
import os
import sys

# Load .env from backend directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


# Drop order must respect FK constraints (children before parents)
MF_TABLES = [
    'sync_jobs',
    'fund_metrics',
    'fund_nav_history',
    'fund_master',
    'benchmark_metrics',
    'benchmark_nav_history',
    'benchmark_master',
]

STOCK_TABLES = [
    'pipeline_audit',
    'stock_ratings',
    'detected_patterns',
    'technical_indicators',
    'financial_ratios',
    'shareholding_pattern',
    'financial_statements',
    'price_data',
    'stocks',
]

# Tables whose presence indicates a populated database
KEY_TABLES = ('fund_master', 'stocks', 'sync_jobs', 'price_data')


def _get_engine():
    url = os.getenv("DATABASE_URL", "")
    if not url:
        print("[ERROR] DATABASE_URL is not set. Check backend/.env", file=sys.stderr)
        sys.exit(1)
    return create_async_engine(url)


async def check_tables_exist() -> bool:
    """Return True if any key tables exist in the database."""
    engine = _get_engine()
    try:
        async with engine.connect() as conn:
            url = os.getenv("DATABASE_URL", "")
            if _is_sqlite(url):
                placeholders = ", ".join(f"'{t}'" for t in KEY_TABLES)
                result = await conn.execute(text(
                    f"SELECT COUNT(*) FROM sqlite_master "
                    f"WHERE type='table' AND name IN ({placeholders})"
                ))
            else:
                placeholders = ", ".join(f"'{t}'" for t in KEY_TABLES)
                result = await conn.execute(text(
                    f"SELECT COUNT(*) FROM information_schema.tables "
                    f"WHERE table_schema = 'public' AND table_name IN ({placeholders})"
                ))
            count = result.scalar()
            return (count or 0) > 0
    except Exception as e:
        print(f"[WARN]  Could not check tables: {e}", file=sys.stderr)
        return False
    finally:
        await engine.dispose()


async def drop_tables(tables: list, also_alembic: bool = False):
    """Drop the given list of tables using CASCADE. Optionally drop alembic_version."""
    engine = _get_engine()
    url = os.getenv("DATABASE_URL", "")
    try:
        async with engine.begin() as conn:
            for table in tables:
                if _is_sqlite(url):
                    await conn.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
                else:
                    await conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                print(f"  [OK]  dropped: {table}")
            if also_alembic:
                await conn.execute(text('DROP TABLE IF EXISTS alembic_version'))
                print("  [OK]  dropped: alembic_version")
        print("[OK]    Tables dropped successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to drop tables: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await engine.dispose()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)

    cmd = sys.argv[1]

    if cmd == '--check':
        exists = asyncio.run(check_tables_exist())
        # Exit 0 = tables exist, exit 1 = tables absent
        sys.exit(0 if exists else 1)

    elif cmd == '--drop-all':
        print("[WARN]  Dropping ALL tables...")
        asyncio.run(drop_tables(STOCK_TABLES + MF_TABLES, also_alembic=True))

    elif cmd == '--drop-mf':
        print("[WARN]  Dropping Mutual Fund tables...")
        asyncio.run(drop_tables(MF_TABLES, also_alembic=False))

    elif cmd == '--drop-stocks':
        print("[WARN]  Dropping Stock tables...")
        # Reset alembic_version so that migration 001 can re-run cleanly
        asyncio.run(drop_tables(STOCK_TABLES, also_alembic=True))

    else:
        print(f"[ERROR] Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(2)


if __name__ == '__main__':
    main()
