from sqlalchemy import select, insert, update, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from typing import Optional, List, Tuple
from datetime import datetime
import uuid

from .models import FundMaster, BenchmarkMaster, FundNavHistory, BenchmarkNavHistory, FundMetrics, BenchmarkMetrics, SyncJob
from .schemas import (
    FundMasterCreate, FundMasterUpdate,
    BenchmarkMasterCreate, BenchmarkMasterUpdate,
    FundNavHistoryCreate, BenchmarkNavHistoryCreate
)

# ============================================================================
# FUND MASTER CRUD
# ============================================================================

async def create_fund_master(session: AsyncSession, fund_in: FundMasterCreate):
    stmt = insert(FundMaster).values(**fund_in.model_dump()).returning(FundMaster)
    res = await session.execute(stmt)
    fund = res.scalar_one()
    await session.commit()
    return await get_fund_master_by_code(session, fund.scheme_code)

async def get_fund_master_by_code(session: AsyncSession, scheme_code: str):
    q = select(FundMaster).options(joinedload(FundMaster.metrics)).where(FundMaster.scheme_code == scheme_code)
    res = await session.execute(q)
    return res.unique().scalar_one_or_none()

async def get_similar_funds(session: AsyncSession, scheme_code: str, limit: int = 4):
    """
    Find funds in the same category and subcategory as the given scheme_code.
    """
    fund = await get_fund_master_by_code(session, scheme_code)
    if not fund:
        return []
    
    q = (
        select(FundMaster)
        .options(joinedload(FundMaster.metrics))
        .where(
            FundMaster.scheme_category == fund.scheme_category,
            FundMaster.scheme_subcategory == fund.scheme_subcategory,
            FundMaster.scheme_code != scheme_code,
            FundMaster.is_active == True
        )
        .limit(limit)
    )
    
    res = await session.execute(q)
    return res.unique().scalars().all()

def _apply_fund_filters(
    q,
    is_active: Optional[bool] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    amc: Optional[str] = None,
    plan_type: Optional[str] = None,
    benchmark_code: Optional[str] = None,
):
    """Apply common FundMaster filter predicates to a query."""
    if is_active is not None:
        q = q.where(FundMaster.is_active == is_active)
    if category and category != "All":
        q = q.where(FundMaster.scheme_category.ilike(f"%{category}%"))
    if subcategory:
        q = q.where(FundMaster.scheme_subcategory.ilike(f"%{subcategory}%"))
    if amc:
        q = q.where(FundMaster.amc_name.ilike(f"%{amc}%"))
    if plan_type:
        q = q.where(FundMaster.plan_type == plan_type)
    if benchmark_code:
        q = q.where(FundMaster.benchmark_index_code.ilike(f"%{benchmark_code}%"))
    return q


async def get_all_fund_masters(
    session: AsyncSession,
    is_active: Optional[bool] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    amc: Optional[str] = None,
    plan_type: Optional[str] = None,
    benchmark_code: Optional[str] = None,
    order_by: Optional[str] = "scheme_name",
    skip: int = 0,
    limit: int = 100,
) -> List[FundMaster]:
    q = _apply_fund_filters(
        select(FundMaster), is_active, category, subcategory, amc, plan_type, benchmark_code
    )

    if order_by == "scheme_name":
        q = q.order_by(FundMaster.scheme_name.asc())
    elif order_by == "-scheme_name":
        q = q.order_by(FundMaster.scheme_name.desc())

    q = q.options(joinedload(FundMaster.metrics)).offset(skip).limit(limit)
    res = await session.execute(q)
    return res.unique().scalars().all()


async def get_fund_masters_count(
    session: AsyncSession,
    is_active: Optional[bool] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    amc: Optional[str] = None,
    plan_type: Optional[str] = None,
    benchmark_code: Optional[str] = None,
) -> int:
    q = _apply_fund_filters(
        select(func.count(FundMaster.scheme_code)), is_active, category, subcategory, amc, plan_type, benchmark_code
    )
    res = await session.execute(q)
    return res.scalar() or 0

async def update_fund_master(session: AsyncSession, scheme_code: str, fund_in: FundMasterUpdate):
    data = fund_in.model_dump(exclude_unset=True)
    if not data:
        return await get_fund_master_by_code(session, scheme_code)
    stmt = (
        update(FundMaster)
        .where(FundMaster.scheme_code == scheme_code)
        .values(**data)
    )
    await session.execute(stmt)
    await session.commit()
    return await get_fund_master_by_code(session, scheme_code)

async def delete_fund_master(session: AsyncSession, scheme_code: str):
    fund = await get_fund_master_by_code(session, scheme_code)
    if not fund:
        return None
        
    stmt = delete(FundMaster).where(FundMaster.scheme_code == scheme_code)
    await session.execute(stmt)
    await session.commit()
    return fund

