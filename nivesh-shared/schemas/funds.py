from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import Optional, List, Dict


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

class BulkNavUpload(BaseModel):
    data: dict  # Format: {"YYYY-MM-DD": value, ...}


# ============================================================================
# FUND METRICS SCHEMAS
# ============================================================================

class FundMetricsFields(BaseModel):
    aum_in_crores: Optional[float] = None
    expense_ratio: Optional[float] = None
    fund_rating: Optional[float] = None
    volatility: Optional[float] = None
    cagr_3year: Optional[float] = None
    cagr_5year: Optional[float] = None
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
    final_verdict: Optional[str] = None

class FundMetricsBase(FundMetricsFields):
    scheme_code: str
    current_nav: float
    nav_date: date

class FundMetricsRead(FundMetricsBase):
    metrics_calculated_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class FundMetricsReadWithoutNav(FundMetricsFields):
    scheme_code: str
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
    manager_experience: Optional[str] = None
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
    manager_experience: Optional[str] = None
    is_active: Optional[bool] = None


# ============================================================================
# FUND COMPARISON SCHEMAS
# ============================================================================

class FundRanking(BaseModel):
    scheme_code: str
    rank: int
    composite_score: float
    group_scores: Dict[str, float]
    wins: List[str] = []
    is_recommended: bool = False
    recommendation_reason: Optional[str] = None

class RankingResult(BaseModel):
    rankings: List[FundRanking]
    comparison_summary: str

class FundComparisonItem(BaseModel):
    scheme_code: str
    fund_info: Optional[FundMasterRead] = None
    metrics: Optional[FundMetricsRead] = None

class ComparisonResponse(BaseModel):
    funds: List[FundComparisonItem]
    ranking: Optional[RankingResult] = None
    warning: Optional[str] = None
