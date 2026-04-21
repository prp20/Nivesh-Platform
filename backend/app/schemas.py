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
    cagr_3year: Optional[float] = None
    cagr_5year: Optional[float] = None
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
    latest_close: Optional[float] = None
    change_percent: Optional[float] = None
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

class FundRanking(BaseModel):
    """Individual fund's ranking in a comparison."""
    scheme_code: str
    rank: int
    composite_score: float
    group_scores: Dict[str, float]
    wins: List[str] = []
    is_recommended: bool = False
    recommendation_reason: Optional[str] = None

class RankingResult(BaseModel):
    """Full ranking output from the comparison engine."""
    rankings: List[FundRanking]
    comparison_summary: str

class FundComparisonItem(BaseModel):
    """Container for fund master details and computed metrics for comparison."""
    scheme_code: str
    fund_info: Optional[FundMasterRead] = None
    metrics: Optional[FundMetricsRead] = None

class ComparisonResponse(BaseModel):
    """Unified response for multi-fund comparison metrics."""
    funds: List[FundComparisonItem]
    ranking: Optional[RankingResult] = None
    warning: Optional[str] = None


# ============================================================================
# STOCK SCREENER SCHEMAS
# ============================================================================

class ScreenerFilterInput(BaseModel):
    """Validated input for stock screener filters."""
    # Valuation filters
    min_pe: Optional[float] = None
    max_pe: Optional[float] = None
    min_pb: Optional[float] = None
    max_pb: Optional[float] = None

    # Profitability filters
    min_roe: Optional[float] = None
    min_roce: Optional[float] = None
    min_pat_margin: Optional[float] = None
    min_ebitda_margin: Optional[float] = None

    # Growth filters
    min_revenue_growth: Optional[float] = None
    min_pat_growth: Optional[float] = None

    # Leverage filters
    max_debt_equity: Optional[float] = None
    min_interest_cov: Optional[float] = None

    # Quality filters
    min_cfo_to_pat: Optional[float] = None

    # Stock filters
    sector: Optional[str] = None
    market_cap_cat: Optional[str] = None
    rating_label: Optional[str] = None

    # Pagination
    page: int = 1
    limit: int = 25
    sort_by: str = "total_score"
    order: str = "desc"

    class Config:
        validate_default = True

    def validate_pe_range(self):
        """Validate PE range: 0 <= min_pe <= max_pe <= 500"""
        from app.query_utils import validate_min_max_range
        validate_min_max_range(self.min_pe, self.max_pe, "PE ratio range")
        if self.min_pe is not None and self.min_pe < 0:
            raise ValueError("min_pe: must be >= 0")
        if self.max_pe is not None and self.max_pe > 500:
            raise ValueError("max_pe: must be <= 500")

    def validate_pb_range(self):
        """Validate P/B range: 0 <= min_pb <= max_pb <= 50"""
        from app.query_utils import validate_min_max_range
        validate_min_max_range(self.min_pb, self.max_pb, "P/B ratio range")
        if self.min_pb is not None and self.min_pb < 0:
            raise ValueError("min_pb: must be >= 0")
        if self.max_pb is not None and self.max_pb > 50:
            raise ValueError("max_pb: must be <= 50")

    def validate_roe_range(self):
        """Validate ROE: -100 <= value <= 500"""
        if self.min_roe is not None and not (-100 <= self.min_roe <= 500):
            raise ValueError("min_roe: must be between -100 and 500")

    def validate_debt_equity(self):
        """Validate Debt/Equity: 0 <= value <= 100"""
        if self.max_debt_equity is not None and not (0 <= self.max_debt_equity <= 100):
            raise ValueError("max_debt_equity: must be between 0 and 100")

    def validate_margins(self):
        """Validate margins: -100 <= value <= 100"""
        for field, val in [
            ("min_pat_margin", self.min_pat_margin),
            ("min_ebitda_margin", self.min_ebitda_margin),
        ]:
            if val is not None and not (-100 <= val <= 100):
                raise ValueError(f"{field}: must be between -100 and 100")


class StockScreenerResult(BaseModel):
    """Single stock result from screener."""
    symbol: str
    company_name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    summary: Optional[str] = None
    market_cap_cat: Optional[str] = None
    latest_close: Optional[float] = None
    latest_date: Optional[date] = None
    roe: Optional[float] = None
    roce: Optional[float] = None
    pat_margin: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    debt_equity: Optional[float] = None
    revenue_growth: Optional[float] = None
    pat_growth: Optional[float] = None
    eps: Optional[float] = None
    interest_cov: Optional[float] = None
    cfo_to_pat: Optional[float] = None
    market_cap: Optional[float] = None
    low_52w: Optional[float] = None
    high_52w: Optional[float] = None
    revenue_per_share: Optional[float] = None
    dividend_yield: Optional[float] = None
    rating_label: Optional[str] = None
    total_score: Optional[float] = None


