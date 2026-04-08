"""
Wraps the existing ScreenerScraper to:
1. Fetch data from screener.in
2. Normalise using pipeline/normalizer.py
3. Store to financial_statements + shareholding_pattern tables
4. Use checksum deduplication to skip unchanged data
"""

import sys
import asyncio
import hashlib
import logging
import random
from datetime import date, datetime
import os

# Import the EXISTING scraper — do not modify that file
# Add parent directory (project root) to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from fundamental_data_extractor import ScreenerScraper
except ImportError:
    # Fallback if running from different directory
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from fundamental_data_extractor import ScreenerScraper

from pipeline.normalizer import (
    normalize_financial_table,
    normalize_shareholding,
    validate_pl,
    validate_bs,
    _slugify,
)
from pipeline.audit import audit_job
from app.database import raw_connection

logger = logging.getLogger(__name__)


# ─── Main entry points ────────────────────────────────────────────────────────

async def run_fundamental_scrape_all():
    """Scrape all active stocks that haven't been scraped in 90+ days."""
    async with audit_job("fundamental_scrape_all") as audit:
        stocks = await _fetch_stocks_needing_scrape(days_since_last=90)
        scraper = ScreenerScraper(delay_seconds=2.5)
        total = 0
        for stock in stocks:
            success = await _scrape_and_store(scraper, stock)
            if success:
                total += 1
            # Polite delay between stocks
            await asyncio.sleep(random.uniform(2.0, 5.0))
        audit.records_out = total
        logger.info(f"fundamental_scrape_all: {total}/{len(stocks)} stocks scraped")


async def run_fundamental_scrape_one(symbol: str):
    """Scrape a single stock (for manual admin triggers)."""
    async with audit_job("fundamental_scrape_single") as audit:
        stock = await _fetch_stock_by_symbol(symbol)
        if not stock:
            raise ValueError(f"Stock {symbol} not found")
        scraper = ScreenerScraper(delay_seconds=1.5)
        success = await _scrape_and_store(scraper, stock)
        audit.records_out = 1 if success else 0


# ─── Core scrape + store logic ────────────────────────────────────────────────

async def _scrape_and_store(scraper: ScreenerScraper, stock: dict) -> bool:
    ticker = stock.get("screener_slug") or stock["symbol"]

    try:
        # Try consolidated first, fall back to standalone
        raw = None
        for consolidated in [True, False]:
            try:
                raw = scraper.scrape_ticker(ticker, consolidated=consolidated)
                break
            except Exception as e:
                if not consolidated:
                    raise
                logger.warning(f"{ticker}: consolidated failed, trying standalone. Error: {e}")

        if not raw:
            return False

        # Checksum to detect changes
        checksum = hashlib.md5(str(raw).encode()).hexdigest()
        existing_checksum = await _get_latest_checksum(stock["id"])
        if checksum == existing_checksum:
            logger.info(f"{ticker}: no change detected (checksum match), skipping DB write")
            return True

        # Normalise and store each statement type
        await _store_pl(stock["id"], raw.get("profit_and_loss", {}), checksum)
        await _store_bs(stock["id"], raw.get("balance_sheet",   {}), checksum)
        await _store_cf(stock["id"], raw.get("cash_flow",        {}), checksum)
        await _store_shareholding(stock["id"], raw.get("shareholding_pattern", {}))

        logger.info(f"{ticker}: stored successfully")
        return True

    except Exception as e:
        logger.error(f"{ticker}: scrape failed — {e}")
        await _log_pipeline_error("fundamental_scrape", str(e), stock["id"])
        return False


# ─── Per-statement storage ────────────────────────────────────────────────────

async def _store_pl(stock_id: int, raw_pl: dict, checksum: str):
    normalised = normalize_financial_table(raw_pl)
    ok, missing = validate_pl(normalised)
    if not ok:
        logger.warning(f"stock_id={stock_id} P&L missing keys: {missing}")
        # Store anyway — partial data is better than no data
        # But alert if REQUIRED fields are missing
        if "revenue" not in normalised["data"] and "net_profit" not in normalised["data"]:
            logger.error(f"stock_id={stock_id} P&L critically incomplete — skipping")
            return

    for i, period_label in enumerate(normalised["periods"]):
        period_end = _parse_period_label(period_label)
        if not period_end:
            continue
        period_data = {k: (v[i] if i < len(v) else None) for k, v in normalised["data"].items()}

        sql = """
            INSERT INTO financial_statements
                (stock_id, statement_type, period_type, period_end, data, raw_data, raw_checksum)
            VALUES ($1, 'PL', 'annual', $2, $3::jsonb, $4::jsonb, $5)
            ON CONFLICT (stock_id, statement_type, period_type, period_end)
            DO UPDATE SET
                data         = EXCLUDED.data,
                raw_data     = EXCLUDED.raw_data,
                raw_checksum = EXCLUDED.raw_checksum,
                scraped_at   = NOW()
        """
        import json
        async with raw_connection() as conn:
            await conn.execute(sql, stock_id, period_end,
                               json.dumps(period_data), json.dumps(raw_pl), checksum)


