"""
Seed the stocks table with NSE-listed companies.

Data source: NSE website or a curated CSV.
This script uses yfinance to validate each symbol before inserting.

Run once: python scripts/seed/seed_stock_master.py
"""
import asyncio
import asyncpg
import yfinance as yf
from typing import List, Dict
import sys
import os

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.config import settings

# Curated list of well-known NSE stocks for initial seeding.
# Extend this with a full NSE symbol CSV download from:
# https://www.nseindia.com/market-data/securities-available-for-trading
SEED_STOCKS: List[Dict] = [
    # Large Cap — NIFTY 50
    {"symbol": "RELIANCE",   "yf_symbol": "RELIANCE.NS",   "company_name": "Reliance Industries Ltd",        "sector": "Energy",          "market_cap_cat": "large"},
    {"symbol": "TCS",        "yf_symbol": "TCS.NS",        "company_name": "Tata Consultancy Services Ltd",  "sector": "IT",              "market_cap_cat": "large"},
    {"symbol": "HDFCBANK",   "yf_symbol": "HDFCBANK.NS",   "company_name": "HDFC Bank Ltd",                  "sector": "Banking",         "market_cap_cat": "large"},
    {"symbol": "INFY",       "yf_symbol": "INFY.NS",       "company_name": "Infosys Ltd",                    "sector": "IT",              "market_cap_cat": "large"},
    {"symbol": "ICICIBANK",  "yf_symbol": "ICICIBANK.NS",  "company_name": "ICICI Bank Ltd",                 "sector": "Banking",         "market_cap_cat": "large"},
    {"symbol": "HINDUNILVR", "yf_symbol": "HINDUNILVR.NS", "company_name": "Hindustan Unilever Ltd",         "sector": "FMCG",            "market_cap_cat": "large"},
    {"symbol": "BHARTIARTL", "yf_symbol": "BHARTIARTL.NS", "company_name": "Bharti Airtel Ltd",              "sector": "Telecom",         "market_cap_cat": "large"},
    {"symbol": "KOTAKBANK",  "yf_symbol": "KOTAKBANK.NS",  "company_name": "Kotak Mahindra Bank Ltd",        "sector": "Banking",         "market_cap_cat": "large"},
    {"symbol": "WIPRO",      "yf_symbol": "WIPRO.NS",      "company_name": "Wipro Ltd",                      "sector": "IT",              "market_cap_cat": "large"},
    {"symbol": "LT",         "yf_symbol": "LT.NS",         "company_name": "Larsen & Toubro Ltd",            "sector": "Infrastructure",  "market_cap_cat": "large"},
    {"symbol": "AXISBANK",   "yf_symbol": "AXISBANK.NS",   "company_name": "Axis Bank Ltd",                  "sector": "Banking",         "market_cap_cat": "large"},
    {"symbol": "BAJFINANCE", "yf_symbol": "BAJFINANCE.NS", "company_name": "Bajaj Finance Ltd",              "sector": "NBFC",            "market_cap_cat": "large"},
    {"symbol": "SBIN",       "yf_symbol": "SBIN.NS",       "company_name": "State Bank of India",            "sector": "Banking",         "market_cap_cat": "large"},
    {"symbol": "MARUTI",     "yf_symbol": "MARUTI.NS",     "company_name": "Maruti Suzuki India Ltd",        "sector": "Auto",            "market_cap_cat": "large"},
    {"symbol": "SUNPHARMA",  "yf_symbol": "SUNPHARMA.NS",  "company_name": "Sun Pharmaceutical Industries",  "sector": "Pharma",          "market_cap_cat": "large"},
    # Indices (is_index = True)
    {"symbol": "NIFTY50",    "yf_symbol": "^NSEI",         "company_name": "NIFTY 50 Index",                 "sector": "Index",           "market_cap_cat": None, "is_index": True},
    {"symbol": "SENSEX",     "yf_symbol": "^BSESN",        "company_name": "BSE SENSEX",                     "sector": "Index",           "market_cap_cat": None, "is_index": True},
    {"symbol": "NIFTYBANK",  "yf_symbol": "^NSEBANK",      "company_name": "NIFTY Bank Index",               "sector": "Index",           "market_cap_cat": None, "is_index": True},
    # Add more stocks here — or load from a CSV file
]

INSERT_SQL = """
    INSERT INTO stocks (symbol, nse_symbol, yf_symbol, screener_slug, company_name, sector, market_cap_cat, is_index, is_active)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE)
    ON CONFLICT (symbol) DO UPDATE SET
        company_name   = EXCLUDED.company_name,
        sector         = EXCLUDED.sector,
        market_cap_cat = EXCLUDED.market_cap_cat,
        updated_at     = NOW()
"""


async def seed():
    # Convert async URL to sync URL for asyncpg
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    try:
        for s in SEED_STOCKS:
            await conn.execute(
                INSERT_SQL,
                s["symbol"],
                s.get("nse_symbol", s["symbol"]),
                s["yf_symbol"],
                s.get("screener_slug", s["symbol"]),
                s["company_name"],
                s.get("sector"),
                s.get("market_cap_cat"),
                s.get("is_index", False),
            )
            print(f"  ✓ {s['symbol']}")
        print(f"\nSeeded {len(SEED_STOCKS)} records.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
