from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from .. import crud, schemas, security

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.post("/", response_model=schemas.BenchmarkMasterRead, status_code=status.HTTP_201_CREATED)
async def create_benchmark(
    benchmark: schemas.BenchmarkMasterCreate,
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    existing = await crud.get_benchmark_master(session, benchmark.benchmark_code)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Benchmark with code {benchmark.benchmark_code} already exists",
        )
    return await crud.create_benchmark_master(session, benchmark)

@router.get("/", response_model=schemas.BenchmarkPaginated)
async def list_benchmarks(
    q: Optional[str] = Query(None, description="Search by name or code"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    items, total = await crud.get_all_benchmark_masters(session, is_active=is_active, skip=skip, limit=limit, search=q)
    return {"items": items, "total": total}

@router.get("/{benchmark_code}", response_model=schemas.BenchmarkMasterRead)
async def read_benchmark(
    benchmark_code: str,
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    benchmark = await crud.get_benchmark_master(session, benchmark_code)
    if not benchmark:
        raise HTTPException(status_code=404, detail=f"Benchmark with code {benchmark_code} not found")
    return benchmark

@router.put("/{benchmark_code}", response_model=schemas.BenchmarkMasterRead)
async def update_benchmark(
    benchmark_code: str,
    benchmark_in: schemas.BenchmarkMasterUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    result = await crud.update_benchmark_master(session, benchmark_code, benchmark_in)
    if not result:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return result


@router.delete("/{benchmark_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_benchmark(
    benchmark_code: str,
    session: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.get_current_user),
):
    result = await crud.delete_benchmark_master(session, benchmark_code)
    if not result:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return None
