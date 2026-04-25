import asyncio
from app.database import raw_connection
from decimal import Decimal

async def check_nan_inf():
    async with raw_connection() as conn:
        print("Checking for NaN or Infinity in financial_ratios...")
        rows = await conn.fetch("SELECT * FROM financial_ratios WHERE stock_id=10")
        for r in rows:
            for k, v in r.items():
                if isinstance(v, Decimal):
                    if v.is_infinite() or v.is_nan():
                        print(f"Found non-finite Decimal in {k}: {v} for period_end {r['period_end']}")
                elif isinstance(v, float):
                    import math
                    if math.isinf(v) or math.isnan(v):
                        print(f"Found non-finite float in {k}: {v} for period_end {r['period_end']}")

        print("\nChecking for NaN or Infinity in technical_indicators...")
        rows = await conn.fetch("SELECT * FROM technical_indicators WHERE stock_id=10")
        for r in rows:
            for k, v in r.items():
                if isinstance(v, Decimal):
                    if v.is_infinite() or v.is_nan():
                        print(f"Found non-finite Decimal in {k}: {v} for date {r['ind_date']}")

if __name__ == "__main__":
    asyncio.run(check_nan_inf())
