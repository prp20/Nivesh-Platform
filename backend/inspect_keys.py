import asyncio
import json
from app.database import raw_connection

async def inspect():
    async with raw_connection() as conn:
        print("PL Data Sample:")
        row = await conn.fetchrow("SELECT data FROM financial_statements WHERE stock_id=10 AND statement_type='PL' ORDER BY period_end DESC LIMIT 1")
        if row:
            data = row['data']
            if isinstance(data, str): data = json.loads(data)
            print("Net Profit:", data.get("net_profit"))
            print("EPS in Rs:", data.get("eps_in_rs"))
            print("Dividend Payout:", data.get("dividend_payout"))
        
        print("\nBS Data Sample:")
        row = await conn.fetchrow("SELECT data FROM financial_statements WHERE stock_id=10 AND statement_type='BS' ORDER BY period_end DESC LIMIT 1")
        if row:
            data = row['data']
            print(f"Period End: {row['period_end']}")
            if isinstance(data, str): data = json.loads(data)
            print("Equity Capital:", data.get("equity_capital"))
            print("Reserves:", data.get("reserves"))

if __name__ == "__main__":
    asyncio.run(inspect())
