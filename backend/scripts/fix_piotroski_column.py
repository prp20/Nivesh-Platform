import asyncio
import logging
import os
from sqlalchemy import text
from app.database import engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FIX_QUERIES = [
    # Rename column if it exists with the old name
    """
    DO $$ 
    BEGIN 
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='financial_ratios' AND column_name='piotroski_score') THEN
            ALTER TABLE financial_ratios RENAME COLUMN piotroski_score TO piotroski_f_score;
        END IF;
    END $$;
    """,
    # Ensure it exists with the new name if not already there
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS piotroski_f_score INTEGER;"
]

async def run_fix():
    logger.info("Fixing Piotroski column name...")
    async with engine.begin() as conn:
        for query in FIX_QUERIES:
            try:
                await conn.execute(text(query))
                logger.info(f"Executed query successfully.")
            except Exception as e:
                logger.error(f"Failed to execute query: {e}")
    logger.info("Fix complete.")

if __name__ == "__main__":
    asyncio.run(run_fix())
