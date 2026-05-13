import asyncio
import csv
import sys
import os
from datetime import datetime
from pathlib import Path
from tqdm import tqdm

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import AsyncSessionLocal
from app import crud, schemas

CSV_PATH = Path("data/new_equity_only_updated.csv")

def parse_date(date_str):
    if not date_str or date_str == "-":
        return None
    # For DD-MM-YYYY
    try:
        return datetime.strptime(date_str.strip(), "%d-%m-%Y").date()
    except ValueError:
        try:
            # Fallback to YYYY-MM-DD
            return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None

async def seed_funds():
    if not CSV_PATH.exists():
        print(f"Error: CSV file {CSV_PATH} not found.")
        return

    print(f"Reading mutual fund data from {CSV_PATH}...")
    funds_to_create = []
    
    with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            scheme_code = row.get("scheme_code")
            if not scheme_code:
                continue
                
            inception_date = parse_date(row.get("inception_date"))
            if not inception_date:
                # Use a default very old date if missing to avoid DB integrity error
                inception_date = datetime(2013, 1, 1).date()

            fund_in = schemas.FundMasterCreate(
                scheme_code=scheme_code,
                scheme_name=row.get("scheme_name"),
                amc_name=row.get("amc_name"),
                inception_date=inception_date,
                plan_type=row.get("plan_type", "Direct"),
                scheme_category=row.get("scheme_category"),
                scheme_subcategory=row.get("scheme_subcategory"),
                benchmark_index_code=row.get("benchmark_index_code"),
                is_active=True
            )
            funds_to_create.append(fund_in)

    print(f"Found {len(funds_to_create)} funds in CSV. syncing with database...")
    
    async with AsyncSessionLocal() as session:
        created_count = 0
        for fund in tqdm(funds_to_create, desc="Seeding Mutual Funds", unit="fund"):
            existing = await crud.get_fund_master_by_code(session, fund.scheme_code)
            if not existing:
                try:
                    await crud.create_fund_master(session, fund)
                    created_count += 1
                except Exception as e:
                    print(f"\nError creating fund {fund.scheme_code}: {e}")
                    await session.rollback()
            else:
                # Optional: Update existing records if needed
                # For now, we skip to save time as requested
                pass
        
        print(f"\nSeeding complete. Created {created_count} new fund records.")

if __name__ == "__main__":
    asyncio.run(seed_funds())
