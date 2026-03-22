from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from .models import FundMaster, BenchmarkMaster, FundNavHistory, BenchmarkNavHistory, FundMetrics
from .schemas import (
    FundMasterCreate, FundMasterUpdate,
    BenchmarkMasterCreate, BenchmarkMasterUpdate,
    FundNavHistoryCreate, BenchmarkNavHistoryCreate
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import datetime
from sqlalchemy.orm import joinedload

# ============================================================================
# FUND MASTER CRUD
# ============================================================================

async def create_fund_master(session: AsyncSession, fund_in: FundMasterCreate):
    stmt = insert(FundMaster).values(**fund_in.model_dump()).returning(FundMaster)
    res = await session.execute(stmt)
    await session.commit()
    return res.scalar_one()

async def get_fund_master_by_code(session: AsyncSession, scheme_code: str):
    q = select(FundMaster).options(joinedload(FundMaster.metrics)).where(FundMaster.scheme_code == scheme_code)
    res = await session.execute(q)
    return res.scalar_one_or_none()

async def get_all_fund_masters(
    session: AsyncSession, 
    is_active: Optional[bool] = None, 
    category: Optional[str] = None,
    amc: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100
):
    q = select(FundMaster).options(joinedload(FundMaster.metrics)).offset(skip).limit(limit)
    if is_active is not None:
        q = q.where(FundMaster.is_active == is_active)
    if category and category != 'All':
        q = q.where(FundMaster.scheme_category.ilike(f"%{category}%"))
    if amc:
        q = q.where(FundMaster.amc_name.ilike(f"%{amc}%"))
        
    res = await session.execute(q)
    return res.scalars().all()

async def get_fund_masters_count(
    session: AsyncSession,
    is_active: Optional[bool] = None,
    category: Optional[str] = None,
    amc: Optional[str] = None
):
    from sqlalchemy import func
    q = select(func.count(FundMaster.scheme_code))
    if is_active is not None:
        q = q.where(FundMaster.is_active == is_active)
    if category and category != 'All':
        q = q.where(FundMaster.scheme_category.ilike(f"%{category}%"))
    if amc:
        q = q.where(FundMaster.amc_name.ilike(f"%{amc}%"))
        
    res = await session.execute(q)
    return res.scalar()

async def update_fund_master(session: AsyncSession, scheme_code: str, fund_in: FundMasterUpdate):
    data = fund_in.model_dump(exclude_unset=True)
    if not data:
        return await get_fund_master_by_code(session, scheme_code)
    stmt = (
        update(FundMaster)
        .where(FundMaster.scheme_code == scheme_code)
        .values(**data)
        .returning(FundMaster)
    )
    res = await session.execute(stmt)
    await session.commit()
    return res.scalar_one_or_none()

async def delete_fund_master(session: AsyncSession, scheme_code: str):
    stmt = delete(FundMaster).where(FundMaster.scheme_code == scheme_code).returning(FundMaster)
    res = await session.execute(stmt)
    await session.commit()
    return res.scalar_one_or_none()

# ============================================================================
# BENCHMARK MASTER CRUD
# ============================================================================

async def create_benchmark_master(session: AsyncSession, benchmark_in: BenchmarkMasterCreate):
    stmt = insert(BenchmarkMaster).values(**benchmark_in.model_dump()).returning(BenchmarkMaster)
    res = await session.execute(stmt)
    await session.commit()
    return res.scalar_one()

async def get_benchmark_master(session: AsyncSession, benchmark_code: str):
    q = select(BenchmarkMaster).where(BenchmarkMaster.benchmark_code == benchmark_code)
    res = await session.execute(q)
    return res.scalar_one_or_none()

async def get_all_benchmark_masters(session: AsyncSession, is_active: Optional[bool] = None, skip: int = 0, limit: int = 100):
    q = select(BenchmarkMaster).offset(skip).limit(limit)
    if is_active is not None:
        q = q.where(BenchmarkMaster.is_active == is_active)
    res = await session.execute(q)
    return res.scalars().all()

async def update_benchmark_master(session: AsyncSession, benchmark_code: str, benchmark_in: BenchmarkMasterUpdate):
    data = benchmark_in.model_dump(exclude_unset=True)
    if not data:
        return await get_benchmark_master(session, benchmark_code)
    stmt = (
        update(BenchmarkMaster)
        .where(BenchmarkMaster.benchmark_code == benchmark_code)
        .values(**data)
        .returning(BenchmarkMaster)
    )
    res = await session.execute(stmt)
    await session.commit()
    return res.scalar_one_or_none()

async def delete_benchmark_master(session: AsyncSession, benchmark_code: str):
    stmt = delete(BenchmarkMaster).where(BenchmarkMaster.benchmark_code == benchmark_code).returning(BenchmarkMaster)
    res = await session.execute(stmt)
    await session.commit()
    return res.scalar_one_or_none()

# ============================================================================
# TIME-SERIES CRUD (NAV & BENCHMARK)
# ============================================================================

async def bulk_insert_fund_navs(session: AsyncSession, scheme_code: str, nav_data: dict):
    if not nav_data: return 0
    rows = []
    for d, v in nav_data.items():
        rows.append({
            "scheme_code": scheme_code,
            "nav_date": datetime.strptime(d, "%Y-%m-%d").date(),
            "nav_value": float(v)
        })
    stmt = pg_insert(FundNavHistory).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=['scheme_code', 'nav_date'],
        set_=dict(nav_value=stmt.excluded.nav_value)
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)

