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
