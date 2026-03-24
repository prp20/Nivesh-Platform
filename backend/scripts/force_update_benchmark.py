import asyncio
from sqlalchemy import update
from backend.app.database import session_factory
from backend.app.models import FundMaster

async def force_update():
    async with session_factory() as session:
        print("Force updating Fund 120505 benchmark...")
        stmt = (
            update(FundMaster)
            .where(FundMaster.scheme_code == "120505")
            .values(benchmark_index_code="NIFTY_MIDCAP_150")
        )
        await session.execute(stmt)
        await session.commit()
        print("Update complete.")

if __name__ == "__main__":
    asyncio.run(force_update())
