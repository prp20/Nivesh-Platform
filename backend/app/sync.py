import asyncio
import logging
import pandas as pd
from typing import Optional
from datetime import datetime, timezone
from mftool import Mftool
from sqlalchemy.ext.asyncio import AsyncSession
from . import crud, analytics, schemas
from .database import session_factory
import requests
import json

logger = logging.getLogger(__name__)

BASE_CAPTNEMO = "https://mf.captnemo.in"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def get_aum_by_isin(isin: str) -> dict | None:
    """
    Fetch AUM, expense ratio, fund manager, and returns for a fund by ISIN.
    Uses Kuvera data via Captnemo's static API.

    NOTE: Only works for ISINs listed on the Kuvera platform.
          Use get_nav_by_isin() as a fallback for non-Kuvera ISINs.

    Returns dict with AUM data, or None if ISIN not found.
    """
    try:
        resp = requests.get(f"{BASE_CAPTNEMO}/kuvera/{isin}", headers=HEADERS, timeout=10)

        if resp.status_code == 404:
            logger.warning(f"ISIN {isin} not found on Kuvera.")
            return None

        resp.raise_for_status()
        data = resp.json()

        # Response is a LIST — index [0]
        fund = data[0] if isinstance(data, list) and data else {}

        return {
            "isin":           isin,
            "name":           fund.get("name"),
            "aum_cr":         float(fund.get("aum")) if fund.get("aum") else 0.0, # Captnemo API returns values in Crores
            "category":       fund.get("category"),
            "fund_type":      fund.get("fund_type"),
            "fund_category":  fund.get("fund_category"),
            "expense_ratio":  fund.get("expense_ratio"),
            "fund_manager":   fund.get("fund_manager"),
            "fund_rating":    fund.get("fund_rating"),
            "last_nav":       fund.get("last_nav"),        # {date, nav}
            "returns":        fund.get("returns"),         # {inception, year_1, year_3, year_5}
            "maturity_type":  fund.get("maturity_type"),
            "start_date":     fund.get("start_date"),
            "volatility":     fund.get("volatility"),
        }
    except Exception as e:
        logger.error(f"Error in get_aum_by_isin for {isin}: {e}")
        return None

async def sync_fund_data(session: AsyncSession, scheme_code: str, job_id: Optional[str] = None) -> Optional[float]:
    """Fetch latest NAV and recompute metrics for a single fund. Returns AUM if found."""
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
                fetched = await asyncio.to_thread(
                    mf.get_scheme_historical_nav, scheme_code, True
                )
                if fetched is not None and len(fetched) > 0:
                    if isinstance(fetched, pd.DataFrame):
                        nav_list = []
                        for date_val, row in fetched.iterrows():
                            nav_list.append({"date": str(date_val), "nav": row.get('nav', row.get('nav_value'))})
                    elif isinstance(fetched, list):
                        nav_list = fetched
                    else:
                        continue
                    
                    nav_df = nav_list
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

        # 2. Transform to dict - handle various date formats
        nav_dict = {}
        for item in nav_df:
            d = item.get('date')
            v = item.get('nav')
            if d and v:
                nav_dict[pd_to_date(str(d))] = float(v)
        
        await update_progress(f"Storing {len(nav_dict)} NAV records...")
        # 3. Bulk insert NAVs
        await crud.bulk_insert_fund_navs(session, scheme_code, nav_dict)
        
        # 4. Fetch AUM and metadata using ISIN/Details
        aum = 0.0
        isin = fund_master.isin
        
        # 4.1 Try mftool details first for ISIN if missing
        if not isin:
            try:
                details = await asyncio.to_thread(mf.get_scheme_details, scheme_code)
                if details and isinstance(details, dict):
                    isin = details.get("isin") or details.get("isin_code")
                    if isin:
                        await crud.update_fund_master(session, scheme_code, schemas.FundMasterUpdate(isin=isin))
            except Exception as e:
                logger.warning(f"Failed to fetch ISIN from mftool for {scheme_code}: {e}")

        # 4.2 Fetch AUM and TER from Captnemo/Kuvera if ISIN is available
        # FALLBACK: When Kuvera/ISIN is unavailable, AUM/expense_ratio/fund_rating default to None
        # This prioritises local generation over external fetch (as per architecture guidelines)
        if isin:
            await update_progress(f"Fetching AUM and Expense Ratio for ISIN {isin}...")
            fund_data = await asyncio.to_thread(get_aum_by_isin, isin)
            if fund_data:
                aum = fund_data.get("aum_cr") or 0.0
                ter_val = fund_data.get("expense_ratio")
                expense_ratio = float(ter_val) / 100.0 if ter_val is not None else None
                fund_rating = float(fund_data.get("fund_rating")) if fund_data.get("fund_rating") else None
                volatility = float(fund_data.get("volatility")) if fund_data.get("volatility") else None
            else:
                logger.warning(f"No Kuvera data for ISIN {isin}, external fetch failed, using defaults")
                expense_ratio = None
                fund_rating = None
                volatility = None
                aum = 0.0
        else:
            expense_ratio = None
            fund_rating = None
            volatility = None
            aum = 0.0
            logger.warning(f"No ISIN available for {scheme_code}, cannot fetch from Kuvera")

        # 5. Get Benchmark History if available
        benchmark_history_list = None
        if fund_master.benchmark_index_code:
            await update_progress(f"Loading benchmark history ({fund_master.benchmark_index_code})...")
            bench_history = await crud.get_benchmark_nav_history(session, fund_master.benchmark_index_code, limit=5000)
            if bench_history:
                benchmark_history_list = [{"nav_date": b.nav_date, "index_value": float(b.index_value)} for b in bench_history]

        await update_progress("Computing complex financial metrics...")
        # 6. Recompute Metrics
        nav_history = await crud.get_fund_nav_history(session, scheme_code, limit=5000)
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
            "expense_ratio": expense_ratio,
            "fund_rating": fund_rating,
            "volatility": volatility,
            "cagr_3year": calc_results.get("cagr_3year"),
            "cagr_5year": calc_results.get("cagr_5year"),
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
            "final_verdict": calc_results.get("final_verdict"),
            "calculation_period_start_date": calc_results.get("calculation_period_start_date"),
            "calculation_period_end_date": calc_results.get("calculation_period_end_date"),
            "data_completeness_percentage": calc_results.get("data_completeness_percentage"),
            "has_sufficient_data": calc_results.get("has_sufficient_data", True),
            "metrics_calculated_at": datetime.now(timezone.utc)
        }
        await crud.upsert_fund_metrics(session, metrics_payload)
        
        if job_id:
            await crud.update_sync_job(session, job_id, status="COMPLETED", message="Analysis complete")
        logger.info(f"Successfully synced {scheme_code} (AUM: {aum})")
        return aum
        
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
    # Snapshot scheme codes so the listing session can be released promptly
    scheme_codes = [f.scheme_code for f in funds_list]
    for scheme_code in scheme_codes:
        # Dedicated session per fund — failure in one does not contaminate others.
        async with session_factory() as fund_session:
            job, created = await crud.create_sync_job(fund_session, scheme_code)
            if created:
                await sync_fund_data(fund_session, scheme_code, job_id=job.id)
            # If a job already exists (RUNNING), skip to avoid duplicate work.
        # Polite throttling
        await asyncio.sleep(1)
