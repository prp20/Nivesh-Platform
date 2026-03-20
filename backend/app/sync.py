import asyncio
import logging
from datetime import datetime
from mftool import Mftool
from sqlalchemy.ext.asyncio import AsyncSession
from . import crud, analytics

logger = logging.getLogger(__name__)

async def sync_fund_data(session: AsyncSession, scheme_code: str):
    """Fetch latest NAV and recompute metrics for a single fund."""
    mf = Mftool()
    try:
        # 1. Fetch from mftool
        nav_data = mf.get_scheme_historical_nav(scheme_code, as_Dataframe=True)
        if nav_data is None or nav_data.empty:
            logger.warning(f"No data found for {scheme_code}")
            return
        
        # 2. Transform to dict
        nav_dict = {
            pd_to_date(date_str): float(row['nav'])
            for date_str, row in nav_data.iterrows()
        }
        
        # 3. Bulk insert NAVs
        await crud.bulk_insert_fund_navs(session, scheme_code, nav_dict)
        
        # 4. Recompute Metrics
        nav_history = await crud.get_fund_nav_history(session, scheme_code, limit=1000)
        nav_list = [{"nav_date": n.nav_date, "nav_value": float(n.nav_value)} for n in nav_history]
        calc_results = analytics.compute_all_metrics(nav_list)
        
        metrics_payload = {
            "scheme_code": scheme_code,
            "current_nav": calc_results["current_nav"],
            "nav_date": calc_results["nav_date"],
            "sharpe_ratio": calc_results["sharpe"],
            "sortino_ratio": calc_results["sortino"],
            "standard_deviation": calc_results["std_dev"],
            "maximum_drawdown": calc_results["max_drawdown"]
        }
        await crud.upsert_fund_metrics(session, metrics_payload)
        logger.info(f"Successfully synced {scheme_code}")
        
    except Exception as e:
        logger.error(f"Error syncing {scheme_code}: {e}")

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
