import asyncio
import logging
import requests
import sys
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Add the project root to sys.path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import engine, AsyncSessionLocal
from app.models import FundMaster

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest_isins")

AMFI_NAV_URL = "https://portal.amfiindia.com/spages/NAVOpen.txt"

async def ingest_isins():
    logger.info(f"Fetching AMFI NAV data from {AMFI_NAV_URL}...")
    try:
        response = requests.get(AMFI_NAV_URL, timeout=30)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        logger.error(f"Failed to fetch AMFI data: {e}")
        return

    lines = content.splitlines()
    # Format: Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
    
    isin_map = {} # scheme_code -> isin
    
    logger.info("Parsing AMFI data...")
    for line in lines:
        if not line or ';' not in line:
            continue
        
        parts = line.split(';')
        if len(parts) < 4:
            continue
            
        try:
            scheme_code = parts[0].strip()
            isin_growth = parts[1].strip()
            isin_reinvest = parts[2].strip()
            
            # Prefer growth ISIN, fallback to reinvestment ISIN
            isin = isin_growth if isin_growth and isin_growth != '-' else isin_reinvest
            
            if scheme_code and isin and isin != '-':
                isin_map[scheme_code] = isin
        except Exception:
            continue

    logger.info(f"Found {len(isin_map)} ISIN mappings. Updating database...")
    
    async with AsyncSessionLocal() as session:
        count = 0
        batch_size = 500
        scheme_codes = list(isin_map.keys())
        
        for i in range(0, len(scheme_codes), batch_size):
            batch = scheme_codes[i:i+batch_size]
            for code in batch:
                isin = isin_map[code]
                # Update if scheme_code exists
                await session.execute(
                    text("UPDATE fund_master SET isin = :isin WHERE scheme_code = :code AND (isin IS NULL OR isin != :isin)"),
                    {"isin": isin, "code": code}
                )
            await session.commit()
            count += len(batch)
            logger.info(f"Processed {count}/{len(isin_map)} potential updates...")

    logger.info("ISIN ingestion complete.")

if __name__ == "__main__":
    asyncio.run(ingest_isins())
