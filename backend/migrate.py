import argparse
import asyncio

from app.database import engine, Base

# Import all models so metadata has them registered
from app.models import (  # noqa: F401
    FundMaster,
    BenchmarkMaster,
    FundNavHistory,
    BenchmarkNavHistory,
    FundMetrics,
    BenchmarkMetrics,
)

_DANGER_WARNING = """
WARNING: This script will permanently DELETE all rows from:
  - benchmark_nav_history
  - benchmark_metrics

This is a destructive, irreversible operation.
Re-run with --force to confirm you understand the consequences.
"""


async def run_migrations(force: bool) -> None:
    if not force:
        print(_DANGER_WARNING)
        return

    async with engine.begin() as conn:
        print("Provisioning BenchmarkMetrics table if it doesn't exist...")
        await conn.run_sync(Base.metadata.create_all)

        print("Flushing benchmark_nav_history rows...")
        await conn.execute(BenchmarkNavHistory.__table__.delete())

        print("Flushing benchmark_metrics rows...")
        await conn.execute(BenchmarkMetrics.__table__.delete())

        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Provision schema and optionally wipe benchmark tables."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Required to actually execute the destructive DELETE statements.",
    )
    args = parser.parse_args()
    asyncio.run(run_migrations(force=args.force))
