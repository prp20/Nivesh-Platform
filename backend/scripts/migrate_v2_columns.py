import asyncio
import logging
from sqlalchemy import text
from app.database import engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALTER_QUERIES = [
    # financial_ratios table
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS operating_margin NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS dividend_per_share NUMERIC(12, 4);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS dividend_payout_ratio NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS ev_sales NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS net_debt NUMERIC(18, 4);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS net_debt_ebitda NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS asset_turnover NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS inventory_turnover NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS receivables_days NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS payable_days NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS cash_conv_cycle NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS fcf NUMERIC(18, 4);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS fcf_margin NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS fcf_yield NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS capex_to_revenue NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS capex_to_depreciation NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS piotroski_f_score INTEGER;",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS altman_z_score NUMERIC(10, 3);",
    "ALTER TABLE financial_ratios ADD COLUMN IF NOT EXISTS roic NUMERIC(10, 3);",

    # technical_indicators table
    "ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS volume_sma_50 BIGINT;",
    "ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS volume_ratio NUMERIC(10, 3);",
    "ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS obv BIGINT;",
    "ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS vwap_20 NUMERIC(12, 4);",
    "ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS cci_20 NUMERIC(10, 3);",
    "ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS williams_r NUMERIC(10, 3);",
    "ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS roc_14 NUMERIC(10, 3);",
    "ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS beta_1y NUMERIC(10, 4);",
    "ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS rs_6m_vs_nifty NUMERIC(10, 3);",
    "ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS pct_from_52w_high NUMERIC(10, 3);",
    "ALTER TABLE technical_indicators ADD COLUMN IF NOT EXISTS pct_from_52w_low NUMERIC(10, 3);",
]

async def run_migration():
    logger.info("Starting database migration (v2 ratios)...")
    async with engine.begin() as conn:
        for query in ALTER_QUERIES:
            try:
                await conn.execute(text(query))
                logger.info(f"Executed: {query}")
            except Exception as e:
                logger.error(f"Failed to execute {query}: {e}")
    logger.info("Migration complete.")

if __name__ == "__main__":
    asyncio.run(run_migration())
