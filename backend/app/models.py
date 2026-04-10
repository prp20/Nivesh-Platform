from sqlalchemy import Column, String, Numeric, TIMESTAMP, Date, Boolean, ForeignKey, text, Index, Integer, BigInteger, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from .database import Base

class SyncJob(Base):
    """Tracks the progress of a background synchronization task"""
    __tablename__ = "sync_jobs"
    
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    scheme_code = Column(String(50), ForeignKey("fund_master.scheme_code", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="RUNNING")  # RUNNING, COMPLETED, FAILED
    message = Column(String(500))
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('uq_running_sync_job', 'scheme_code', unique=True, postgresql_where=text("status = 'RUNNING'")),
    )

class FundMaster(Base):
    """Master data for mutual fund schemes"""
    __tablename__ = "fund_master"

    __table_args__ = (
        # GIN trigram indexes for fast substring ilike() searches.
        # Requires: CREATE EXTENSION IF NOT EXISTS pg_trgm;
        # These replace the earlier B-Tree indexes which did not help for
        # %pattern% queries. create_all will create them on a fresh DB;
        # run the CREATE INDEX statements manually on existing deployments.
        Index(
            "ix_fund_master_amc_name_trgm",
            "amc_name",
            postgresql_using="gin",
            postgresql_ops={"amc_name": "gin_trgm_ops"},
        ),
        Index(
            "ix_fund_master_scheme_category_trgm",
            "scheme_category",
            postgresql_using="gin",
            postgresql_ops={"scheme_category": "gin_trgm_ops"},
        ),
        # B-Tree indexes for equality filters (plan_type, is_active)
        Index("ix_fund_master_plan_type", "plan_type"),
        Index("ix_fund_master_is_active", "is_active"),
    )

    scheme_code = Column(String(50), primary_key=True, nullable=False)
    scheme_name = Column(String(500), nullable=False)
    amc_name = Column(String(200), nullable=False)
    inception_date = Column(Date, nullable=False)
    plan_type = Column(String(20), nullable=False)  # 'Direct', 'Regular'
    scheme_category = Column(String(100), nullable=False)
    scheme_subcategory = Column(String(100))
    benchmark_index_code = Column(String(50))
    isin = Column(String(50), unique=True, index=True)
    manager_experience = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    metrics = relationship("FundMetrics", back_populates="fund", uselist=False)


class BenchmarkMaster(Base):
    """Master data for benchmark indices"""
    __tablename__ = "benchmark_master"
    
    benchmark_code = Column(String(50), primary_key=True)
    benchmark_name = Column(String(200), nullable=False)
    ticker = Column(String(50), nullable=False)
    benchmark_type = Column(String(100))
    asset_class = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    metrics = relationship("BenchmarkMetrics", back_populates="benchmark", uselist=False)


