from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import crud, schemas, analytics

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/{scheme_code}", response_model=schemas.FundMetricsRead)
async def get_metrics(scheme_code: str, session: AsyncSession = Depends(get_db)):
    metrics = await crud.get_fund_metrics(session, scheme_code)
    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found for this fund")
    return metrics

@router.post("/{scheme_code}/compute", status_code=200)
async def compute_metrics(scheme_code: str, session: AsyncSession = Depends(get_db)):
    # 1. Fetch NAV History
    nav_history = await crud.get_fund_nav_history(session, scheme_code, limit=1000)
    if not nav_history:
        raise HTTPException(status_code=400, detail="Insufficient NAV data to compute metrics")
    
    # 2. Convert to dict for analytics engine
    nav_data = [{"nav_date": n.nav_date, "nav_value": float(n.nav_value)} for n in nav_history]
    
    # 3. Calculate
    calc_results = analytics.compute_all_metrics(nav_data)
    
    # 4. Save to DB
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
    
    return {"message": "Metrics computed successfully", "metrics": metrics_payload}