class ScreenerResponse(BaseModel):
    """Response for screener endpoint."""
    results: List[StockScreenerResult]
    total: int
    page: int
    limit: int
    filters_applied: Dict[str, Any]


class StockListResult(BaseModel):
    """
    Single stock from list_stocks endpoint.

    Note: Internal fields (is_active, data_quality, created_at, etc.) are excluded.
    Only public-facing fields are included in API responses.
    """

    id: int
    symbol: str
    company_name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    summary: Optional[str] = None
    market_cap_cat: Optional[str] = None
    latest_close: Optional[float] = None
    latest_date: Optional[date] = None
    rating_label: Optional[str] = None
    total_score: Optional[float] = None


class StockListResponse(BaseModel):
    """Response for list_stocks endpoint."""

    results: List[StockListResult]
    total: int
    page: int
    limit: int


class StockDetailResult(BaseModel):
    """
    Full stock detail response.

    Excludes internal fields: is_active, data_quality, created_at, updated_at.
    Only includes fields relevant to users.
    """

    id: int
    symbol: str
    nse_symbol: Optional[str] = None
    company_name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    summary: Optional[str] = None
    market_cap_cat: Optional[str] = None
    latest_close: Optional[float] = None
    latest_high: Optional[float] = None
    latest_low: Optional[float] = None
    latest_volume: Optional[int] = None
    latest_date: Optional[date] = None
    change_pct: Optional[float] = None
    rating_label: Optional[str] = None
    total_score: Optional[float] = None
    fundamental_score: Optional[float] = None
    technical_score: Optional[float] = None
    rsi_14: Optional[float] = None
    macd_hist: Optional[float] = None
    sma_200: Optional[float] = None
    sma_50: Optional[float] = None


# ============================================================================
# FUNDAMENTAL SCORING PIPELINE SCHEMAS
# ============================================================================

class FundamentalScoreRunRequest(BaseModel):
    """Request to trigger fundamental scoring for a stock."""
    symbol: str
    period_type: str = "annual"
    score_version: str = "v1.0"

class BulkFundamentalScoreRequest(BaseModel):
    """Request to trigger bulk fundamental scoring."""
    symbols: Optional[List[str]] = None  # If None, run for all active stocks
    period_type: str = "annual"
    score_version: str = "v1.0"
    recompute: bool = False

class ScoringStateSchema(BaseModel):
    """Pydantic representation of the LangGraph ScoringState."""
    stock_id: int
    symbol: str
    period_type: str
    score_version: str
    statements_data: Dict[str, List[Dict[str, Any]]] = {}
    pl_results: Optional[Dict[str, Any]] = None
    bs_results: Optional[Dict[str, Any]] = None
    cf_results: Optional[Dict[str, Any]] = None
    composite_score: float = 0.0
    reasoning_label: Optional[str] = None
    reasoning_text: Optional[str] = None
    status: str
    error: Optional[str] = None
    logs: List[str] = []

class FundamentalScoreRead(BaseModel):
    """Schema for reading a persisted fundamental score."""
    id: int
    stock_id: int
    period_end: date
    period_type: str
    score_version: str
    
    # Statement Scores (0-10)
    pl_score: float
    bs_score: float
    cf_score: float
    
    # Sub-component scores
    pl_growth_score: Optional[float] = None
    pl_margin_score: Optional[float] = None
    pl_eps_score: Optional[float] = None
    pl_consistency_score: Optional[float] = None
    
    bs_leverage_score: Optional[float] = None
    bs_liquidity_score: Optional[float] = None
    bs_asset_score: Optional[float] = None
    bs_networth_score: Optional[float] = None
    
    cf_operating_score: Optional[float] = None
    cf_capex_score: Optional[float] = None
    cf_financing_score: Optional[float] = None
    
    # Composite Result
    composite_fundamental_score: float
    reasoning_label: Optional[str] = None
    reasoning_text: Optional[str] = None
    
    created_at: datetime # Or computed_at depending on model? Model has computed_at.
    # Check model again: model has computed_at. 
    # But usually created_at is standard. I'll use computed_at to match model.
    computed_at: datetime
    model_config = ConfigDict(from_attributes=True)

