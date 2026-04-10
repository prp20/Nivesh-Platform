import asyncio
from pipeline.price_ingestion import _ingest_chunk
from app.database import raw_connection

async def test_sync():
    async with raw_connection() as conn:
        stock = await conn.fetchrow("SELECT id, symbol, yf_symbol FROM stocks WHERE symbol = 'RELIANCE'")
        print(f"Syncing {stock['symbol']}...")
        await _ingest_chunk([dict(stock)], period="5d")
        
        row = await conn.fetchrow("""
            SELECT price_date, close, adj_close 
            FROM price_data 
            WHERE stock_id = $1 
            ORDER BY price_date DESC 
            LIMIT 1
        """, stock['id'])
        print(f"Latest in DB: {dict(row)}")

if __name__ == "__main__":
    asyncio.run(test_sync())
