import asyncio
from app.database import raw_connection

async def cleanup():
    async with raw_connection() as conn:
        # Technical Indicators
        print("Cleaning technical_indicators...")
        res = await conn.execute("UPDATE technical_indicators SET rs_6m_vs_nifty = NULL WHERE rs_6m_vs_nifty = 'NaN'::numeric")
        print(f"Updated {res}")
        
        # Financial Ratios (just in case)
        print("Cleaning financial_ratios...")
        # Get numeric columns
        cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'financial_ratios' AND data_type = 'numeric'")
        for col in cols:
            cname = col['column_name']
            await conn.execute(f"UPDATE financial_ratios SET {cname} = NULL WHERE {cname} = 'NaN'::numeric OR {cname} = 'Infinity'::numeric OR {cname} = '-Infinity'::numeric")

if __name__ == "__main__":
    asyncio.run(cleanup())
