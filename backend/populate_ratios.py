import asyncio
from pipeline.ratio_engine import compute_ratios_for_stock, _get_latest_close

async def main(stock_id):
    latest_close = await _get_latest_close(stock_id)
    print(f"Computing ratios for stock_id={stock_id} with close={latest_close}")
    await compute_ratios_for_stock(stock_id, latest_close)
    print("Done")

if __name__ == "__main__":
    asyncio.run(main(10))
