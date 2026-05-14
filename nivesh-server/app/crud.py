"""
CRUD operations for mutual fund and stock market data.

Provides database access layer with async SQLAlchemy queries.
All functions use proper type hints and docstrings following Google style.
"""

from sqlalchemy import select, insert, update, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import Select
from typing import Optional, List, Tuple
from datetime import datetime, timezone
import uuid

from .models import (
    FundMaster, BenchmarkMaster, FundNavHistory, BenchmarkNavHistory,
    FundMetrics, BenchmarkMetrics, EtlRun, AdminUser,
    Stock, PriceData, TechnicalIndicator, FinancialStatement,
    FinancialRatio, ShareholdingPattern, StockRating, FundamentalScore,
)
from .schemas import (
    FundMasterCreate, FundMasterUpdate,
    BenchmarkMasterCreate, BenchmarkMasterUpdate,
    FundNavHistoryCreate, BenchmarkNavHistoryCreate
)

# ============================================================================
# FUND MASTER CRUD
# ============================================================================


async def create_fund_master(
    session: AsyncSession, fund_in: FundMasterCreate
) -> FundMaster:
    """
    Create a new fund master record.

    Args:
        session: AsyncSession for database access
        fund_in: Fund creation data

    Returns:
        Created FundMaster with loaded relationships

    Raises:
        IntegrityError: If fund scheme_code or ISIN already exists
    """
    stmt = insert(FundMaster).values(**fund_in.model_dump()).returning(FundMaster)
    res = await session.execute(stmt)
    fund = res.scalar_one()
    await session.commit()
    return await get_fund_master_by_code(session, fund.scheme_code)


async def get_fund_master_by_code(
    session: AsyncSession, scheme_code: str
) -> Optional[FundMaster]:
    """
    Retrieve a fund by scheme code with eager-loaded metrics.

    Args:
        session: AsyncSession for database access
        scheme_code: Fund scheme code (primary key)

    Returns:
        FundMaster object if found, None otherwise
    """
    q = select(FundMaster).options(joinedload(FundMaster.metrics)).where(FundMaster.scheme_code == scheme_code)
    res = await session.execute(q)
    return res.unique().scalar_one_or_none()


async def get_fund_masters_by_codes(
    session: AsyncSession, scheme_codes: List[str]
) -> List[FundMaster]:
    """
    Retrieve multiple funds by their scheme codes in a single batch.

    Args:
        session: AsyncSession for database access
        scheme_codes: List of fund scheme codes

    Returns:
        List of FundMaster objects found, with metrics eager-loaded
    """
    if not scheme_codes:
        return []
    q = (
        select(FundMaster)
        .options(joinedload(FundMaster.metrics))
        .where(FundMaster.scheme_code.in_(scheme_codes))
    )
    res = await session.execute(q)
    return res.unique().scalars().all()