async def _store_bs(stock_id: int, raw_bs: dict, checksum: str):
    """Store balance sheet — same structure as _store_pl."""
    normalised = normalize_financial_table(raw_bs)
    for i, period_label in enumerate(normalised["periods"]):
        period_end = _parse_period_label(period_label)
        if not period_end:
            continue
        period_data = {k: (v[i] if i < len(v) else None) for k, v in normalised["data"].items()}
        import json
        sql = """
            INSERT INTO financial_statements
                (stock_id, statement_type, period_type, period_end, data, raw_data, raw_checksum)
            VALUES ($1, 'BS', 'annual', $2, $3::jsonb, $4::jsonb, $5)
            ON CONFLICT (stock_id, statement_type, period_type, period_end)
            DO UPDATE SET data=EXCLUDED.data, raw_data=EXCLUDED.raw_data,
                          raw_checksum=EXCLUDED.raw_checksum, scraped_at=NOW()
        """
        async with raw_connection() as conn:
            await conn.execute(sql, stock_id, period_end,
                               json.dumps(period_data), json.dumps(raw_bs), checksum)


async def _store_cf(stock_id: int, raw_cf: dict, checksum: str):
    """Store cash flow — same structure as _store_pl."""
    normalised = normalize_financial_table(raw_cf)
    for i, period_label in enumerate(normalised["periods"]):
        period_end = _parse_period_label(period_label)
        if not period_end:
            continue
        period_data = {k: (v[i] if i < len(v) else None) for k, v in normalised["data"].items()}
        import json
        sql = """
            INSERT INTO financial_statements
                (stock_id, statement_type, period_type, period_end, data, raw_data, raw_checksum)
            VALUES ($1, 'CF', 'annual', $2, $3::jsonb, $4::jsonb, $5)
            ON CONFLICT (stock_id, statement_type, period_type, period_end)
            DO UPDATE SET data=EXCLUDED.data, raw_data=EXCLUDED.raw_data,
                          raw_checksum=EXCLUDED.raw_checksum, scraped_at=NOW()
        """
        async with raw_connection() as conn:
            await conn.execute(sql, stock_id, period_end,
                               json.dumps(period_data), json.dumps(raw_cf), checksum)


async def _store_shareholding(stock_id: int, raw_sh: dict):
    """Parse and store shareholding records."""
    records = normalize_shareholding(raw_sh)
    if not records:
        return

    sql = """
        INSERT INTO shareholding_pattern
            (stock_id, period_end, promoter_pct, fii_pct, dii_pct, public_pct, pledged_pct)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (stock_id, period_end) DO UPDATE SET
            promoter_pct = EXCLUDED.promoter_pct,
            fii_pct      = EXCLUDED.fii_pct,
            dii_pct      = EXCLUDED.dii_pct,
            public_pct   = EXCLUDED.public_pct,
            pledged_pct  = EXCLUDED.pledged_pct,
            scraped_at   = NOW()
    """
    for rec in records:
        period_end = _parse_period_label(rec["period"])
        if not period_end:
            continue
        async with raw_connection() as conn:
            await conn.execute(sql, stock_id, period_end,
                               rec["promoter_pct"], rec["fii_pct"], rec["dii_pct"],
                               rec["public_pct"],   rec["pledged_pct"])


# ─── DB helpers ───────────────────────────────────────────────────────────────

async def _fetch_stocks_needing_scrape(days_since_last: int = 90) -> list:
    sql = """
        SELECT s.id, s.symbol, s.screener_slug
        FROM stocks s
        WHERE s.is_active = TRUE
          AND s.is_index  = FALSE
          AND (
            NOT EXISTS (
                SELECT 1 FROM financial_statements fs
                WHERE fs.stock_id = s.id
                  AND fs.scraped_at > NOW() - INTERVAL '1 day' * $1
            )
          )
        ORDER BY s.id
    """
    async with raw_connection() as conn:
        rows = await conn.fetch(sql, days_since_last)
        return [dict(r) for r in rows]


async def _fetch_stock_by_symbol(symbol: str) -> dict:
    async with raw_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, symbol, screener_slug FROM stocks WHERE symbol = $1 AND is_active = TRUE",
            symbol.upper()
        )
        return dict(row) if row else None


async def _get_latest_checksum(stock_id: int) -> str | None:
    async with raw_connection() as conn:
        row = await conn.fetchrow(
            "SELECT raw_checksum FROM financial_statements WHERE stock_id=$1 ORDER BY scraped_at DESC LIMIT 1",
            stock_id
        )
        return row["raw_checksum"] if row else None


async def _log_pipeline_error(job_name: str, error: str, stock_id: int):
    sql = """
        INSERT INTO pipeline_audit (job_name, stock_id, status, error_msg, ended_at)
        VALUES ($1, $2, 'FAILED', $3, NOW())
    """
    async with raw_connection() as conn:
        await conn.execute(sql, job_name, stock_id, error)


# ─── Period label parser ──────────────────────────────────────────────────────

def _parse_period_label(label: str) -> date | None:
    """
    Converts screener.in period labels to Python date objects.
    Examples:
      'Mar 2024' → date(2024, 3, 31)
      'Sep 2023' → date(2023, 9, 30)
    """
    MONTHS = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }
    MONTH_ENDS = {1:31, 2:28, 3:31, 4:30, 5:31, 6:30,
                  7:31, 8:31, 9:30, 10:31, 11:30, 12:31}
    parts = str(label).strip().split()
    if len(parts) != 2:
        return None
    month_str, year_str = parts
    month = MONTHS.get(month_str)
    try:
        year = int(year_str)
    except ValueError:
        return None
    if not month or not (2000 <= year <= 2030):
        return None
    day = MONTH_ENDS[month]
    # Handle leap year for February
    if month == 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        day = 29
    return date(year, month, day)
