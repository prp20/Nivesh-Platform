from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any
import logging
from ..state import FundScoringState

logger = logging.getLogger(__name__)

async def fetch_fund_data_node(state: FundScoringState, db: AsyncSession) -> Dict[str, Any]:
    """
    Fetches mutual fund master and metrics from the database.
    """
    scheme_code = state["scheme_code"]
    
    try:
        # Fetch Master Data
        master_sql = text("SELECT scheme_name, scheme_category FROM fund_master WHERE scheme_code = :code")
        master_result = await db.execute(master_sql, {"code": scheme_code})
        master = master_result.fetchone()
        
        if not master:
            return {"status": "FAILED", "error": f"Fund {scheme_code} not found"}
            
        # Fetch Metrics
        metrics_sql = text("SELECT * FROM fund_metrics WHERE scheme_code = :code")
        metrics_result = await db.execute(metrics_sql, {"code": scheme_code})
        metrics_row = metrics_result.fetchone()
        
        if not metrics_row:
            return {"status": "FAILED", "error": f"Metrics for fund {scheme_code} not found"}
            
        metrics = dict(metrics_row._mapping)
        
        # Calculate a simple composite score for the UI (0-100)
        # We can use a weighted average of some key metrics
        # For funds: Sharpe, Alpha, CAGR_3Y, Rating
        sharpe = float(metrics.get("sharpe_ratio") or 0)
        alpha = float(metrics.get("alpha") or 0)
        cagr = float(metrics.get("cagr_3year") or 0)
        rating = float(metrics.get("fund_rating") or 0)
        
        # Normalize and weight
        # Sharpe > 1 is good (30%)
        # Alpha > 0.05 is good (30%)
        # CAGR > 0.15 is good (20%)
        # Rating 1-5 (20%)
        
        s_score = min(max(sharpe / 1.5 * 100, 0), 100)
        a_score = min(max(alpha / 0.1 * 100, 0), 100)
        c_score = min(max(cagr / 0.2 * 100, 0), 100)
        r_score = (rating / 5) * 100 if rating else 50
        
        composite = (s_score * 0.3) + (a_score * 0.3) + (c_score * 0.2) + (r_score * 0.2)
        
        return {
            "scheme_name": master.scheme_name,
            "category": master.scheme_category,
            "metrics": metrics,
            "composite_score": round(composite, 2),
            "status": "FETCHED",
            "logs": state["logs"] + ["Fund data and metrics fetched successfully"]
        }
        
    except Exception as e:
        logger.error(f"Error in fetch_fund_data_node: {e}")
        return {"status": "FAILED", "error": str(e)}
