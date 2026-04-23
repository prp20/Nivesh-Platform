import asyncio
from app.database import raw_connection

async def check_fundamentals():
    symbol = 'ASIANPAINT'
    async with raw_connection() as conn:
        stock = await conn.fetchrow("SELECT id, symbol FROM stocks WHERE symbol = $1", symbol)
        if not stock:
            print(f"Stock {symbol} not found")
            return
        
        print(f"Stock ID: {stock['id']} ({stock['symbol']})")
        
        # Check financial statements
        stmt_counts = await conn.fetch("""
            SELECT statement_type, period_type, COUNT(*) as count
            FROM financial_statements
            WHERE stock_id = $1
            GROUP BY statement_type, period_type
        """, stock['id'])
        
        print("\nStatement counts:")
        if not stmt_counts:
            print("No financial statements found in database.")
        else:
            for r in stmt_counts:
                print(dict(r))

if __name__ == "__main__":
    asyncio.run(check_fundamentals())
