"""
User-private data models — watchlist, portfolio, transactions, preferences.

All data here is stored locally in SQLite and never sent to the server.
"""

from sqlalchemy import Column, Integer, String, Float, Date, Text, TIMESTAMP
from sqlalchemy.sql import func

from ..database import Base


class Watchlist(Base):
    """
    User's personal watchlist — stocks and funds to track.
    Never sent to the server. Local only.
    """
    __tablename__ = "watchlist"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    symbol       = Column(String(50), nullable=False)
    asset_type   = Column(String(10), nullable=False)
    # asset_type: 'STOCK' | 'FUND'
    # For STOCK: symbol is the NSE symbol (e.g. 'RELIANCE')
    # For FUND:  symbol is the scheme_code (e.g. '119598')
    display_name = Column(String(255))
    notes        = Column(Text)
    alert_above  = Column(Float)      # Price/NAV alert threshold (high)
    alert_below  = Column(Float)      # Price/NAV alert threshold (low)
    added_at     = Column(TIMESTAMP, server_default=func.now())
    updated_at   = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class PortfolioHolding(Base):
    """
    User's actual holdings. Never sent to the server.
    Supports both stocks and mutual funds in one table.
    """
    __tablename__ = "portfolio_holdings"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    symbol       = Column(String(50), nullable=False)
    asset_type   = Column(String(10), nullable=False)   # 'STOCK' | 'FUND'
    quantity     = Column(Float, nullable=False)
    avg_cost     = Column(Float, nullable=False)         # Per unit cost (price or NAV)
    buy_date     = Column(Date, nullable=False)
    folio_number = Column(String(50))                    # MF folio number, if applicable
    broker       = Column(String(100))                   # Broker/AMC name
    notes        = Column(Text)
    created_at   = Column(TIMESTAMP, server_default=func.now())
    updated_at   = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Transaction(Base):
    """
    Full transaction history — buy, sell, dividend, SIP instalment.
    Local ledger only.
    """
    __tablename__ = "transactions"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    symbol       = Column(String(50), nullable=False)
    asset_type   = Column(String(10), nullable=False)
    txn_type     = Column(String(15), nullable=False)
    # txn_type: 'BUY' | 'SELL' | 'DIVIDEND' | 'SIP' | 'SWITCH_IN' | 'SWITCH_OUT'
    quantity     = Column(Float, nullable=False)
    price        = Column(Float, nullable=False)         # Price or NAV at time of txn
    txn_date     = Column(Date, nullable=False)
    amount       = Column(Float)                         # quantity × price (stored for quick calc)
    brokerage    = Column(Float, default=0.0)
    notes        = Column(Text)
    created_at   = Column(TIMESTAMP, server_default=func.now())


class UserPreference(Base):
    """
    Key-value store for all user settings.

    Using a KV table rather than a single wide row means
    adding new preferences doesn't require a schema migration.

    Keys in use:
      'default_benchmark'   → benchmark_code string
      'default_plan_type'   → 'Direct' | 'Regular'
      'chart_interval'      → '1d' | '1w'
      'theme'               → 'dark' | 'light'
      'last_login_username' → username string
    """
    __tablename__ = "user_preferences"

    key        = Column(String(100), primary_key=True)
    value      = Column(Text, nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
