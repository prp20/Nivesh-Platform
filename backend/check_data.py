import asyncio
import json
from app.database import raw_connection
from datetime import date

async def check_data():
    async with raw_connection() as conn:
        # Get stock ID
        stock = await conn.fetchrow("SELECT id, symbol, yf_symbol FROM stocks WHERE symbol = 'RELIANCE'")
        if not stock:
            print("Stock not found")
            return
        print(f"Stock: {dict(stock)}")
        
        # Get recent price data
        rows = await conn.fetch("""
            SELECT price_date, open, high, low, close, adj_close, volume
            FROM price_data
            WHERE stock_id = $1
            ORDER BY price_date DESC
            LIMIT 10
        """, stock['id'])
        
        print("\nLast 10 price records:")
        for r in rows:
            print(dict(r))

if __name__ == "__main__":
    asyncio.run(check_data())