async def get_similar_funds(
    session: AsyncSession, scheme_code: str, limit: int = 4
) -> List[FundMaster]:
    """
    Find similar funds in the same category and subcategory.

    Args:
        session: AsyncSession for database access
        scheme_code: Scheme code to find similar funds for
        limit: Maximum number of results (default: 4)

    Returns:
        List of similar active FundMaster objects, ordered by name
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
            FundMaster.is_active == True,
        )
        .limit(limit)
    )

    res = await session.execute(q)
    return res.unique().scalars().all()


def _apply_fund_filters(
    q: Select[tuple[FundMaster]],
    is_active: Optional[bool] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    amc: Optional[str] = None,
    plan_type: Optional[str] = None,
    benchmark_code: Optional[str] = None,
    search: Optional[str] = None,
) -> Select[tuple[FundMaster]]:
    """
    Apply common FundMaster filter predicates to a query.

    Args:
        q: SQLAlchemy Select query to filter
        is_active: Filter by active status
        category: Filter by scheme category (substring match)
        subcategory: Filter by scheme subcategory (substring match)
        amc: Filter by AMC name (substring match)
        plan_type: Filter by plan type (Direct/Regular)
        benchmark_code: Filter by benchmark index code (substring match)
        search: Search in scheme_name and scheme_code (substring match)

    Returns:
        Modified Select query with applied filters
    """
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
    if search:
        q = q.where(
            (FundMaster.scheme_name.ilike(f"%{search}%")) |
            (FundMaster.scheme_code.ilike(f"%{search}%"))
        )
    return q


async def get_all_fund_masters(
    session: AsyncSession,
    is_active: Optional[bool] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    amc: Optional[str] = None,
    plan_type: Optional[str] = None,
    benchmark_code: Optional[str] = None,
    search: Optional[str] = None,
    order_by: Optional[str] = "scheme_name",
    skip: int = 0,
    limit: int = 100,
) -> List[FundMaster]:
    """
    Retrieve paginated list of funds with optional filters.

    Args:
        session: AsyncSession for database access
        is_active: Filter by active status
        category: Filter by scheme category (substring match)
        subcategory: Filter by scheme subcategory (substring match)
        amc: Filter by AMC name (substring match)
        plan_type: Filter by plan type (Direct/Regular)
        benchmark_code: Filter by benchmark index code (substring match)
        search: Search in scheme_name and scheme_code (substring match)
        order_by: Order by column ("scheme_name" or "-scheme_name" for DESC)
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return

    Returns:
        List of FundMaster objects matching filters, with metrics eager-loaded
    """
    query = select(FundMaster)
    q = _apply_fund_filters(
        q=query,
        is_active=is_active,
        category=category,
        subcategory=subcategory,
        amc=amc,
        plan_type=plan_type,
        benchmark_code=benchmark_code,
        search=search,
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
    search: Optional[str] = None,
) -> int:
    query = select(func.count(FundMaster.scheme_code))
    q = _apply_fund_filters(
        q=query,
        is_active=is_active,
        category=category,
        subcategory=subcategory,
        amc=amc,
        plan_type=plan_type,
        benchmark_code=benchmark_code,
        search=search,
    )
    res = await session.execute(q)
    return res.scalar() or 0

async def get_distinct_categories(session: AsyncSession) -> List[str]:
    """Return sorted distinct scheme_category values from active funds."""
    q = (
        select(FundMaster.scheme_category)
        .where(FundMaster.is_active == True)
        .distinct()
    )
    res = await session.execute(q)
    return sorted([row[0] for row in res.all()])


async def get_distinct_subcategories(session: AsyncSession, category: str) -> List[str]:
    """Return sorted distinct scheme_subcategory values for a given category."""
    q = (
        select(FundMaster.scheme_subcategory)
        .where(FundMaster.is_active == True, FundMaster.scheme_category == category)
        .where(FundMaster.scheme_subcategory.isnot(None))
        .distinct()
    )
    res = await session.execute(q)
    return sorted([row[0] for row in res.all() if row[0]])


async def get_distinct_amcs(session: AsyncSession) -> List[str]:
    """Return sorted distinct amc_name values from active funds."""
    q = (
        select(FundMaster.amc_name)
        .where(FundMaster.is_active == True)
        .distinct()
    )
    res = await session.execute(q)
    return sorted([row[0] for row in res.all() if row[0]])


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

async def get_fund_nav_history(
    session: AsyncSession,
    scheme_code: str,
    limit: int = 100,
    from_date=None,
):
    q = (
        select(FundNavHistory)
        .where(FundNavHistory.scheme_code == scheme_code)
        .order_by(FundNavHistory.nav_date.desc())
        .limit(limit)
    )
    if from_date is not None:
        q = q.where(FundNavHistory.nav_date >= from_date)
    res = await session.execute(q)
    return res.scalars().all()

async def get_benchmark_nav_history(session: AsyncSession, benchmark_code: str, limit: int = 100):
    q = select(BenchmarkNavHistory).where(BenchmarkNavHistory.benchmark_code == benchmark_code).order_by(BenchmarkNavHistory.nav_date.desc()).limit(limit)
    res = await session.execute(q)
    return res.scalars().all()

async def get_benchmarks_latest_prices(session: AsyncSession, benchmark_codes: List[str]):
    """Fetch latest 2 prices for each benchmark to calculate change."""
    if not benchmark_codes:
        return {}
    
    # Using window function to get latest 2 rows per benchmark
    subq = (
        select(
            BenchmarkNavHistory,
            func.row_number().over(
                partition_by=BenchmarkNavHistory.benchmark_code,
                order_by=BenchmarkNavHistory.nav_date.desc()
            ).label("rn")
        )
        .where(BenchmarkNavHistory.benchmark_code.in_(benchmark_codes))
    ).subquery()
    
    q = select(subq).where(subq.c.rn <= 2)
    res = await session.execute(q)
    rows = res.all()
    
    # Process into dict: {code: {latest: X, prev: Y}}
    prices = {}
    for r in rows:
        code = r.benchmark_code
        if code not in prices:
            prices[code] = []
        prices[code].append(float(r.index_value))
    
    result = {}
    for code, history in prices.items():
        latest = history[0]
        prev = history[1] if len(history) > 1 else latest
        change_pct = ((latest - prev) / prev * 100) if prev else 0.0
        result[code] = {
            "latest_close": latest,
            "change_percent": round(change_pct, 2)
        }
    return result

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
# ETL RUN CRUD  (replaces SyncJob + PipelineAudit)
# ============================================================================

async def start_etl_run(
    session: AsyncSession,
    pipeline_name: str,
    entity_id: Optional[str] = None,
    triggered_by: str = "manual",
) -> Tuple["EtlRun", bool]:
    """
    Create a new RUNNING etl_run row.

    Returns (run, True) if a new row was created.
    Returns (existing_run, False) if a RUNNING row already exists
    for this pipeline_name + entity_id (partial unique index prevents duplicates).
    """
    run = EtlRun(
        pipeline_name=pipeline_name,
        entity_id=entity_id,
        status="RUNNING",
        triggered_by=triggered_by,
    )
    try:
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run, True
    except IntegrityError:
        await session.rollback()
        existing = await get_latest_etl_run(session, pipeline_name, entity_id)
        return existing, False


async def finish_etl_run(
    session: AsyncSession,
    run_id: int,
    status: str,
    records_in: int = 0,
    records_out: int = 0,
    error_msg: Optional[str] = None,
) -> Optional["EtlRun"]:
    """
    Mark an etl_run as finished. Sets ended_at to NOW().
    status should be: 'COMPLETED' | 'FAILED' | 'PARTIAL'
    """
    values: dict = {
        "status": status,
        "ended_at": datetime.now(timezone.utc),
        "records_in": records_in,
        "records_out": records_out,
    }
    if error_msg is not None:
        values["error_msg"] = error_msg

    stmt = (
        update(EtlRun)
        .where(EtlRun.id == run_id)
        .values(**values)
        .returning(EtlRun)
    )
    res = await session.execute(stmt)
    await session.commit()
    return res.scalar_one_or_none()


async def get_latest_etl_run(
    session: AsyncSession,
    pipeline_name: str,
    entity_id: Optional[str] = None,
) -> Optional["EtlRun"]:
    """Fetch the most recent etl_run for a pipeline + entity combination."""
    q = (
        select(EtlRun)
        .where(EtlRun.pipeline_name == pipeline_name)
        .order_by(EtlRun.started_at.desc())
        .limit(1)
    )
    if entity_id is not None:
        q = q.where(EtlRun.entity_id == entity_id)
    res = await session.execute(q)
    return res.scalar_one_or_none()


async def get_etl_run_summary(
    session: AsyncSession,
    pipeline_name: Optional[str] = None,
    limit: int = 50,
) -> List["EtlRun"]:
    """Return recent etl_run rows, optionally filtered by pipeline_name."""
    q = select(EtlRun).order_by(EtlRun.started_at.desc()).limit(limit)
    if pipeline_name:
        q = q.where(EtlRun.pipeline_name == pipeline_name)
    res = await session.execute(q)
    return list(res.scalars().all())


# ============================================================================
# ADMIN USER CRUD
# ============================================================================

async def get_user_by_username(
    session: AsyncSession, username: str
) -> Optional["AdminUser"]:
    """Used by the auth login endpoint to look up a user."""
    result = await session.execute(
        select(AdminUser).where(
            AdminUser.username == username,
            AdminUser.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


# ============================================================================
# STOCK PIPELINE CRUD
# ============================================================================


async def get_active_stocks(
    session: AsyncSession, is_index: bool = False
) -> list:
    """Return all active stocks, optionally filtered by is_index flag."""
    result = await session.execute(
        select(Stock)
        .where(Stock.is_active.is_(True), Stock.is_index.is_(is_index))
        .order_by(Stock.symbol)
    )
    return list(result.scalars().all())


async def upsert_price_data(session: AsyncSession, rows: list) -> int:
    """
    Bulk upsert OHLCV rows into price_data.

    ON CONFLICT (stock_id, price_date) → update all OHLCV fields.
    Returns the number of rows processed.
    """
    if not rows:
        return 0
    stmt = pg_insert(PriceData).values(rows)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_id", "price_date"],
        set_={
            "open":      excluded.open,
            "high":      excluded.high,
            "low":       excluded.low,
            "close":     excluded.close,
            "adj_close": excluded.adj_close,
            "volume":    excluded.volume,
        },
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)


async def get_price_data_for_ta(
    session: AsyncSession, stock_id: int, lookback_days: int = 260
) -> list:
    """
    Fetch the most recent N days of price_data for a single stock.

    Returns PriceData ORM objects ordered ascending by price_date so
    TA-Lib arrays are in the correct chronological order.
    """
    from sqlalchemy import desc
    result = await session.execute(
        select(PriceData)
        .where(PriceData.stock_id == stock_id)
        .order_by(desc(PriceData.price_date))
        .limit(lookback_days)
    )
    rows = list(result.scalars().all())
    rows.reverse()  # oldest → newest for TA-Lib
    return rows


async def upsert_technical_indicators(session: AsyncSession, rows: list) -> int:
    """
    Bulk upsert technical indicator rows.

    ON CONFLICT (stock_id, ind_date, timeframe) → update all indicator columns.
    Returns the number of rows processed.
    """
    if not rows:
        return 0
    stmt = pg_insert(TechnicalIndicator).values(rows)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_id", "ind_date", "timeframe"],
        set_={
            "sma_20": excluded.sma_20,
            "sma_50": excluded.sma_50,
            "sma_200": excluded.sma_200,
            "ema_9": excluded.ema_9,
            "ema_21": excluded.ema_21,
            "ema_50": excluded.ema_50,
            "rsi_14": excluded.rsi_14,
            "macd_line": excluded.macd_line,
            "macd_signal": excluded.macd_signal,
            "macd_hist": excluded.macd_hist,
            "bb_upper": excluded.bb_upper,
            "bb_middle": excluded.bb_middle,
            "bb_lower": excluded.bb_lower,
            "atr_14": excluded.atr_14,
            "adx_14": excluded.adx_14,
            "stoch_k": excluded.stoch_k,
            "stoch_d": excluded.stoch_d,
            "volume_sma_20": excluded.volume_sma_20,
            "volume_sma_50": excluded.volume_sma_50,
            "volume_ratio": excluded.volume_ratio,
            "obv": excluded.obv,
            "vwap_20": excluded.vwap_20,
            "cci_20": excluded.cci_20,
            "williams_r": excluded.williams_r,
            "roc_14": excluded.roc_14,
            "beta_1y": excluded.beta_1y,
            "rs_6m_vs_nifty": excluded.rs_6m_vs_nifty,
            "pct_from_52w_high": excluded.pct_from_52w_high,
            "pct_from_52w_low": excluded.pct_from_52w_low,
        },
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)


async def upsert_financial_statement(session: AsyncSession, row: dict) -> bool:
    """
    Upsert a single financial statement row with checksum-based deduplication.

    Skips the upsert if raw_checksum matches the stored value.
    Returns True if the row was inserted/updated, False if skipped (unchanged).
    """
    existing = await session.execute(
        select(FinancialStatement.raw_checksum).where(
            FinancialStatement.stock_id == row["stock_id"],
            FinancialStatement.statement_type == row["statement_type"],
            FinancialStatement.period_type == row["period_type"],
            FinancialStatement.period_end == row["period_end"],
        )
    )
    stored_checksum = existing.scalar_one_or_none()
    if stored_checksum is not None and stored_checksum == row.get("raw_checksum"):
        return False  # unchanged — skip

    stmt = pg_insert(FinancialStatement).values(row)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_id", "statement_type", "period_type", "period_end"],
        set_={
            "data":         excluded.data,
            "raw_data":     excluded.raw_data,
            "raw_checksum": excluded.raw_checksum,
            "scraped_at":   excluded.scraped_at,
        },
    )
    await session.execute(stmt)
    await session.commit()
    return True


async def upsert_financial_ratios(session: AsyncSession, row: dict) -> int:
    """
    Upsert a single financial ratios row.

    ON CONFLICT (stock_id, period_end, period_type) → update all ratio columns.
    Returns 1 on success.
    """
    stmt = pg_insert(FinancialRatio).values(row)
    conflict_keys = {"id", "stock_id", "period_end", "period_type"}
    set_ = {k: v for k, v in row.items() if k not in conflict_keys}
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_id", "period_end", "period_type"],
        set_=set_,
    )
    await session.execute(stmt)
    await session.commit()
    return 1


async def upsert_shareholding(session: AsyncSession, row: dict) -> int:
    """
    Upsert a single shareholding pattern row.

    ON CONFLICT (stock_id, period_end) → update all shareholding columns.
    Returns 1 on success.
    """
    stmt = pg_insert(ShareholdingPattern).values(row)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_id", "period_end"],
        set_={
            "promoter_pct":    excluded.promoter_pct,
            "fii_pct":         excluded.fii_pct,
            "dii_pct":         excluded.dii_pct,
            "public_pct":      excluded.public_pct,
            "pledged_pct":     excluded.pledged_pct,
            "promoter_change": excluded.promoter_change,
            "fii_change":      excluded.fii_change,
            "scraped_at":      excluded.scraped_at,
        },
    )
    await session.execute(stmt)
    await session.commit()
    return 1


async def upsert_stock_rating(session: AsyncSession, row: dict) -> int:
    """
    Upsert a single stock rating row.

    ON CONFLICT (stock_id, rated_on) → update all score columns.
    Returns 1 on success.
    """
    stmt = pg_insert(StockRating).values(row)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_id", "rated_on"],
        set_={
            "total_score":        excluded.total_score,
            "rating_label":       excluded.rating_label,
            "fundamental_score":  excluded.fundamental_score,
            "valuation_score":    excluded.valuation_score,
            "technical_score":    excluded.technical_score,
            "momentum_score":     excluded.momentum_score,
            "quality_score":      excluded.quality_score,
            "shareholding_score": excluded.shareholding_score,
            "score_breakdown":    excluded.score_breakdown,
        },
    )
    await session.execute(stmt)
    await session.commit()
    return 1


async def upsert_fundamental_score(session: AsyncSession, row: dict) -> int:
    """
    Upsert a single fundamental score row (LangGraph AI scoring output).

    ON CONFLICT (stock_id, period_end, score_version) → update all score columns.
    Returns 1 on success.
    """
    stmt = pg_insert(FundamentalScore).values(row)
    conflict_keys = {"id", "stock_id", "period_end", "score_version"}
    set_ = {k: v for k, v in row.items() if k not in conflict_keys}
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_id", "period_end", "score_version"],
        set_=set_,
    )
    await session.execute(stmt)
    await session.commit()
    return 1
