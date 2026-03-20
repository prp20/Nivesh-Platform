from sqlalchemy import Column, String, Numeric, TIMESTAMP, Date, Boolean, ForeignKey, text, UniqueConstraint
from sqlalchemy.sql import func
from .database import Base

class FundMaster(Base):
    """Master data for mutual fund schemes"""
    __tablename__ = "fund_master"
    
    scheme_code = Column(String(50), primary_key=True, nullable=False)
    scheme_name = Column(String(500), nullable=False)
    amc_name = Column(String(200), nullable=False)
    inception_date = Column(Date, nullable=False)
    plan_type = Column(String(20), nullable=False)  # 'Direct', 'Regular'
    scheme_category = Column(String(100), nullable=False)
    scheme_subcategory = Column(String(100))
    benchmark_index_code = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class FundNavHistory(Base):
    """Historical NAV data for all mutual fund schemes (TimescaleDB Hypertable)"""
    __tablename__ = "fund_nav_history"
    __table_args__ = (
        UniqueConstraint('scheme_code', 'nav_date', name='uq_fund_nav_scheme_date'),
    )
    
    scheme_code = Column(String(50), ForeignKey("fund_master.scheme_code", ondelete="CASCADE"), primary_key=True)
    nav_date = Column(Date, primary_key=True)
    nav_value = Column(Numeric(15, 4), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class BenchmarkNavHistory(Base):
    """Historical index values for benchmark indices (TimescaleDB Hypertable)"""
    __tablename__ = "benchmark_nav_history"
    __table_args__ = (
        UniqueConstraint('benchmark_code', 'nav_date', name='uq_benchmark_nav_date'),
    )
    
    benchmark_code = Column(String(50), ForeignKey("benchmark_master.benchmark_code", ondelete="CASCADE"), primary_key=True)
    nav_date = Column(Date, primary_key=True)
    index_value = Column(Numeric(15, 4), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class FundMetrics(Base):
    """Daily computed performance and risk metrics"""
    __tablename__ = "fund_metrics"
    
    scheme_code = Column(String(50), ForeignKey("fund_master.scheme_code", ondelete="CASCADE"), primary_key=True)
    current_nav = Column(Numeric(15, 4), nullable=False)
    nav_date = Column(Date, nullable=False)
    aum_in_crores = Column(Numeric(18, 2))
    rolling_return_3year = Column(Numeric(10, 4))
    rolling_return_5year = Column(Numeric(10, 4))
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
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
