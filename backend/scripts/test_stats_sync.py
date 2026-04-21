import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv('.env')

from pipeline.stats_ingestion import sync_all_stats
from app.database import raw_connection, init_db_pool

async def verify():
    print("Testing stats sync for ABB.NS...")
    await init_db_pool()
    
    # Run sync for one stock
    await sync_all_stats(symbol="ABB")
    
    # Check DB
    async with raw_connection() as conn:
        row = await conn.fetchrow("""
            SELECT fr.* FROM financial_ratios fr
            JOIN stocks s ON s.id = fr.stock_id
            WHERE s.symbol = 'ABB' AND fr.period_type = 'latest'
            ORDER BY fr.period_end DESC LIMIT 1
        """)
        
        if row:
            print("\nSync Successful. Data found in DB:")
            for key, val in dict(row).items():
                if val is not None:
                    print(f"  {key}: {val}")
        else:
            print("\nSync Failed. No 'latest' record found for ABB.")

if __name__ == "__main__":
    asyncio.run(verify())
