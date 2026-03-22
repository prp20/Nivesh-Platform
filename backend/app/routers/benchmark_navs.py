from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import crud, schemas

router = APIRouter(prefix="/benchmark-navs", tags=["benchmark-navs"])

@router.post("/{benchmark_code}/bulk", status_code=201)
async def upload_bulk_benchmark_nav(benchmark_code: str, payload: schemas.BulkNavUpload, session: AsyncSession = Depends(get_db)):
    count = await crud.bulk_insert_benchmark_navs(session, benchmark_code, payload.data)
    return {"message": f"Successfully processed {count} benchmark records"}

@router.get("/{benchmark_code}", response_model=List[schemas.BenchmarkNavHistoryRead])
async def get_benchmark_nav_history(benchmark_code: str, limit: int = 100, session: AsyncSession = Depends(get_db)):
    # Fallback to general history getter if I implement it
    return []
