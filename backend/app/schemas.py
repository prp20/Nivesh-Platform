from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import Optional, List, Dict, Any

# ============================================================================
# NAV HISTORY SCHEMAS
# ============================================================================

class FundNavHistoryCreate(BaseModel):
    scheme_code: str
    nav_date: date
    nav_value: float

class FundNavHistoryRead(FundNavHistoryCreate):
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class BenchmarkNavHistoryCreate(BaseModel):
    benchmark_code: str
    nav_date: date
    index_value: float

class BenchmarkNavHistoryRead(BenchmarkNavHistoryCreate):
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class BulkNavUpload(BaseModel):
    data: dict  # Format: {"YYYY-MM-DD": value, ...}

# ============================================================================
# FUND METRICS SCHEMAS
# ============================================================================

class FundMetricsBase(BaseModel):
    scheme_code: str
    current_nav: float
    nav_date: date
    aum_in_crores: Optional[float] = None
    rolling_return_3year: Optional[float] = None
    rolling_return_5year: Optional[float] = None
    absolute_return_1y: Optional[float] = None
    absolute_return_3y: Optional[float] = None
    absolute_return_5y: Optional[float] = None
    absolute_return_10y: Optional[float] = None
    short_term_return_6m: Optional[float] = None
    upside_capture: Optional[float] = None
    downside_capture: Optional[float] = None
    sortino_ratio: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    standard_deviation: Optional[float] = None
    maximum_drawdown: Optional[float] = None
    tracking_error: Optional[float] = None
    information_ratio: Optional[float] = None
    calculation_period_start_date: Optional[date] = None
    calculation_period_end_date: Optional[date] = None
    has_sufficient_data: bool = True
    data_completeness_percentage: Optional[float] = None

class FundMetricsRead(FundMetricsBase):
    metrics_calculated_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class FundMetricsReadWithoutNav(BaseModel):
    scheme_code: str
    aum_in_crores: Optional[float] = None
    rolling_return_3year: Optional[float] = None
    rolling_return_5year: Optional[float] = None
    absolute_return_1y: Optional[float] = None
    absolute_return_3y: Optional[float] = None
    absolute_return_5y: Optional[float] = None
    absolute_return_10y: Optional[float] = None
    short_term_return_6m: Optional[float] = None
    upside_capture: Optional[float] = None
    downside_capture: Optional[float] = None
    sortino_ratio: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    standard_deviation: Optional[float] = None
    maximum_drawdown: Optional[float] = None
    tracking_error: Optional[float] = None
    information_ratio: Optional[float] = None
    calculation_period_start_date: Optional[date] = None
    calculation_period_end_date: Optional[date] = None
    has_sufficient_data: bool = True
    data_completeness_percentage: Optional[float] = None
    metrics_calculated_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class FundMetricsResponse(BaseModel):
    metrics: Optional[FundMetricsReadWithoutNav] = None
    sync_job_id: Optional[str] = None
    sync_status: Optional[str] = None
    sync_message: Optional[str] = None

# ============================================================================
# FUND MASTER SCHEMAS
# ============================================================================

class FundMasterBase(BaseModel):
    scheme_code: str
    scheme_name: str
    amc_name: str
    inception_date: date
    plan_type: str
    scheme_category: str
    scheme_subcategory: Optional[str] = None
    benchmark_index_code: Optional[str] = None
    isin: Optional[str] = None
    is_active: bool = True

class FundMasterCreate(FundMasterBase):
    pass

class FundMasterRead(FundMasterBase):
    created_at: datetime
    updated_at: datetime
    metrics: Optional[FundMetricsRead] = None
    model_config = ConfigDict(from_attributes=True)

class FundMasterListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[FundMasterRead]

class FundMasterUpdate(BaseModel):
    scheme_name: Optional[str] = None
    amc_name: Optional[str] = None
    inception_date: Optional[date] = None
    plan_type: Optional[str] = None
    scheme_category: Optional[str] = None
    scheme_subcategory: Optional[str] = None
    benchmark_index_code: Optional[str] = None
    isin: Optional[str] = None
    is_active: Optional[bool] = None

# ============================================================================
# BENCHMARK MASTER SCHEMAS
# ============================================================================

class BenchmarkMasterBase(BaseModel):
    benchmark_code: str
    benchmark_name: str
    ticker: str
    benchmark_type: Optional[str] = None
    asset_class: Optional[str] = None
    is_active: bool = True

class BenchmarkMasterCreate(BenchmarkMasterBase):
    pass

class BenchmarkMetricsBase(BaseModel):
    benchmark_code: str
    current_nav: float
    nav_date: date
    rolling_return_3year: Optional[float] = None
    rolling_return_5year: Optional[float] = None
    sortino_ratio: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    standard_deviation: Optional[float] = None
    maximum_drawdown: Optional[float] = None

class BenchmarkMetricsRead(BenchmarkMetricsBase):
    metrics_calculated_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class BenchmarkMasterRead(BenchmarkMasterBase):
    created_at: datetime
    updated_at: datetime
    metrics: Optional[BenchmarkMetricsRead] = None
    model_config = ConfigDict(from_attributes=True)

class BenchmarkMasterUpdate(BaseModel):
    benchmark_name: Optional[str] = None
    benchmark_type: Optional[str] = None
    ticker: Optional[str] = None
    asset_class: Optional[str] = None
    is_active: Optional[bool] = None

class BenchmarkPaginated(BaseModel):
    items: List[BenchmarkMasterRead]
    total: int

# ============================================================================
# SYNC JOB SCHEMAS
# ============================================================================

class SyncJobBase(BaseModel):
    scheme_code: str
    status: str
    message: Optional[str] = None

class SyncJobRead(SyncJobBase):
    id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ============================================================================
# EXPENSE RATIO SCHEMAS
# ============================================================================

class FundExpenseRatioBase(BaseModel):
    scheme_code: str
    expense_ratio: float
    as_of_date: date

class FundExpenseRatioCreate(FundExpenseRatioBase):
    pass

class FundExpenseRatioRead(FundExpenseRatioBase):
    id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ComparisonResponse(BaseModel):
    """Unified response for multi-fund comparison metrics."""
    funds: List[Dict[str, Any]]
    metrics_comparison: Dict[str, Any]