async def bulk_insert_benchmark_navs(session: AsyncSession, benchmark_code: str, nav_data: dict):
    if not nav_data: return 0
    rows = []
    for d, v in nav_data.items():
        rows.append({
            "benchmark_code": benchmark_code,
            "nav_date": datetime.strptime(d, "%Y-%m-%d").date(),
            "index_value": float(v)
        })
    stmt = pg_insert(BenchmarkNavHistory).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=['benchmark_code', 'nav_date'],
        set_=dict(index_value=stmt.excluded.index_value)
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)

async def get_fund_nav_history(session: AsyncSession, scheme_code: str, limit: int = 100):
    q = select(FundNavHistory).where(FundNavHistory.scheme_code == scheme_code).order_by(FundNavHistory.nav_date.desc()).limit(limit)
    res = await session.execute(q)
    return res.scalars().all()

async def get_benchmark_nav_history(session: AsyncSession, benchmark_code: str, limit: int = 100):
    q = select(BenchmarkNavHistory).where(BenchmarkNavHistory.benchmark_code == benchmark_code).order_by(BenchmarkNavHistory.nav_date.desc()).limit(limit)
    res = await session.execute(q)
    return res.scalars().all()

# ============================================================================
# FUND METRICS CRUD
# ============================================================================

async def upsert_fund_metrics(session: AsyncSession, metrics_data: dict):
    stmt = pg_insert(FundMetrics).values(metrics_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=['scheme_code'],
        set_=metrics_data
    )
    await session.execute(stmt)
    await session.commit()

async def get_fund_metrics(session: AsyncSession, scheme_code: str):
    q = select(FundMetrics).where(FundMetrics.scheme_code == scheme_code)
    res = await session.execute(q)
    return res.scalar_one_or_none()

# ============================================================================
# SYNC JOB CRUD
# ============================================================================

from .models import SyncJob
import uuid

from sqlalchemy.exc import IntegrityError

async def create_sync_job(session: AsyncSession, scheme_code: str):
    job = SyncJob(scheme_code=scheme_code, status="RUNNING", message="Initializing sync...")
    try:
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job, True
    except IntegrityError:
        await session.rollback()
        # Fallback: get the existing running job
        existing_job = await get_latest_sync_job(session, scheme_code)
        return existing_job, False

async def update_sync_job(session: AsyncSession, job_id: str, status: Optional[str] = None, message: Optional[str] = None):
    values = {}
    if status: values['status'] = status
    if message: values['message'] = message
    
    stmt = update(SyncJob).where(SyncJob.id == job_id).values(**values).returning(SyncJob)
    res = await session.execute(stmt)
    await session.commit()
    return res.scalar_one_or_none()

async def get_latest_sync_job(session: AsyncSession, scheme_code: str):
    q = select(SyncJob).where(SyncJob.scheme_code == scheme_code).order_by(SyncJob.created_at.desc()).limit(1)
    res = await session.execute(q)
    return res.scalar_one_or_none()