# ============================================================================
# BENCHMARK MASTER CRUD
# ============================================================================

async def create_benchmark_master(session: AsyncSession, benchmark_in: BenchmarkMasterCreate):
    stmt = insert(BenchmarkMaster).values(**benchmark_in.model_dump()).returning(BenchmarkMaster)
    res = await session.execute(stmt)
    benchmark = res.scalar_one()
    await session.commit()
    return await get_benchmark_master(session, benchmark.benchmark_code)

async def get_benchmark_master(session: AsyncSession, benchmark_code: str):
    q = select(BenchmarkMaster).options(joinedload(BenchmarkMaster.metrics)).where(BenchmarkMaster.benchmark_code == benchmark_code)
    res = await session.execute(q)
    return res.unique().scalar_one_or_none()

async def get_all_benchmark_masters(
    session: AsyncSession, 
    is_active: Optional[bool] = None, 
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None
) -> Tuple[List[BenchmarkMaster], int]:
    q = select(BenchmarkMaster)
    if is_active is not None:
        q = q.where(BenchmarkMaster.is_active == is_active)
    if search:
        q = q.where(
            (BenchmarkMaster.benchmark_name.ilike(f"%{search}%")) |
            (BenchmarkMaster.benchmark_code.ilike(f"%{search}%"))
        )
    
    # Total count using a subquery to preserve filters
    count_q = select(func.count()).select_from(q.subquery())
    total_res = await session.execute(count_q)
    total = total_res.scalar() or 0
    
    # Items
    q_items = q.options(joinedload(BenchmarkMaster.metrics)).offset(skip).limit(limit)
    res = await session.execute(q_items)
    return res.unique().scalars().all(), total

async def update_benchmark_master(session: AsyncSession, benchmark_code: str, benchmark_in: BenchmarkMasterUpdate):
    data = benchmark_in.model_dump(exclude_unset=True)
    if not data:
        return await get_benchmark_master(session, benchmark_code)
    stmt = (
        update(BenchmarkMaster)
        .where(BenchmarkMaster.benchmark_code == benchmark_code)
        .values(**data)
    )
    await session.execute(stmt)
    await session.commit()
    return await get_benchmark_master(session, benchmark_code)

async def delete_benchmark_master(session: AsyncSession, benchmark_code: str):
    benchmark = await get_benchmark_master(session, benchmark_code)
    if not benchmark:
        return None
        
    stmt = delete(BenchmarkMaster).where(BenchmarkMaster.benchmark_code == benchmark_code)
    await session.execute(stmt)
    await session.commit()
    return benchmark

# ============================================================================
# TIME-SERIES CRUD (NAV & BENCHMARK)
# ============================================================================

async def bulk_insert_fund_navs(session: AsyncSession, scheme_code: str, nav_data: dict):
    if not nav_data: return 0
    rows = []
    for d, v in nav_data.items():
        try:
            nav_value = float(v)
            if nav_value <= 0:
                continue  # Reject zero/negative NAVs — invalid data
            date_obj = datetime.strptime(d, "%Y-%m-%d").date() if isinstance(d, str) else d
            rows.append({
                "scheme_code": scheme_code,
                "nav_date": date_obj,
                "nav_value": nav_value,
            })
        except (ValueError, TypeError):
            continue

    if not rows:
        return 0

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
        try:
            date_obj = datetime.strptime(d, "%Y-%m-%d").date() if isinstance(d, str) else d
            rows.append({
                "benchmark_code": benchmark_code,
                "nav_date": date_obj,
                "index_value": float(v)
            })
        except (ValueError, TypeError):
            continue

    if not rows: return 0

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
# METRICS CRUD
# ============================================================================

async def upsert_benchmark_metrics(session: AsyncSession, metrics_data: dict):
    # Exclude PK from update set to avoid DB error
    update_data = {k: v for k, v in metrics_data.items() if k != 'benchmark_code'}
    
    stmt = pg_insert(BenchmarkMetrics).values(metrics_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=['benchmark_code'],
        set_=update_data
    )
    await session.execute(stmt)
    await session.commit()

async def upsert_fund_metrics(session: AsyncSession, metrics_data: dict):
    # Exclude PK from update set to avoid DB error
    update_data = {k: v for k, v in metrics_data.items() if k != 'scheme_code'}
    
    stmt = pg_insert(FundMetrics).values(metrics_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=['scheme_code'],
        set_=update_data
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

async def create_sync_job(session: AsyncSession, scheme_code: str) -> Tuple[SyncJob, bool]:
    job = SyncJob(scheme_code=scheme_code, status="RUNNING", message="Initializing sync...")
    try:
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job, True
    except IntegrityError:
        await session.rollback()
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
