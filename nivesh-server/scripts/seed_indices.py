import asyncio
import csv
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import AsyncSessionLocal
from app import crud, models, schemas

# Target directory and metadata
INDEX_MAPPING = {
    "NIFTY_100": {"name": "NIFTY 100", "type": "Broad Market", "dir": "NIFTY_100"},
    "NIFTY_500": {"name": "NIFTY 500", "type": "Broad Market", "dir": "NIFTY_500"},
    # Add more as needed, but NIFTY_100 is specifically requested
}

BASE_DATA_DIR = Path("data/Nifty_indices")

def parse_date(date_str):
    for fmt in ("%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None

async def seed_benchmark(session, code, name, b_type):
    print(f"Ensuring benchmark exists: {name} ({code})")
    existing = await crud.get_benchmark_master(session, code)
    if not existing:
        benchmark_in = schemas.BenchmarkMasterCreate(
            benchmark_code=code,
            benchmark_name=name,
            ticker=code,
            benchmark_type=b_type,
            asset_class="Equity",
            is_active=True
        )
        await crud.create_benchmark_master(session, benchmark_in)
    else:
        print(f"Benchmark {code} already exists.")

async def process_index_folder(session, dir_path, code):
    if not dir_path.exists():
        print(f"Warning: Folder {dir_path} not found.")
        return

    csv_files = list(dir_path.glob("*.csv"))
    print(f"Found {len(csv_files)} historical files for {code}. Processing...")

    nav_data = {}
    for csv_file in csv_files:
        with open(csv_file, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Handle possible quoted keys or variations
                date_val = row.get("Date") or row.get("date")
                close_val = row.get("Close") or row.get("close") or row.get("Closing Index Value")
                
                if date_val and close_val:
                    date_obj = parse_date(date_val)
                    if date_obj:
                        try:
                            nav_data[date_obj.strftime("%Y-%m-%d")] = float(close_val.replace(",", "").strip())
                        except ValueError:
                            continue
    
    if nav_data:
        print(f"Inserting {len(nav_data)} records for {code}...")
        count = await crud.bulk_insert_benchmark_navs(session, code, nav_data)
        print(f"Successfully inserted/updated {count} records for {code}.")

async def main():
    async with AsyncSessionLocal() as session:
        for code, info in INDEX_MAPPING.items():
            dir_path = BASE_DATA_DIR / info["dir"]
            await seed_benchmark(session, code, info["name"], info["type"])
            await process_index_folder(session, dir_path, code)
        
        # Ensure additional benchmarks mentioned in funds CSV exist
        extra_benchmarks = [
            ("NIFTY_50", "NIFTY 50", "Broad Market"),
            ("NIFTY_LARGEMIDCAP_250", "NIFTY LARGEMIDCAP 250", "Multi Cap"),
            ("NIFTY_MIDCAP_150", "NIFTY MIDCAP 150", "Mid Cap"),
            ("NIFTY_SMALLCAP_250", "NIFTY SMALLCAP 250", "Small Cap"),
            ("NIFTY_MULTICAP_500_50_25_50", "NIFTY MULTICAP 500 50:25:25", "Multi Cap")
        ]
        for c, n, t in extra_benchmarks:
            await seed_benchmark(session, c, n, t)

if __name__ == "__main__":
    asyncio.run(main())
