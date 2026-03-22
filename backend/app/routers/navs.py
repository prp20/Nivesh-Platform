from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import crud, schemas

router = APIRouter(prefix="/navs", tags=["navs"])

@router.post("/{scheme_code}/bulk", status_code=201)
async def upload_bulk_nav(scheme_code: str, payload: schemas.BulkNavUpload, session: AsyncSession = Depends(get_db)):
    count = await crud.bulk_insert_fund_navs(session, scheme_code, payload.data)
    return {"message": f"Successfully processed {count} NAV records"}

@router.get("/{scheme_code}", response_model=List[schemas.FundNavHistoryRead])
async def get_nav_history(scheme_code: str, limit: int = 100, session: AsyncSession = Depends(get_db)):
    return await crud.get_fund_nav_history(session, scheme_code, limit)
