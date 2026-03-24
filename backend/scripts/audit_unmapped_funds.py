import asyncio
import pandas as pd
from sqlalchemy import select
from app.database import session_factory
from app.models import FundMaster

async def audit_funds():
    async with session_factory() as session:
        print("Auditing Mutual Fund Vault for unmapped indices...")
        
        # 1. Query for UNCLASSIFIED
        q = select(FundMaster).where(FundMaster.benchmark_index_code == "UNCLASSIFIED")
        res = await session.execute(q)
        funds = res.scalars().all()
        
        if not funds:
            print("Zero unmapped assets found. Vault is 100% indexed.")
            return

        print(f"Detected {len(funds)} unmapped assets.")
        
        # 2. Extract details
        data = [
            {
                "Code": f.scheme_code,
                "Name": f.scheme_name,
                "Category": f.scheme_category,
                "AMC": f.amc_name
            }
            for f in funds
        ]
        
        df = pd.DataFrame(data)
        # Display nicely
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_colwidth', None)
        print("\n=== UNMAPPED ASSETS REPORT ===")
        print(df.to_string(index=False))
        print("==============================\n")

if __name__ == "__main__":
    asyncio.run(audit_funds())
