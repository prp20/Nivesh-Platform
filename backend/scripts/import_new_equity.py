import asyncio
import pandas as pd
from sqlalchemy import select, insert, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from backend.app.database import session_factory
from backend.app.models import FundMaster, BenchmarkMaster
from datetime import datetime

async def import_data(csv_path):
    print(f"Reading CSV from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    async with session_factory() as session:
        # 1. Sync BenchmarkMaster
        print("Checking benchmarks...")
        unique_benchmarks = df['benchmark_index_code'].unique()
        res = await session.execute(select(BenchmarkMaster.benchmark_code))
        existing_benchmarks = set(res.scalars().all())
        
        for b_code in unique_benchmarks:
            if b_code not in existing_benchmarks:
                print(f"Adding missing benchmark: {b_code}")
                # We don't have descriptions, so just use title case for now
                name = b_code.replace('_', ' ').title()
                session.add(BenchmarkMaster(
                    benchmark_code=b_code, 
                    benchmark_name=name,
                    ticker=b_code, # Placeholder ticker
                    benchmark_type="Equity",
                    asset_class="Equity"
                ))
        
        await session.flush() # Ensure benchmarks exist for foreign keys
        
        # 2. Sync FundMaster
        print(f"Upserting {len(df)} funds...")
        for _, row in df.iterrows():
            fund_data = {
                "scheme_name": row['scheme_name'],
                "amc_name": row['amc_name'],
                "plan_type": row.get('plan_type', 'Direct'),
                "scheme_category": row['scheme_category'],
                "scheme_subcategory": row['scheme_subcategory'],
                "benchmark_index_code": row['benchmark_index_code'],
                "inception_date": datetime.strptime(row['inception_date'], '%d-%m-%Y').date() if isinstance(row['inception_date'], str) else None,
                "is_active": True,
                "updated_at": datetime.utcnow()
            }
            
            # Using PostgreSQL-specific upsert (since user OS is linux/postgres)
            stmt = pg_insert(FundMaster).values(
                scheme_code=str(row['scheme_code']),
                **fund_data
            ).on_conflict_do_update(
                index_elements=[FundMaster.scheme_code],
                set_=fund_data
            )
            await session.execute(stmt)

        await session.commit()
        print("Import Complete.")

if __name__ == "__main__":
    csv_file = "backend/data/new_equity_only.csv"
    asyncio.run(import_data(csv_file))