class FundNavHistory(Base):
    """Historical NAV data for all mutual fund schemes"""
    __tablename__ = "fund_nav_history"
    __table_args__ = (
        Index('ix_fund_nav_history_nav_date', 'nav_date'),
    )
    
    scheme_code = Column(String(50), ForeignKey("fund_master.scheme_code", ondelete="CASCADE"), primary_key=True)
    nav_date = Column(Date, primary_key=True)
    nav_value = Column(Numeric(15, 4), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class BenchmarkNavHistory(Base):
    """Historical index values for benchmark indices"""
    __tablename__ = "benchmark_nav_history"
    __table_args__ = (
        Index('ix_benchmark_nav_history_nav_date', 'nav_date'),
    )
    
    benchmark_code = Column(String(50), ForeignKey("benchmark_master.benchmark_code", ondelete="CASCADE"), primary_key=True)
    nav_date = Column(Date, primary_key=True)
    index_value = Column(Numeric(15, 4), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class BenchmarkMetrics(Base):
    """Daily computed performance and risk metrics for indices"""
    __tablename__ = "benchmark_metrics"
    
    benchmark_code = Column(String(50), ForeignKey("benchmark_master.benchmark_code", ondelete="CASCADE"), primary_key=True)
    current_nav = Column(Numeric(15, 4), nullable=False)
    nav_date = Column(Date, nullable=False)
    cagr_3year = Column(Numeric(10, 4))
    cagr_5year = Column(Numeric(10, 4))
    sortino_ratio = Column(Numeric(10, 4))
    sharpe_ratio = Column(Numeric(10, 4))
    standard_deviation = Column(Numeric(10, 4))
    maximum_drawdown = Column(Numeric(10, 4))
    metrics_calculated_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    benchmark = relationship("BenchmarkMaster", back_populates="metrics")


class FundMetrics(Base):
    """Daily computed performance and risk metrics"""
    __tablename__ = "fund_metrics"
    
    scheme_code = Column(String(50), ForeignKey("fund_master.scheme_code", ondelete="CASCADE"), primary_key=True)
    current_nav = Column(Numeric(15, 4), nullable=False)
    nav_date = Column(Date, nullable=False)
    aum_in_crores = Column(Numeric(18, 2))
    expense_ratio = Column(Numeric(5, 4))
    fund_rating = Column(Numeric(5, 2))
    volatility = Column(Numeric(10, 4))
    cagr_3year = Column(Numeric(10, 4))
    cagr_5year = Column(Numeric(10, 4))
    absolute_return_1y = Column(Numeric(10, 4))
    absolute_return_3y = Column(Numeric(10, 4))
    absolute_return_5y = Column(Numeric(10, 4))
    absolute_return_10y = Column(Numeric(10, 4))
    short_term_return_6m = Column(Numeric(10, 4)) # Adding 6M as it's common
    upside_capture = Column(Numeric(10, 4))
    downside_capture = Column(Numeric(10, 4))
    sortino_ratio = Column(Numeric(10, 4))
    sharpe_ratio = Column(Numeric(10, 4))
    alpha = Column(Numeric(10, 4))
    beta = Column(Numeric(10, 4))
    standard_deviation = Column(Numeric(10, 4))
    maximum_drawdown = Column(Numeric(10, 4))
    tracking_error = Column(Numeric(10, 4))
    information_ratio = Column(Numeric(10, 4))
    metrics_calculated_at = Column(TIMESTAMP, server_default=func.now())
    calculation_period_start_date = Column(Date)
    calculation_period_end_date = Column(Date)
    has_sufficient_data = Column(Boolean, default=True)
    data_completeness_percentage = Column(Numeric(5, 2))
    final_verdict = Column(String(1000))
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    fund = relationship("FundMaster", back_populates="metrics")


# ─── Stock Market Models (Phase 1) ────────────────────────────────────────────

class Stock(Base):
    __tablename__ = "stocks"

    id             = Column(Integer, primary_key=True)
    symbol         = Column(String(20), nullable=False, unique=True)
    nse_symbol     = Column(String(20))
    bse_code       = Column(String(10))
    yf_symbol      = Column(String(30), nullable=False)
    screener_slug  = Column(String(50))
    company_name   = Column(String(255), nullable=False)
    sector         = Column(String(100))
    industry       = Column(String(100))
    market_cap_cat = Column(String(10))
    is_index       = Column(Boolean, default=False)
    is_active      = Column(Boolean, default=True)
    data_quality   = Column(String(10), default="OK")
    created_at     = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at     = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class PriceData(Base):
    __tablename__ = "price_data"
    __table_args__ = (
        UniqueConstraint('stock_id', 'price_date', name='uq_price_data_stock_date'),
        Index('ix_price_data_stock_date_desc', 'stock_id', 'price_date'),
    )

    id         = Column(BigInteger, primary_key=True)
    stock_id   = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    price_date = Column(Date, nullable=False)
    open       = Column(Numeric(12, 4))
    high       = Column(Numeric(12, 4))
    low        = Column(Numeric(12, 4))
    close      = Column(Numeric(12, 4), nullable=False)
    adj_close  = Column(Numeric(12, 4))
    volume     = Column(BigInteger)


class FinancialStatement(Base):
    __tablename__ = "financial_statements"
    __table_args__ = (
        UniqueConstraint('stock_id', 'statement_type', 'period_type', 'period_end',
                        name='uq_financial_stmt_stock_type_period'),
        Index('ix_financial_stmt_stock_period', 'stock_id', 'period_end'),
    )

    id             = Column(Integer, primary_key=True)
    stock_id       = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    statement_type = Column(String(5), nullable=False)   # 'PL' | 'BS' | 'CF'
    period_type    = Column(String(10), nullable=False)  # 'annual' | 'quarterly'
    period_end     = Column(Date, nullable=False)
    currency       = Column(String(5), default="INR")
    data           = Column(JSONB, nullable=False)
    raw_data       = Column(JSONB)
    scraped_at     = Column(TIMESTAMP(timezone=True), server_default=func.now())
    raw_checksum   = Column(String(64))


class ShareholdingPattern(Base):
    __tablename__ = "shareholding_pattern"
    __table_args__ = (
        UniqueConstraint('stock_id', 'period_end',
                        name='uq_shareholding_pattern_stock_period'),
        Index('ix_shareholding_pattern_stock_period', 'stock_id', 'period_end'),
    )

    id              = Column(Integer, primary_key=True)
    stock_id        = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    period_end      = Column(Date, nullable=False)
    promoter_pct    = Column(Numeric(6, 3))
    fii_pct         = Column(Numeric(6, 3))
    dii_pct         = Column(Numeric(6, 3))
    public_pct      = Column(Numeric(6, 3))
    pledged_pct     = Column(Numeric(6, 3))
    promoter_change = Column(Numeric(6, 3))
    fii_change      = Column(Numeric(6, 3))
    scraped_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())


class FinancialRatio(Base):
    __tablename__ = "financial_ratios"

    id             = Column(Integer, primary_key=True)
    stock_id       = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    period_end     = Column(Date, nullable=False)
    period_type    = Column(String(10), nullable=False)
    pe_ratio       = Column(Numeric(10, 3))
    pb_ratio       = Column(Numeric(10, 3))
    ps_ratio       = Column(Numeric(10, 3))
    ev_ebitda      = Column(Numeric(10, 3))
    peg_ratio      = Column(Numeric(10, 3))
    roe            = Column(Numeric(10, 3))
    roce           = Column(Numeric(10, 3))
    roa            = Column(Numeric(10, 3))
    gross_margin   = Column(Numeric(10, 3))
    ebitda_margin  = Column(Numeric(10, 3))
    pat_margin     = Column(Numeric(10, 3))
    debt_equity    = Column(Numeric(10, 3))
    interest_cov   = Column(Numeric(10, 3))
    current_ratio  = Column(Numeric(10, 3))
    quick_ratio    = Column(Numeric(10, 3))
    revenue_growth = Column(Numeric(10, 3))
    pat_growth     = Column(Numeric(10, 3))
    eps_growth     = Column(Numeric(10, 3))
    eps            = Column(Numeric(12, 4))
    book_value_ps  = Column(Numeric(12, 4))
    dividend_yield = Column(Numeric(8, 4))
    cfo_to_pat     = Column(Numeric(10, 3))
    computed_at    = Column(TIMESTAMP(timezone=True), server_default=func.now())


class TechnicalIndicator(Base):
    __tablename__ = "technical_indicators"
    __table_args__ = (
        UniqueConstraint('stock_id', 'ind_date', 'timeframe',
                        name='uq_technical_indicator_stock_date_tf'),
        Index('ix_technical_indicator_stock_date', 'stock_id', 'ind_date'),
    )

    id            = Column(BigInteger, primary_key=True)
    stock_id      = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    ind_date      = Column(Date, nullable=False)
    timeframe     = Column(String(5), nullable=False)
    sma_20        = Column(Numeric(12, 4))
    sma_50        = Column(Numeric(12, 4))
    sma_200       = Column(Numeric(12, 4))
    ema_9         = Column(Numeric(12, 4))
    ema_21        = Column(Numeric(12, 4))
    ema_50        = Column(Numeric(12, 4))
    rsi_14        = Column(Numeric(8, 4))
    macd_line     = Column(Numeric(12, 4))
    macd_signal   = Column(Numeric(12, 4))
    macd_hist     = Column(Numeric(12, 4))
    bb_upper      = Column(Numeric(12, 4))
    bb_middle     = Column(Numeric(12, 4))
    bb_lower      = Column(Numeric(12, 4))
    atr_14        = Column(Numeric(12, 4))
    adx_14        = Column(Numeric(8, 4))
    stoch_k       = Column(Numeric(8, 4))
    stoch_d       = Column(Numeric(8, 4))
    volume_sma_20 = Column(BigInteger)


class DetectedPattern(Base):
    __tablename__ = "detected_patterns"

    id             = Column(Integer, primary_key=True)
    stock_id       = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    pattern_type   = Column(String(30), nullable=False)
    timeframe      = Column(String(5), nullable=False)
    detected_on    = Column(Date, nullable=False)
    pattern_start  = Column(Date, nullable=False)
    pattern_end    = Column(Date, nullable=False)
    breakout_level = Column(Numeric(12, 4))
    direction      = Column(String(10))
    confidence     = Column(Numeric(4, 3))
    is_active      = Column(Boolean, default=True)
    metadata_      = Column("metadata", JSONB)
    created_at     = Column(TIMESTAMP(timezone=True), server_default=func.now())


class StockRating(Base):
    __tablename__ = "stock_ratings"
    __table_args__ = (
        UniqueConstraint("stock_id", "rated_on", name="uq_stock_rating_stock_date"),
    )

    id                 = Column(Integer, primary_key=True)
    stock_id           = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    rated_on           = Column(Date, nullable=False)
    total_score        = Column(Numeric(6, 3))
    rating_label       = Column(String(15))
    fundamental_score  = Column(Numeric(6, 3))
    valuation_score    = Column(Numeric(6, 3))
    technical_score    = Column(Numeric(6, 3))
    momentum_score     = Column(Numeric(6, 3))
    quality_score      = Column(Numeric(6, 3))   # reserved for future quality metrics
    shareholding_score = Column(Numeric(6, 3))
    score_breakdown_   = Column("score_breakdown", JSONB)


class PipelineAudit(Base):
    __tablename__ = "pipeline_audit"

    id          = Column(Integer, primary_key=True)
    job_name    = Column(String(60), nullable=False)
    stock_id    = Column(Integer, ForeignKey("stocks.id"))
    status      = Column(String(10), nullable=False)
    started_at  = Column(TIMESTAMP(timezone=True), server_default=func.now())
    ended_at    = Column(TIMESTAMP(timezone=True))
    records_in  = Column(Integer, default=0)
    records_out = Column(Integer, default=0)
    error_msg   = Column(Text)
    metadata_   = Column("metadata", JSONB)
