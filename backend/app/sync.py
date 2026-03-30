import asyncio
import logging
import pandas as pd
from typing import Optional
from datetime import datetime
from mftool import Mftool
from sqlalchemy.ext.asyncio import AsyncSession
from . import crud, analytics, schemas

logger = logging.getLogger(__name__)

async def sync_fund_data(session: AsyncSession, scheme_code: str, job_id: Optional[str] = None):
    """Fetch latest NAV and recompute metrics for a single fund."""
    mf = Mftool()
    
    async def update_progress(msg: str):
        if job_id:
            await crud.update_sync_job(session, job_id, message=msg)
            logger.info(f"Job {job_id} [{scheme_code}]: {msg}")

    try:
        await update_progress("Fetching fund metadata...")
        # 0. Get fund master to find benchmark code
        fund_master = await crud.get_fund_master_by_code(session, scheme_code)
        if not fund_master:
            logger.error(f"Fund master not found for {scheme_code}")
            if job_id: 
                await crud.update_sync_job(session, job_id, status="FAILED", message="Fund master not found")
            return

        await update_progress("Downloading historical NAV data...")
        # 1. Fetch from mftool with retry
        nav_df = None
        for attempt in range(3):
            try:
                # mftool returns DataFrame or None
                fetched = mf.get_scheme_historical_nav(scheme_code, as_Dataframe=True)
                if fetched is not None and not fetched.empty:
                    nav_df = fetched
                    break
            except Exception as e:
                if attempt == 2: raise e
                wait_time = (attempt + 1) * 3
                await update_progress(f"NAV Fetch Attempt {attempt+1} failed. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

        if nav_df is None:
            logger.warning(f"No NAV data found for {scheme_code}")
            if job_id: 
                await crud.update_sync_job(session, job_id, status="FAILED", message="No NAV data found")
            return
        
        # 2. Transform to dict - handle index as date
        nav_dict = {
            pd_to_date(str(date_val)): float(row['nav'])
            for date_val, row in nav_df.iterrows()
        }
        
        await update_progress(f"Storing {len(nav_dict)} NAV records...")
        # 3. Bulk insert NAVs
        await crud.bulk_insert_fund_navs(session, scheme_code, nav_dict)
        
        # 4. Fetch AUM and ISIN from details
        aum = None
        isin = fund_master.isin
        try:
            details = mf.get_scheme_details(scheme_code)
            if details and isinstance(details, dict):
                # Try to extract AUM
                raw_aum = details.get("fund_house_aum") or details.get("aum")
                if raw_aum:
                    try:
                        aum = float(str(raw_aum).replace(",", "").split()[-1])
                    except (ValueError, IndexError):
                        pass
                
                # Try to extract ISIN if not already present
                if not isin:
                    # Some versions of mftool/API might return ISIN in details
                    isin = details.get("isin") or details.get("isin_code")
                    if isin:
                        await crud.update_fund_master(session, scheme_code, schemas.FundMasterUpdate(isin=isin))
        except Exception as e:
            logger.warning(f"Failed to fetch scheme details for {scheme_code}: {e}")

        # 4.1 Fetch Expense Ratio (TER) if ISIN is available
        if isin:
            await update_progress(f"Fetching Expense Ratio for ISIN {isin}...")
            try:
                import requests
                ter_url = f"https://mf.captnemo.in/kuvera/{isin}"
                resp = requests.get(ter_url, timeout=10)
                if resp.status_code == 200:
                    ter_data = resp.json()
                    if isinstance(ter_data, list) and len(ter_data) > 0:
                        ter_val = ter_data[0].get("expense_ratio")
                        if ter_val is not None:
                            await crud.upsert_fund_expense_ratio(session, {
                                "scheme_code": scheme_code,
                                "expense_ratio": float(ter_val) / 100.0, # Convert percentage to decimal
                                "as_of_date": datetime.now().date()
                            })
            except Exception as e:
                logger.warning(f"Failed to fetch expense ratio for {scheme_code}: {e}")

        # 5. Get Benchmark History if available
        benchmark_history_list = None
        if fund_master.benchmark_index_code:
            await update_progress(f"Loading benchmark history ({fund_master.benchmark_index_code})...")
            bench_history = await crud.get_benchmark_nav_history(session, fund_master.benchmark_index_code, limit=2000)
            if bench_history:
                benchmark_history_list = [{"nav_date": b.nav_date, "index_value": float(b.index_value)} for b in bench_history]

        await update_progress("Computing complex financial metrics...")
        # 6. Recompute Metrics
        nav_history = await crud.get_fund_nav_history(session, scheme_code, limit=2500)
        nav_list = [{"nav_date": n.nav_date, "nav_value": float(n.nav_value)} for n in nav_history]
        
        calc_results = analytics.compute_all_metrics(nav_list, benchmark_history_list)
        
        # Guard against empty calculation results
        if not calc_results or "current_nav" not in calc_results:
            logger.warning(f"Insufficient data to compute metrics for {scheme_code}")
            if job_id:
                await crud.update_sync_job(session, job_id, status="FAILED", message="Insufficient data for analysis")
            return

        metrics_payload = {
            "scheme_code": scheme_code,
            "current_nav": calc_results["current_nav"],
            "nav_date": calc_results["nav_date"],
            "aum_in_crores": aum,
            "rolling_return_3year": calc_results.get("rolling_return_3year"),
            "rolling_return_5year": calc_results.get("rolling_return_5year"),
            "absolute_return_1y": calc_results.get("absolute_return_1y"),
            "absolute_return_3y": calc_results.get("absolute_return_3y"),
            "absolute_return_5y": calc_results.get("absolute_return_5y"),
            "absolute_return_10y": calc_results.get("absolute_return_10y"),
            "short_term_return_6m": calc_results.get("short_term_return_6m"),
            "upside_capture": calc_results.get("upside_capture"),
            "downside_capture": calc_results.get("downside_capture"),
            "sharpe_ratio": calc_results.get("sharpe"),
            "sortino_ratio": calc_results.get("sortino"),
            "alpha": calc_results.get("alpha"),
            "beta": calc_results.get("beta"),
            "standard_deviation": calc_results.get("std_dev"),
            "maximum_drawdown": calc_results.get("max_drawdown"),
            "tracking_error": calc_results.get("tracking_error"),
            "information_ratio": calc_results.get("information_ratio"),
            "metrics_calculated_at": datetime.now()
        }
        await crud.upsert_fund_metrics(session, metrics_payload)
        
        if job_id:
            await crud.update_sync_job(session, job_id, status="COMPLETED", message="Analysis complete")
        logger.info(f"Successfully synced {scheme_code}")
        
    except Exception as e:
        logger.error(f"Error syncing {scheme_code}: {e}")
        if job_id:
            await crud.update_sync_job(session, job_id, status="FAILED", message=str(e))

def pd_to_date(date_str: str) -> str:
    """Standardizes date formats from mftool (often DD-MM-YYYY) to YYYY-MM-DD."""
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str

async def sync_all_funds(session: AsyncSession):
    """Sync all active funds in the database."""
    funds_list = await crud.get_all_fund_masters(session, is_active=True)
    for fund in funds_list:
        await sync_fund_data(session, fund.scheme_code)
        # Polite throttling
        await asyncio.sleep(1)
