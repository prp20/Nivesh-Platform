import sys
import os
import time
import logging
import json
import pandas as pd
from datetime import datetime, timezone
from tqdm import tqdm
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert
from mftool import Mftool

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import analytics, models, config

# Setup Synchronous Database Connection
# Convert async URLs to sync: strip both +asyncpg (PostgreSQL) and +aiosqlite (SQLite)
import re
SYNC_DB_URL = re.sub(r'\+(asyncpg|aiosqlite)', '', config.settings.DATABASE_URL)
engine = create_engine(SYNC_DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sync_data_sync")

mf = Mftool()

def pd_to_date(date_str):
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return date_str

def sync_fund_data_sync(session, scheme_code, period="max"):
    """
    Synchronous implementation of sync_fund_data.
    Returns (success: bool, reason: str)
    """
    try:
        # 0. Get fund master record
        fund_master = session.query(models.FundMaster).filter_by(scheme_code=scheme_code).first()
        if not fund_master:
            return False, "Fund not found in master table"

        # 1. Fetch NAVs from mftool
        nav_list = None
        fetch_error = None
        for attempt in range(3):
            try:
                # mftool call is blocking/sync with as_json=True returns a dict with a 'data' key
                fetched = json.loads(mf.get_scheme_historical_nav(scheme_code, as_json=True))
                if fetched and isinstance(fetched, dict) and "data" in fetched:
                    nav_list = fetched["data"]
                    if nav_list:
                        break
                    else:
                        fetch_error = "Successful API call but empty data list"
                elif isinstance(fetched, list):
                    # Fallback for older versions or unexpected list return
                    nav_list = fetched
                    break
                else:
                    fetch_error = "Empty or malformed JSON response from AMFI"
            except Exception as e:
                fetch_error = str(e)
                if attempt < 2:
                    time.sleep(2)
        
        if not nav_list:
            return False, f"NAV fetch failed: {fetch_error}"

        # 2. Process NAVs & Filter by Period
        limit_date = None
        if period != "max":
            try:
                years = int(period.replace("y", ""))
                limit_date = datetime.now().date() - pd.Timedelta(days=years*365.25)
            except:
                pass

        nav_dict = {}
        processed_navs = []
        for item in nav_list:
            d = item.get('date')
            v = item.get('nav')
            if d and v:
                try:
                    date_obj = pd_to_date(str(d))
                    
                    # Apply period filter
                    if limit_date and date_obj < limit_date:
                        continue

                    nav_val = float(v)
                    if nav_val > 0:
                        nav_dict[date_obj] = nav_val
                        processed_navs.append({
                            "scheme_code": scheme_code,
                            "nav_date": date_obj,
                            "nav_value": nav_val
                        })
                except (ValueError, TypeError):
                    continue

        if not processed_navs:
            return False, f"No valid NAV records found for the requested period ({period})"

        # 3. Bulk Upsert NAVs
        # ... rest of the function ...
        stmt = pg_insert(models.FundNavHistory).values(processed_navs)
        stmt = stmt.on_conflict_do_update(
            index_elements=['scheme_code', 'nav_date'],
            set_=dict(nav_value=stmt.excluded.nav_value)
        )
        session.execute(stmt)

        # 4. Fetch AUM and metrics from Captnemo/Kuvera
        # ... (lines 109-147 unchanged) ...
        aum = 0.0
        expense_ratio = None
        fund_rating = None
        volatility = None
        
        isin = fund_master.isin
        if isin:
            try:
                import requests
                # Use headers to mimic browser for the API call
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                # Captnemo API lookup
                resp = requests.get(f"https://mf.captnemo.in/kuvera/{isin}", headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    # Kuvera response is usually a list
                    fund_data = data[0] if isinstance(data, list) and data else {}
                    if fund_data:
                        # aum is in Millions, convert to Crores (/ 10.0)
                        a_val = fund_data.get("aum")
                        aum = (float(a_val) / 10.0) if a_val else 0.0
                        
                        te_val = fund_data.get("expense_ratio")
                        expense_ratio = float(te_val) / 100.0 if te_val is not None else None
                        
                        fund_rating = float(fund_data.get("fund_rating")) if fund_data.get("fund_rating") else None
                        volatility = float(fund_data.get("volatility")) if fund_data.get("volatility") else None
                elif resp.status_code == 404:
                    pass
                else:
                    pass
            except Exception as e:
                pass

        # 5. Compute Metrics
        bench_code = fund_master.benchmark_index_code
        benchmark_history = []
        if bench_code:
            bench_recs = session.query(models.BenchmarkNavHistory).filter_by(benchmark_code=bench_code).all()
            benchmark_history = [{"nav_date": b.nav_date, "index_value": float(b.index_value)} for b in bench_recs]

        # nav_list for analytics should contain all historical NAVs
        all_navs = session.query(models.FundNavHistory).filter_by(scheme_code=scheme_code).all()
        analytics_nav_list = [{"nav_date": n.nav_date, "nav_value": float(n.nav_value)} for n in all_navs]
        
        calc_results = analytics.compute_all_metrics(analytics_nav_list, benchmark_history)
        
        if not calc_results or "current_nav" not in calc_results:
            return False, "Insufficient data to compute financial metrics"

        # 6. Upsert Metrics
        metrics_payload = {
            "scheme_code": scheme_code,
            "current_nav": calc_results["current_nav"],
            "nav_date": calc_results["nav_date"],
            "aum_in_crores": aum,
            "expense_ratio": expense_ratio,
            "fund_rating": fund_rating,
            "volatility": volatility,
            "calculation_period_start_date": calc_results.get("calculation_period_start_date"),
            "calculation_period_end_date": calc_results.get("calculation_period_end_date"),
            "has_sufficient_data": calc_results.get("has_sufficient_data", True),
            "final_verdict": calc_results.get("final_verdict"),
            "metrics_calculated_at": datetime.now(timezone.utc)
        }
        # Add other metric fields from calc_results
        metric_fields = [
            "cagr_3year", "cagr_5year", "absolute_return_1y", "absolute_return_3y", 
            "absolute_return_5y", "absolute_return_10y", "short_term_return_6m",
            "upside_capture", "downside_capture", "sortino_ratio", "sharpe_ratio",
            "alpha", "beta", "standard_deviation", "maximum_drawdown", "tracking_error",
            "information_ratio", "data_completeness_percentage"
        ]
        # Mapping names if they differ
        mapping = {"sharpe": "sharpe_ratio", "sortino": "sortino_ratio", "std_dev": "standard_deviation", "max_drawdown": "maximum_drawdown"}
        for field in metric_fields:
            src_key = next((k for k, v in mapping.items() if v == field), field)
            metrics_payload[field] = calc_results.get(src_key)

        stmt_m = pg_insert(models.FundMetrics).values(metrics_payload)
        stmt_m = stmt_m.on_conflict_do_update(
            index_elements=['scheme_code'],
            set_={k: v for k, v in metrics_payload.items() if k != 'scheme_code'}
        )
        session.execute(stmt_m)
        session.commit()
        
        return True, "Success"

    except Exception as e:
        session.rollback()
        return False, f"Unexpected error: {str(e)}"

def main():
    print("==========================================================")
    print("    SYNCHRONOUS DATA INGESTION & SYNC PIPELINE          ")
    print("==========================================================")
    
    period = sys.argv[1] if len(sys.argv) > 1 else "max"
    
    with SessionLocal() as session:
        funds = session.query(models.FundMaster).filter_by(is_active=True).all()
        
        if not funds:
            print("No active funds found to sync.")
            return

        print(f"Syncing {len(funds)} funds for period '{period}'...")
        fail_count = 0
        max_fails = 5
        
        with tqdm(total=len(funds), desc="Sync Progress") as pbar:
            for f in funds:
                success, reason = sync_fund_data_sync(session, f.scheme_code, period=period)
                if not success:
                    # Fallback logic for Mutual Funds: if requested period fails, try fewer years
                    if period != "max":
                        # Try max (which ironically might have more success if it bypasses some filtering logic)
                        # or try 1y if 5y failed.
                        pass # mftool is different, it always gives full history. Filtering is our choice.
                    
                    fail_count += 1
                    tqdm.write(f"[-] Code {f.scheme_code} failed: {reason}")
                    
                    if fail_count > max_fails:
                        print(f"\nCRITICAL: Synchronization aborted after {fail_count} failures.")
                        sys.exit(1)
                pbar.update(1)
        
        print(f"\nSync complete. Total failures: {fail_count}")

if __name__ == "__main__":
    main()
