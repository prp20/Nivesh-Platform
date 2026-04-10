"""
Application constants and configuration values.

Centralizes all magic numbers and configuration constants to improve maintainability.
"""

# ============================================================================
# FINANCIAL CALCULATIONS
# ============================================================================

# Risk-free rate for Sharpe/Sortino ratio calculations (India 10-year GSec)
ANNUAL_RISK_FREE_RATE = 0.065

# Number of trading days per year (standard for financial calculations)
TRADING_DAYS_PER_YEAR = 252

# Minimum data completeness percentage required for metrics
MIN_DATA_COMPLETENESS_PCT = 0.90  # 90% of requested period

# ============================================================================
# DATA INGESTION & PIPELINE
# ============================================================================

# Batch size for price ingestion (avoid rate limits from yfinance)
PRICE_INGESTION_CHUNK_SIZE = 30

# Number of trading days to fetch for daily ingestion
PRICE_INGESTION_LOOKBACK_DAYS = 5

# Maximum number of retries for failed API calls
MAX_API_RETRIES = 3

# Base delay for exponential backoff (in seconds)
EXPONENTIAL_BACKOFF_BASE = 2

# Timeout for external API calls (in seconds)
API_CALL_TIMEOUT_SECS = 15

# Delay between stocks during fundamental scraping (be polite to screener.in)
FUNDAMENTAL_SCRAPE_DELAY_SECS = 2.5

# Only scrape stocks not updated in last N days
FUNDAMENTAL_SCRAPE_THRESHOLD_DAYS = 90

# ============================================================================
# DATABASE & PAGINATION
# ============================================================================

# Default items per page in paginated responses
DEFAULT_PAGE_SIZE = 25

# Maximum items per page (prevent memory exhaustion)
MAX_PAGE_SIZE = 100

# Maximum page number (prevent huge offset queries)
MAX_PAGE_NUMBER = 10000

# ============================================================================
# RATE LIMITING
# ============================================================================

# Rate limit for stock screener endpoint: 100 requests per minute
SCREENER_RATE_LIMIT = (100, 60)

# Rate limit for stock listing endpoint: 1000 requests per minute
STOCKS_RATE_LIMIT = (1000, 60)

# Rate limit for stock search endpoint: 500 requests per minute
STOCKS_SEARCH_RATE_LIMIT = (500, 60)

# Rate limit for pipeline endpoints (admin-only): 50 requests per minute
PIPELINE_RATE_LIMIT = (50, 60)

# Default rate limit for unlisted endpoints: 1000 requests per minute
DEFAULT_RATE_LIMIT = (1000, 60)

# ============================================================================
# TECHNICAL ANALYSIS PERIODS
# ============================================================================

# Short-term moving average period (ta-lib default)
SMA_SHORT = 20

# Medium-term moving average period
SMA_MEDIUM = 50

# Long-term moving average period
SMA_LONG = 200

# Exponential moving average short period
EMA_SHORT = 9

# Exponential moving average medium period
EMA_MEDIUM = 21

# Exponential moving average long period
EMA_LONG = 50

# RSI period
RSI_PERIOD = 14

# Bollinger Bands period
BOLLINGER_PERIOD = 20

# Bollinger Bands standard deviation multiplier
BOLLINGER_STD_DEV = 2

# ATR (Average True Range) period
ATR_PERIOD = 14

# ADX (Average Directional Index) period
ADX_PERIOD = 14

# Stochastic period
STOCHASTIC_PERIOD = 14

# Stochastic smoothing period for %K
STOCHASTIC_K_SMOOTHING = 3

# Stochastic smoothing period for %D
STOCHASTIC_D_SMOOTHING = 3

# ============================================================================
# VALUATION BOUNDS (for input validation)
# ============================================================================

# P/E ratio bounds for validation
PE_RATIO_MIN = 0
PE_RATIO_MAX = 500

# P/B ratio bounds for validation
PB_RATIO_MIN = 0
PB_RATIO_MAX = 50

# P/S ratio bounds for validation
PS_RATIO_MIN = 0
PS_RATIO_MAX = 100

# ROE bounds for validation (can be negative)
ROE_MIN = -100
ROE_MAX = 500

# Margin bounds (can be negative)
MARGIN_MIN = -100
MARGIN_MAX = 100

# Debt/Equity bounds for validation
DEBT_EQUITY_MIN = 0
DEBT_EQUITY_MAX = 100

# Interest coverage minimum (must be positive if not None)
INTEREST_COVERAGE_MIN = 0
