import asyncio
from app.database import raw_connection

async def check():
    async with raw_connection() as conn:
        print("Stock Basic Info (stocks table):")
        row = await conn.fetchrow("SELECT id, symbol, company_name FROM stocks WHERE symbol='ASIANPAINT'")
        print(dict(row))
        
        print("\nLatest Ratios (financial_ratios table):")
        ratio = await conn.fetchrow("""
            SELECT pe_ratio, pb_ratio, roe, roce, piotroski_f_score, 
                   dividend_yield, dividend_per_share, debt_equity,
                   revenue_growth, pat_growth, eps_growth,
                   fcf, asset_turnover, inventory_turnover
            FROM financial_ratios 
            WHERE stock_id=10 AND period_type = 'annual'
            ORDER BY period_end DESC LIMIT 1
        """)
        print(dict(ratio) if ratio else "None found")
        
        print("\nTechnical Indicators (technical_indicators table):")
        ti = await conn.fetchrow("""
            SELECT rsi_14, macd_hist, sma_200, sma_50, obv, rs_6m_vs_nifty
            FROM technical_indicators 
            WHERE stock_id=10 
            ORDER BY ind_date DESC LIMIT 1
        """)
        print(dict(ti) if ti else "None found")

if __name__ == "__main__":
    asyncio.run(check())
