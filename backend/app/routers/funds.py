from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import crud, schemas

router = APIRouter(prefix="/funds", tags=["funds"])

@router.post("/", response_model=schemas.FundMasterRead, status_code=status.HTTP_201_CREATED)
async def create_fund(fund: schemas.FundMasterCreate, session: AsyncSession = Depends(get_db)):
    existing = await crud.get_fund_master_by_code(session, fund.scheme_code)
    if existing:
        raise HTTPException(status_code=400, detail=f"Fund with scheme_code {fund.scheme_code} already exists")
    return await crud.create_fund_master(session, fund)

@router.get("/", response_model=schemas.FundMasterListResponse)
async def list_funds(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    category: Optional[str] = Query(None, description="Filter by scheme category"),
    amc: Optional[str] = Query(None, description="Filter by AMC name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db)
):
    total = await crud.get_fund_masters_count(session, is_active=is_active, category=category, amc=amc)
    items = await crud.get_all_fund_masters(session, is_active=is_active, category=category, amc=amc, skip=skip, limit=limit)
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": items
    }

@router.get("/compare", response_model=None)
async def compare_funds(
    fund_a: str = Query(..., description="Scheme code for Fund A"),
    fund_b: str = Query(..., description="Scheme code for Fund B"),
    session: AsyncSession = Depends(get_db)
):
    import asyncio
    
    # 1. Fetch masters (which include metrics)
    master_a, master_b = await asyncio.gather(
        crud.get_fund_master_by_code(session, fund_a),
        crud.get_fund_master_by_code(session, fund_b)
    )
    
    if not master_a:
        raise HTTPException(status_code=404, detail=f"Fund A {fund_a} not found")
    if not master_b:
        raise HTTPException(status_code=404, detail=f"Fund B {fund_b} not found")
        
    bench_a_code = master_a.benchmark_index_code
    bench_b_code = master_b.benchmark_index_code
    
    # 2. Fetch Histories
    # We can run these in parallel
    tasks = [
        crud.get_fund_nav_history(session, fund_a, 500),
        crud.get_fund_nav_history(session, fund_b, 500),
    ]
    
    async def empty_list(): return []
    
    if bench_a_code:
        tasks.append(crud.get_benchmark_nav_history(session, bench_a_code, 500))
    else:
        tasks.append(empty_list())
        
    if bench_b_code:
        if bench_b_code == bench_a_code:
            pass # We'll just copy the result of Bench A
        else:
            tasks.append(crud.get_benchmark_nav_history(session, bench_b_code, 500))
    else:
        tasks.append(empty_list())

    res_list = list(await asyncio.gather(*tasks))
    
    hist_a = res_list[0] if len(res_list) > 0 else []
    hist_b = res_list[1] if len(res_list) > 1 else []
    bench_hist_a = res_list[2] if len(res_list) > 2 else []
    
    if len(res_list) > 3:
        bench_hist_b = res_list[3]
    else:
        bench_hist_b = bench_hist_a if bench_a_code == bench_b_code else []
        
    def serialize_history(history_list, is_benchmark=False):
        return [
            {
                "nav_date": h.nav_date.isoformat(),
                "nav_value": h.index_value if is_benchmark else h.nav_value
            } for h in history_list
        ]
        
    metrics_a = schemas.FundMetricsRead.model_validate(master_a.metrics).model_dump(mode="json") if getattr(master_a, "metrics", None) else {}
    metrics_b = schemas.FundMetricsRead.model_validate(master_b.metrics).model_dump(mode="json") if getattr(master_b, "metrics", None) else {}
        
    payload = {
        "fund_a": {
            "detail": schemas.FundMasterRead.model_validate(master_a).model_dump(mode="json"),
            "history": serialize_history(hist_a, False),
            "benchHistory": serialize_history(bench_hist_a, True),
            "metrics": metrics_a
        },
        "fund_b": {
            "detail": schemas.FundMasterRead.model_validate(master_b).model_dump(mode="json"),
            "history": serialize_history(hist_b, False),
            "benchHistory": serialize_history(bench_hist_b, True),
            "metrics": metrics_b
        }
    }
    
    return payload

@router.get("/{scheme_code}", response_model=schemas.FundMasterRead)
async def read_fund(scheme_code: str, session: AsyncSession = Depends(get_db)):
    fund = await crud.get_fund_master_by_code(session, scheme_code)
    if not fund:
        raise HTTPException(status_code=404, detail=f"Fund with scheme_code {scheme_code} not found")
    return fund

@router.put("/{scheme_code}", response_model=schemas.FundMasterRead)
async def update_fund(
    scheme_code: str,
    fund_in: schemas.FundMasterUpdate,
    session: AsyncSession = Depends(get_db)
):
    result = await crud.update_fund_master(session, scheme_code, fund_in)
    if not result:
        raise HTTPException(status_code=404, detail="Fund not found")
    return result

@router.delete("/{scheme_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fund(scheme_code: str, session: AsyncSession = Depends(get_db)):
    result = await crud.delete_fund_master(session, scheme_code)
    if not result:
        raise HTTPException(status_code=404, detail="Fund not found")
    return None
