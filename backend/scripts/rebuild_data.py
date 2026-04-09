import asyncio
import logging
import asyncpg
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from pipeline.price_ingestion import run_backfill
from pipeline.technical_analysis import run_technical_analysis_all
from pipeline.metric_recompute import recompute_price_dependent_ratios_all
from pipeline.rating_engine import run_rating_compute_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def run_wipe_and_rebuild():
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    logger.info("Connecting to database for TRUNCATE cascade...")
    conn = await asyncpg.connect(db_url)
    try:
        # We start with price_data, which will cascade delete dependent rows 
        # in technical_indicators and possibly others if FKs are set up.
        # But to be safe, we explicitly truncate the tables we know are derived.
        logger.info("Executing TRUNCATE on price_data, technical_indicators, stock_ratings...")
        await conn.execute("TRUNCATE TABLE technical_indicators CASCADE;")
        await conn.execute("TRUNCATE TABLE stock_ratings CASCADE;")
        await conn.execute("TRUNCATE TABLE price_data CASCADE;")
        logger.info("TRUNCATE completed successfully.")
    except Exception as e:
        logger.error(f"TRUNCATE failed: {e}")
        await conn.close()
        return
    finally:
        await conn.close()
    
    # 1. Price Backfill
    logger.info("-" * 50)
    logger.info("STEP 1: Starting 5-year price backfill...")
    await run_backfill("5y")
    
    # 2. Technical Analysis
    logger.info("-" * 50)
    logger.info("STEP 2: Starting technical analysis recompute...")
    await run_technical_analysis_all()
    
    # 3. Price-Dependent Ratios
    logger.info("-" * 50)
    logger.info("STEP 3: Starting price-dependent ratio refresh...")
    await recompute_price_dependent_ratios_all()
    
    # 4. Rating Engine
    logger.info("-" * 50)
    logger.info("STEP 4: Starting composite stock ratings recompute...")
    await run_rating_compute_all()
    
    logger.info("Data reconstruction complete!")

if __name__ == "__main__":
    asyncio.run(run_wipe_and_rebuild())
