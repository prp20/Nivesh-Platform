from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import Optional, List, Dict, Any


# ============================================================================
# BENCHMARK SCHEMAS
# ============================================================================

class BenchmarkNavHistoryCreate(BaseModel):
    benchmark_code: str
    nav_date: date
    index_value: float

class BenchmarkNavHistoryRead(BenchmarkNavHistoryCreate):
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

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
# MARKET SNAPSHOT SCHEMAS (new — for Phase 1+ API contract)
# ============================================================================

class MarketSnapshot(BaseModel):
    snap_date: date
    nifty50: Optional[float] = None
    sensex: Optional[float] = None
    bank_nifty: Optional[float] = None
    nifty500: Optional[float] = None
    advance_count: Optional[int] = None
    decline_count: Optional[int] = None
    unchanged_count: Optional[int] = None
    total_volume_cr: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class SectorReturn(BaseModel):
    sector: str
    return_1d: Optional[float] = None
    return_1w: Optional[float] = None
    return_1m: Optional[float] = None

class FIIDIIFlow(BaseModel):
    flow_date: date
    fii_buy: Optional[float] = None
    fii_sell: Optional[float] = None
    dii_buy: Optional[float] = None
    dii_sell: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class MoverRow(BaseModel):
    symbol: str
    company_name: Optional[str] = None
    change_pct: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None


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
