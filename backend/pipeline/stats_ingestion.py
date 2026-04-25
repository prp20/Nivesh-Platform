# backend/pipeline/stats_ingestion.py
"""
Ingests point-in-time statistics and ratios from yfinance Ticker.info.
Groups metrics into Daily (Price-dependent) and Fundamental (Quarterly) categories.
"""

import asyncio
import logging
import yfinance as yf
from datetime import date, datetime
from typing import Dict, Any, Optional, List
from pipeline.audit import audit_job
from app.database import raw_connection

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

DAILY_KEYS = [
    "marketCap",
    "fiftyTwoWeekLow",
    "fiftyTwoWeekHigh",
    "priceToBook",
    "dividendYield",
    "enterpriseToEbitda",
    "enterpriseToRevenue",
    "dividendRate"
]

FUNDAMENTAL_KEYS = [
    "bookValue",
    "pegRatio",
    "quickRatio",
    "currentRatio",
    "debtToEquity",
    "revenuePerShare",
    "returnOnEquity",
    "returnOnAssets",
    "payoutRatio",
    "totalDebt",
    "totalCash",
    "freeCashflow",
    "grossMargins",
    "operatingMargins"
]

ALL_KEYS = DAILY_KEYS + FUNDAMENTAL_KEYS

# ─── Main Entry Points ────────────────────────────────────────────────────────

async def sync_daily_stats():
    """Sync price-dependent stats (Daily)."""
    await _run_sync(DAILY_KEYS, "daily")

async def sync_fundamental_stats():
    """Sync non-price stats (Quarterly/Weekly)."""
    await _run_sync(FUNDAMENTAL_KEYS, "fundamental_refresh")

async def sync_all_stats(symbol: Optional[str] = None):
    """Sync all stats for one or all stocks."""
    await _run_sync(ALL_KEYS, "all_stats", symbol=symbol)

# ─── Core Logic ────────────────────────────────────────────────────────────────

async def _run_sync(keys: List[str], job_type: str, symbol: Optional[str] = None):
    """Generic sync loop for a set of keys."""
    stocks = await _fetch_stocks(symbol)
    if not stocks:
        return

    async with audit_job(f"stats_{job_type}_sync", records_in=len(stocks)) as audit:
        success_count = 0
        for i, stock in enumerate(stocks):
            try:
                # yfinance.Ticker is blocking, run in thread
                info = await asyncio.to_thread(_fetch_yf_info, stock["yf_symbol"])
                if not info:
                    logger.warning(f"No info found for {stock['symbol']}")
                    continue

                processed_data = _process_info(info, keys)
                if processed_data:
                    await _upsert_stats(stock["id"], processed_data)
                    success_count += 1

                # Polite delay between API calls
                await asyncio.sleep(1.0)
                await audit.update_progress(i + 1)

            except Exception as e:
                logger.error(f"Failed to sync stats for {stock['symbol']}: {e}")

        audit.records_out = success_count
        logger.info(f"Stats sync ({job_type}) complete: {success_count}/{len(stocks)} stocks updated")

def _fetch_yf_info(yf_symbol: str) -> Optional[Dict[str, Any]]:
    """Blocking call to yfinance Ticker.info."""
    try:
        ticker = yf.Ticker(yf_symbol)
        return ticker.info
    except Exception as e:
        logger.error(f"yfinance info fetch failed for {yf_symbol}: {e}")
        return None

def _process_info(info: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    """Extract and format requested keys from raw info dict."""
    data = {}
    
    # Mapping yf keys to DB column names (as defined in models.py and migration)
    mapping = {
        "marketCap": "market_cap",
        "dividendYield": "dividend_yield",
        "fiftyTwoWeekLow": "low_52w",
        "fiftyTwoWeekHigh": "high_52w",
        "bookValue": "book_value_ps",
        "priceToBook": "pb_ratio",
        "pegRatio": "peg_ratio",
        "quickRatio": "quick_ratio",
        "currentRatio": "current_ratio",
        "debtToEquity": "debt_equity",
        "revenuePerShare": "revenue_per_share",
        "returnOnEquity": "roe",
        "returnOnAssets": "roa",
        "enterpriseToEbitda": "ev_ebitda",
        "enterpriseToRevenue": "ev_sales",
        "payoutRatio": "dividend_payout_ratio",
        "dividendRate": "dividend_per_share",
        "totalDebt": "net_debt", # will subtract cash below
        "totalCash": "total_cash_yf", # temporary for calculation
        "freeCashflow": "fcf",
        "grossMargins": "gross_margin",
        "operatingMargins": "operating_margin"
    }

    for yf_key in keys:
        val = info.get(yf_key)
        if val is None or val == "n/a":
            continue
            
        db_col = mapping.get(yf_key)
        if not db_col:
            continue

        # Specific formatting logic
        if yf_key == "marketCap":
            # Convert to Crores (INR)
            data[db_col] = float(val) / 10_000_000
        elif yf_key in ["returnOnEquity", "returnOnAssets", "payoutRatio", "grossMargins", "operatingMargins"]:
            # Convert decimal (0.15) to percentage (15.0)
            data[db_col] = float(val) * 100
        elif yf_key == "dividendYield":
            # dividendYield is often decimal (0.015 = 1.5%)
            data[db_col] = float(val) * 100
        elif yf_key in ["totalDebt", "totalCash", "freeCashflow"]:
            # Convert to Crores
            data[db_col] = float(val) / 10_000_000
        else:
            data[db_col] = float(val)

    # Post-process: Net Debt = Total Debt - Total Cash (if both available)
    if "total_cash_yf" in data:
        cash = data.pop("total_cash_yf")
        if "net_debt" in data:
            data["net_debt"] = data["net_debt"] - cash

    return data

async def _upsert_stats(stock_id: int, data: Dict[str, Any]):
    """
    Upsert data into financial_ratios. 
    Uses 'latest' as period_type to store point-in-time statistics.
    """
    if not data:
        return

    # Use today's date for 'latest' statistics tracking
    today = date.today()
    period_type = "latest"

    # Construct the UPSERT query dynamically based on keys present
    cols = ["stock_id", "period_end", "period_type"] + list(data.keys())
    placeholders = [f"${i+1}" for i in range(len(cols))]
    
    update_clause = ", ".join([f"{k} = EXCLUDED.{k}" for k in data.keys()])
    update_clause += ", computed_at = CURRENT_TIMESTAMP"

    sql = f"""
        INSERT INTO financial_ratios ({", ".join(cols)})
        VALUES ({", ".join(placeholders)})
        ON CONFLICT (stock_id, period_end, period_type) 
        DO UPDATE SET {update_clause}
    """
    
    args = [stock_id, today, period_type] + list(data.values())

    async with raw_connection() as conn:
        await conn.execute(sql, *args)

# ─── DB Helpers ──────────────────────────────────────────────────────────────

async def _fetch_stocks(symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch active stocks, optionally filtered by symbol."""
    async with raw_connection() as conn:
        if symbol:
            rows = await conn.fetch(
                "SELECT id, symbol, yf_symbol FROM stocks WHERE symbol = $1 AND is_active = TRUE", 
                symbol.upper()
            )
        else:
            rows = await conn.fetch(
                "SELECT id, symbol, yf_symbol FROM stocks WHERE is_active = TRUE AND is_index = FALSE"
            )
        return [dict(r) for r in rows]
