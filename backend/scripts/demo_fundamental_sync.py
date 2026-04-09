import asyncio
import logging
import sys
import os
import json

# Setup paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from pipeline.fundamental_scraper import run_fundamental_scrape_one
from app.database import raw_connection

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

async def demo_sync():
    symbol = "RELIANCE"
    logger.info(f"--- DEMO: Syncing Fundamental Data for {symbol} ---")
    
    # 1. Trigger the sync
    # This will: Scrape Screener.in -> Normalize -> Store in Postgres
    await run_fundamental_scrape_one(symbol, force=True)
    
    logger.info(f"\n--- VERIFICATION: Data stored in Database ---")
    
    async with raw_connection() as conn:
        # Check financial_statements
        stmt_rows = await conn.fetch("""
            SELECT statement_type, period_end, (data->>'revenue') as revenue, (data->>'net_profit') as net_profit
            FROM financial_statements fs
            JOIN stocks s ON fs.stock_id = s.id
            WHERE s.symbol = $1
            ORDER BY period_end DESC
            LIMIT 3
        """, symbol)
        
        logger.info("\nLATEST FINANCIAL STATEMENTS (P&L):")
        for r in stmt_rows:
            logger.info(f"Type: {r['statement_type']}, Period: {r['period_end']}, Revenue: {r['revenue']} Cr, Net Profit: {r['net_profit']} Cr")

        # Check shareholding
        sh_rows = await conn.fetch("""
            SELECT period_end, promoter_pct, fii_pct, dii_pct, public_pct
            FROM shareholding_pattern sp
            JOIN stocks s ON sp.stock_id = s.id
            WHERE s.symbol = $1
            ORDER BY period_end DESC
            LIMIT 1
        """, symbol)
        
        if sh_rows:
            r = sh_rows[0]
            logger.info(f"\nLATEST SHAREHOLDING PATTERN ({r['period_end']}):")
            logger.info(f"Promoters: {r['promoter_pct']}%, FII: {r['fii_pct']}%, DII: {r['dii_pct']}%, Public: {r['public_pct']}%")

if __name__ == "__main__":
    asyncio.run(demo_sync())
