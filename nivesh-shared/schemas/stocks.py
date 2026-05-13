from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import Optional, List, Dict, Any


# ============================================================================
# STOCK SCREENER SCHEMAS
# ============================================================================

class ScreenerFilterInput(BaseModel):
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
    # Advanced fundamental filters
    min_roic: Optional[float] = None
    min_ev_ebitda: Optional[float] = None
    max_ev_ebitda: Optional[float] = None
    min_piotroski: Optional[int] = None
    min_fcf_yield: Optional[float] = None
    # Advanced technical filters
    min_beta: Optional[float] = None
    max_beta: Optional[float] = None
    min_rs_6m: Optional[float] = None
    min_volume_ratio: Optional[float] = None
    # Pagination
    page: int = 1
    limit: int = 25
    sort_by: str = "total_score"
    order: str = "desc"

    class Config:
        validate_default = True

class StockScreenerResult(BaseModel):
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
    ev_ebitda: Optional[float] = None
    roic: Optional[float] = None
    fcf_yield: Optional[float] = None
    piotroski_f_score: Optional[int] = None
    altman_z_score: Optional[float] = None
    beta_1y: Optional[float] = None
    rs_6m_vs_nifty: Optional[float] = None
    pct_from_52w_high: Optional[float] = None
    pct_from_52w_low: Optional[float] = None
    volume_ratio: Optional[float] = None

class ScreenerResponse(BaseModel):
    results: List[StockScreenerResult]
    total: int
    page: int
    limit: int
    filters_applied: Dict[str, Any]


# ============================================================================
# STOCK LIST / DETAIL SCHEMAS
# ============================================================================

class StockListResult(BaseModel):
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
    results: List[StockListResult]
    total: int
    page: int
    limit: int

class StockDetailResult(BaseModel):
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
    obv: Optional[float] = None
    vwap_20: Optional[float] = None
    cci_20: Optional[float] = None
    beta_1y: Optional[float] = None
    rs_6m_vs_nifty: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ebitda_margin: Optional[float] = None
    roe: Optional[float] = None
    roce: Optional[float] = None
    ev_ebitda: Optional[float] = None
    piotroski_f_score: Optional[int] = None
    debt_equity: Optional[float] = None
    pct_from_52w_high: Optional[float] = None
    pct_from_52w_low: Optional[float] = None


# ============================================================================
# OHLCV SCHEMA (new — for Phase 1+ API contract)
# ============================================================================

class OHLCVRow(BaseModel):
    symbol: str
    trade_date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    adjusted_close: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# FUNDAMENTAL SCORING SCHEMAS
# ============================================================================

class FundamentalScoreRunRequest(BaseModel):
    symbol: str
    period_type: str = "annual"
    score_version: str = "v1.0"

class BulkFundamentalScoreRequest(BaseModel):
    symbols: Optional[List[str]] = None
    period_type: str = "annual"
    score_version: str = "v1.0"
    recompute: bool = False

class FundamentalScoreRead(BaseModel):
    id: int
    stock_id: int
    period_end: date
    period_type: str
    score_version: str
    pl_score: float
    bs_score: float
    cf_score: float
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
    composite_fundamental_score: float
    reasoning_label: Optional[str] = None
    reasoning_text: Optional[str] = None
    computed_at: datetime
    model_config = ConfigDict(from_attributes=True)
