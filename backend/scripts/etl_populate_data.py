import asyncio
import logging
import pandas as pd
import yfinance as yf
from mftool import Mftool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import sys
import os
import argparse
from datetime import datetime, timedelta
from tqdm import tqdm

# Add the project root to sys.path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import AsyncSessionLocal
from app import crud, analytics, schemas, models, sync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('etl_populate.log')
    ]
)
logger = logging.getLogger("etl_populate")
ZERO_AUM_COUNT = 0
AUM_LOCK = asyncio.Lock()

LAST_RUN_FILE = os.path.join(os.path.dirname(__file__), ".etl_last_run")

def get_last_run_time():
    """Read the last run timestamp from a persistent file."""
    if os.path.exists(LAST_RUN_FILE):
        with open(LAST_RUN_FILE, "r") as f:
            try:
                return datetime.fromisoformat(f.read().strip())
            except ValueError:
                return None
    return None

def set_last_run_time():
    """Write the current timestamp to the persistent file."""
    with open(LAST_RUN_FILE, "w") as f:
        f.write(datetime.now().isoformat())

def parse_date_nifty(date_str):
    # Input: "23 Feb 2026" or "2026-02-23"
    for fmt in ("%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

async def process_single_benchmark(benchmark, DATA_DIR, TICKER_MAP, pbar=None):
    """Process a single benchmark: fetch data and compute metrics."""
    async with AsyncSessionLocal() as session:
        ticker = TICKER_MAP.get(benchmark.benchmark_code, benchmark.ticker)
        data_fetched = False
        nav_dict = {}

        try:
            # 1. Try yfinance
            bench_yf = yf.Ticker(ticker)
            data = bench_yf.history(period="10y")
            
            if not data.empty:
                nav_dict = {
                    index.date().strftime('%Y-%m-%d'): float(row['Close'])
                    for index, row in data.iterrows()
                }
                data_fetched = True
        except Exception:
            pass

        # 2. Try CSV fallback if yfinance failed or returned empty
        if not data_fetched:
            dir_name = benchmark.benchmark_code
            dir_path = os.path.join(DATA_DIR, dir_name)
            if os.path.exists(dir_path):
                import csv
                from pathlib import Path
                csv_files = list(Path(dir_path).glob("*.csv"))
                for csv_file in csv_files:
                    with open(csv_file, mode='r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            date_val = row.get("Date") or row.get("date")
                            close_val = row.get("Close") or row.get("close")
                            if date_val and close_val:
                                iso_date = parse_date_nifty(date_val)
                                if iso_date:
                                    try:
                                        nav_dict[iso_date] = float(close_val.replace(",", ""))
                                    except ValueError:
                                        continue
                if nav_dict:
                    data_fetched = True

        if data_fetched:
            try:
                await crud.bulk_insert_benchmark_navs(session, benchmark.benchmark_code, nav_dict)
                
                nav_history = await crud.get_benchmark_nav_history(session, benchmark.benchmark_code, limit=3000)
                if nav_history:
                    nav_list = [{"nav_date": n.nav_date, "nav_value": float(n.index_value)} for n in nav_history]
                    calc_results = analytics.compute_all_metrics(nav_list, None)
                    
                    metrics_payload = {
                        "benchmark_code": benchmark.benchmark_code,
                        "current_nav": calc_results["current_nav"],
                        "nav_date": calc_results["nav_date"],
                        "rolling_return_3year": calc_results.get("rolling_return_3year"),
                        "rolling_return_5year": calc_results.get("rolling_return_5year"),
                        "sharpe_ratio": calc_results.get("sharpe"),
                        "sortino_ratio": calc_results.get("sortino"),
                        "standard_deviation": calc_results.get("std_dev"),
                        "maximum_drawdown": calc_results.get("max_drawdown"),
                        "metrics_calculated_at": datetime.now()
                    }
                    await crud.upsert_benchmark_metrics(session, metrics_payload)
            except Exception as e:
                logger.error(f"Error saving {benchmark.benchmark_code}: {e}")
        
        if pbar:
            pbar.update(1)

async def update_benchmarks(session: AsyncSession):
    """Fetch historical data for benchmarks concurrently."""
    logger.info("Step 1: Updating Benchmarks...")
    benchmarks, _ = await crud.get_all_benchmark_masters(session, is_active=True)
    
    TICKER_MAP = {
        "NIFTY50": "^NSEI",
        "NIFTYNEXT50": "^NSMID400", # Or similar, actually ^NSEI is best for test
        "NIFTYMIDCAP150": "^NSEMDCP100",
        "NIFTYSMALLCAP250": "^NSESCP",
    }
    DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'Nifty_indices')
    
    semaphore = asyncio.Semaphore(2)
    async def wrapped_process(b):
        async with semaphore:
            await process_single_benchmark(b, DATA_DIR, TICKER_MAP, pbar)

    with tqdm(total=len(benchmarks), desc="Benchmarks Progress") as pbar:
        tasks = [wrapped_process(b) for b in benchmarks]
        await asyncio.gather(*tasks)

async def process_single_fund(fund_code: str, semaphore: asyncio.Semaphore, pbar: tqdm):
    """Worker task to update a single fund's data and metrics."""
    global ZERO_AUM_COUNT
    async with semaphore:
        async with AsyncSessionLocal() as session:
            try:
                # sync_fund_data internally fetches NAVs AND RECOMPUTES METRICS
                aum = await sync.sync_fund_data(session, fund_code)
                if aum is None or aum == 0.0:
                    async with AUM_LOCK:
                        ZERO_AUM_COUNT += 1
            except Exception as e:
                logger.error(f"Error updating fund {fund_code}: {e}")
            finally:
                pbar.update(1)

async def update_funds(session: AsyncSession, max_concurrency: int = 5):
    """Fetch historical data for mutual funds using a worker pool."""
    logger.info(f"Step 2: Updating Mutual Funds (Concurrency={max_concurrency})...")
    logger.info("NOTE: Metrics are computed automatically for each fund during sync.")
    funds = await crud.get_all_fund_masters(session, is_active=True, limit=10000)
    
    semaphore = asyncio.Semaphore(max_concurrency)
    with tqdm(total=len(funds), desc="Funds Progress") as pbar:
        tasks = [process_single_fund(fund.scheme_code, semaphore, pbar) for fund in funds]
        await asyncio.gather(*tasks)

async def main():
    parser = argparse.ArgumentParser(description="Mutual Fund ETL Pipeline")
    parser.add_argument("--force", action="store_true", help="Force run the ETL even if run recently")
    args = parser.parse_args()

    last_run = get_last_run_time()
    if not args.force and last_run:
        elapsed = datetime.now() - last_run
        if elapsed < timedelta(hours=24):
            remaining = timedelta(hours=24) - elapsed
            logger.info(f"ETL was run recently ({elapsed.total_seconds()/3600:.1f} hours ago).")
            logger.info(f"Skipping sync. Use --force to override. Next run allowed in {remaining.total_seconds()/3600:.1f} hours.")
            return

    # 1. Update Benchmarks first
    async with AsyncSessionLocal() as session:
        await update_benchmarks(session)
    
    # 2. Update Mutual Fund NAVs and Metrics
    async with AsyncSessionLocal() as session:
        await update_funds(session, max_concurrency=5)
        
    set_last_run_time()
    logger.info("ETL population complete.")
    logger.info(f"Summary: Total funds with 0.0 AUM: {ZERO_AUM_COUNT}")

if __name__ == "__main__":
    asyncio.run(main())
