import asyncio
from sqlalchemy import select, text
from backend.app.database import session_factory
from backend.app.models import FundMetrics

async def check_db():
    async with session_factory() as session:
        # Check count of metrics with Alpha/Beta
        result = await session.execute(text("SELECT count(*) FROM fund_metrics WHERE alpha IS NOT NULL"))
        count = result.scalar()
        print(f"Funds with computed Alpha: {count}")
        
        # Sample one
        result = await session.execute(text("SELECT scheme_code, alpha, beta, tracking_error FROM fund_metrics WHERE alpha IS NOT NULL LIMIT 5"))
        rows = result.fetchall()
        for row in rows:
            print(f"Fund {row[0]}: Alpha={row[1]}, Beta={row[2]}, TE={row[3]}")

if __name__ == "__main__":
    asyncio.run(check_db())
