import asyncio
import logging
from typing import Optional
from datetime import datetime
from mftool import Mftool
from sqlalchemy.ext.asyncio import AsyncSession
from . import crud, analytics

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
            if job_id: await crud.update_sync_job(session, job_id, status="FAILED", message="Fund master not found")
            return

        await update_progress("Downloading historical NAV data...")
        # 1. Fetch from mftool
        nav_data = mf.get_scheme_historical_nav(scheme_code, as_Dataframe=True)
        if nav_data is None or nav_data.empty:
            logger.warning(f"No NAV data found for {scheme_code}")
            if job_id: await crud.update_sync_job(session, job_id, status="FAILED", message="No NAV data found")
            return
        
        # 2. Transform to dict
        nav_dict = {
            pd_to_date(date_str): float(row['nav'])
            for date_str, row in nav_data.iterrows()
        }
        
        await update_progress(f"Storing {len(nav_dict)} NAV records...")
        # 3. Bulk insert NAVs
        await crud.bulk_insert_fund_navs(session, scheme_code, nav_dict)
        
        await update_progress("Fetching AUM and scheme details...")
        # 4. Fetch AUM (Attempt)
        aum = None
        try:
            details = mf.get_scheme_details(scheme_code)
            # mftool details sometimes have AUM
        except Exception as e:
            logger.warning(f"Failed to fetch scheme details for {scheme_code}: {e}")

        # 5. Get Benchmark History if available
        benchmark_history_list = None
        if fund_master.benchmark_index_code:
            await update_progress(f"Loading benchmark history ({fund_master.benchmark_index_code})...")
            bench_history = await crud.get_benchmark_nav_history(session, fund_master.benchmark_index_code, limit=2000)
            if bench_history:
                benchmark_history_list = [{"nav_date": b.nav_date, "index_value": float(b.index_value)} for b in bench_history]

        await update_progress("Computing complex financial metrics...")
        # 6. Recompute Metrics
        nav_history = await crud.get_fund_nav_history(session, scheme_code, limit=2000)
        nav_list = [{"nav_date": n.nav_date, "nav_value": float(n.nav_value)} for n in nav_history]
        
        calc_results = analytics.compute_all_metrics(nav_list, benchmark_history_list)
        
        metrics_payload = {
            "scheme_code": scheme_code,
            "current_nav": calc_results["current_nav"],
            "nav_date": calc_results["nav_date"],
            "aum_in_crores": aum,
            "rolling_return_3year": calc_results.get("rolling_return_3year"),
            "rolling_return_5year": calc_results.get("rolling_return_5year"),
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

def pd_to_date(date_str):
    # mftool returns DD-MM-YYYY
    from datetime import datetime
    return datetime.strptime(date_str, "%d-%m-%Y").strftime("%Y-%m-%d")

async def sync_all_funds(session: AsyncSession):
    """Sync all active funds in the database."""
    funds = await crud.get_all_fund_masters(session, is_active=True)
    for fund in funds:
        await sync_fund_data(session, fund.scheme_code)
        # Polite throttling
        await asyncio.sleep(1)
