from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import crud, schemas

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])

@router.post("/", response_model=schemas.BenchmarkMasterRead, status_code=status.HTTP_201_CREATED)
async def create_benchmark(benchmark: schemas.BenchmarkMasterCreate, session: AsyncSession = Depends(get_db)):
    existing = await crud.get_benchmark_master(session, benchmark.benchmark_code)
    if existing:
        raise HTTPException(status_code=400, detail=f"Benchmark with code {benchmark.benchmark_code} already exists")
    return await crud.create_benchmark_master(session, benchmark)

@router.get("/", response_model=List[schemas.BenchmarkMasterRead])
async def list_benchmarks(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    session: AsyncSession = Depends(get_db)
):
    return await crud.get_all_benchmark_masters(session, is_active=is_active)

@router.get("/{benchmark_code}", response_model=schemas.BenchmarkMasterRead)
async def read_benchmark(benchmark_code: str, session: AsyncSession = Depends(get_db)):
    benchmark = await crud.get_benchmark_master(session, benchmark_code)
    if not benchmark:
        raise HTTPException(status_code=404, detail=f"Benchmark with code {benchmark_code} not found")
    return benchmark

@router.put("/{benchmark_code}", response_model=schemas.BenchmarkMasterRead)
async def update_benchmark(
    benchmark_code: str,
    benchmark_in: schemas.BenchmarkMasterUpdate,
    session: AsyncSession = Depends(get_db)
):
    result = await crud.update_benchmark_master(session, benchmark_code, benchmark_in)
    if not result:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return result

@router.delete("/{benchmark_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_benchmark(benchmark_code: str, session: AsyncSession = Depends(get_db)):
    result = await crud.delete_benchmark_master(session, benchmark_code)
    if not result:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return None
