import asyncio
import asyncpg
import csv
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.config import settings

# Paths to the CSV files
BACKEND_DIR = Path(__file__).parent.parent.parent
INDICES_CSV = BACKEND_DIR / "data" / "indices.csv"
STOCKS_CSV = BACKEND_DIR / "data" / "stocks.csv"
FUNDS_CSV = BACKEND_DIR / "data" / "new_equity_only_updated.csv"

# SQL Queries
INSERT_BENCHMARK_SQL = """
    INSERT INTO benchmark_master (benchmark_code, benchmark_name, ticker, benchmark_type, asset_class, is_active, created_at, updated_at)
    VALUES ($1, $2, $3, 'Market Index', 'Equity', TRUE, NOW(), NOW())
    ON CONFLICT (benchmark_code) DO UPDATE SET
        benchmark_name = EXCLUDED.benchmark_name,
        ticker = EXCLUDED.ticker,
        updated_at = NOW()
"""

INSERT_STOCK_SQL = """
    INSERT INTO stocks (symbol, nse_symbol, yf_symbol, screener_slug, company_name, sector, industry, summary, market_cap_cat, is_index, is_active, created_at, updated_at)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, FALSE, TRUE, NOW(), NOW())
    ON CONFLICT (symbol) DO UPDATE SET
        company_name   = EXCLUDED.company_name,
        sector         = EXCLUDED.sector,
        industry       = EXCLUDED.industry,
        summary        = EXCLUDED.summary,
        market_cap_cat = EXCLUDED.market_cap_cat,
        is_index       = FALSE,
        updated_at     = NOW()
"""

INSERT_FUND_SQL = """
    INSERT INTO fund_master (scheme_code, scheme_name, amc_name, inception_date, plan_type, scheme_category, scheme_subcategory, benchmark_index_code, is_active, created_at, updated_at)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE, NOW(), NOW())
    ON CONFLICT (scheme_code) DO UPDATE SET
        scheme_name = EXCLUDED.scheme_name,
        amc_name = EXCLUDED.amc_name,
        inception_date = EXCLUDED.inception_date,
        plan_type = EXCLUDED.plan_type,
        scheme_category = EXCLUDED.scheme_category,
        scheme_subcategory = EXCLUDED.scheme_subcategory,
        benchmark_index_code = EXCLUDED.benchmark_index_code,
        updated_at = NOW()
"""

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str or date_str.strip() in ("", "-"):
        return datetime(2013, 1, 1)  # Default fallback
    
    date_str = date_str.strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime(2013, 1, 1)

async def get_connection():
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.connect(db_url, statement_cache_size=0)

async def seed_indices(conn):
    print(f"\n[1/3] Seeding Indices from {INDICES_CSV}...")
    if not INDICES_CSV.exists():
        print(f"Error: Indices CSV not found at {INDICES_CSV}")
        return

    count = 0
    with open(INDICES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row["symbol"].strip()
            name = row["company_name"].strip()
            yf_symbol = row["yf_symbol"].strip()
            
            await conn.execute(INSERT_BENCHMARK_SQL, symbol, name, yf_symbol)
            count += 1
            print(f"  ✓ {symbol}")
    
    print(f"Indices seeding complete. Total: {count}")

async def seed_stocks(conn):
    print(f"\n[2/3] Seeding Stocks from {STOCKS_CSV}...")
    if not STOCKS_CSV.exists():
        print(f"Error: Stocks CSV not found at {STOCKS_CSV}")
        return

    count = 0
    with open(STOCKS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["is_index"].lower() == "true":
                continue  # Indices handled by seed_indices or stocks/benchmark split
            
            symbol = row["symbol"].strip()
            await conn.execute(
                INSERT_STOCK_SQL,
                symbol,
                row.get("nse_symbol", symbol),
                row["yf_symbol"],
                row.get("screener_slug", symbol),
                row["company_name"],
                row.get("sector"),
                row.get("industry"),
                row.get("summary"),
                row.get("market_cap_category") or row.get("market_cap_cat")
            )
            count += 1
            if count % 100 == 0:
                print(f"  Processed {count} stocks...")
    
    print(f"Stocks seeding complete. Total: {count}")

async def seed_funds(conn):
    print(f"\n[3/3] Seeding Mutual Funds from {FUNDS_CSV}...")
    if not FUNDS_CSV.exists():
        print(f"Error: Funds CSV not found at {FUNDS_CSV}")
        return

    count = 0
    with open(FUNDS_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            scheme_code = row.get("scheme_code")
            if not scheme_code:
                continue
            
            inception_date = parse_date(row.get("inception_date"))
            
            await conn.execute(
                INSERT_FUND_SQL,
                scheme_code,
                row.get("scheme_name"),
                row.get("amc_name"),
                inception_date,
                row.get("plan_type", "Direct"),
                row.get("scheme_category"),
                row.get("scheme_subcategory"),
                row.get("benchmark_index_code")
            )
            count += 1
            if count % 100 == 0:
                print(f"  Processed {count} funds...")

    print(f"Mutual Funds seeding complete. Total: {count}")

async def main():
    mode = "all"
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    
    conn = await get_connection()
    try:
        # 1. Always seed indices first if requested or in all mode
        if mode in ("indices", "stocks", "funds", "all"):
            await seed_indices(conn)
            
        # 2. Seed others based on mode
        if mode in ("stocks", "all"):
            await seed_stocks(conn)
        
        if mode in ("funds", "all"):
            await seed_funds(conn)
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
