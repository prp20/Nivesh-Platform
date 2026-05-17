"""
pipeline/fundamental_scraper.py — Screener.in HTML scraper for financial statements.

Public interface (called by app/routers/pipeline.py):
    run_fundamental_scrape_all(days_since_last=90)  — scrape stocks not updated in N days
    run_fundamental_scrape_one(symbol, force=False)  — scrape a single stock

Strategy:
    - HTTP GET screener.in/company/<screener_slug>/consolidated/
    - Parse HTML tables with BeautifulSoup
    - Checksum-based dedup: skip if raw_checksum unchanged (upsert_financial_statement)
    - Rate limit: 3s delay per stock, 30s pause every 10 stocks
    - Uses httpx (async) for HTTP requests

Tables scraped per stock:
    - Profit & Loss (PL)  → statement_type='PL'
    - Balance Sheet (BS)  → statement_type='BS'
    - Cash Flow (CF)      → statement_type='CF'
    - Shareholding Pattern → shareholding_pattern table
"""

import asyncio
import hashlib
import json
import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, func as sa_func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Stock, FinancialStatement
from app.crud import (
    get_active_stocks,
    upsert_financial_statement,
    upsert_shareholding,
    start_etl_run,
    finish_etl_run,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.screener.in/company/{slug}/consolidated/"
_REQUEST_DELAY_S = 3.0
_BATCH_PAUSE_S = 30.0
_BATCH_SIZE = 10


# ── Public interface ─────────────────────────────────────────────────────────


async def run_fundamental_scrape_all(days_since_last: int = 90) -> dict:
    """
    Scrape financial statements for all stocks not updated in `days_since_last` days.
    """
    async with AsyncSessionLocal() as db:
        run, created = await start_etl_run(
            db, pipeline_name="screener_fundamentals", triggered_by="scheduler"
        )
        if not created:
            logger.warning("[screener_fundamentals] already RUNNING — skipping")
            return {"skipped": True}

        try:
            cutoff = date.today() - timedelta(days=days_since_last)
            stocks_to_scrape = await _get_stocks_needing_scrape(db, cutoff)

            succeeded = 0
            failed = 0
            for i, stock in enumerate(stocks_to_scrape):
                try:
                    changed = await _scrape_stock(db, stock)
                    if changed:
                        succeeded += 1
                except Exception as exc:
                    logger.warning(f"[screener] {stock.symbol} failed — {exc}")
                    failed += 1

                await asyncio.sleep(_REQUEST_DELAY_S)
                if (i + 1) % _BATCH_SIZE == 0:
                    logger.info(f"[screener] processed {i + 1}/{len(stocks_to_scrape)}, pausing {_BATCH_PAUSE_S}s")
                    await asyncio.sleep(_BATCH_PAUSE_S)

            status = "COMPLETED" if failed == 0 else "PARTIAL"
            await finish_etl_run(
                db, run.id, status,
                records_out=succeeded,
                error_msg=f"{failed} stocks failed" if failed else None,
            )
            return {"scraped": len(stocks_to_scrape), "changed": succeeded, "failed": failed}

        except Exception as exc:
            logger.exception("[screener_fundamentals] pipeline-level failure")
            await finish_etl_run(db, run.id, "FAILED", error_msg=str(exc)[:1000])
            raise


async def run_fundamental_scrape_one(symbol: str, force: bool = False) -> dict:
    """
    Scrape a single stock by symbol.  force=True bypasses checksum dedup.

    Uses stock.screener_slug when set; falls back to the NSE symbol, which
    is the correct screener.in slug for the vast majority of listed stocks.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Stock).where(Stock.symbol == symbol, Stock.is_active.is_(True))
        )
        stock = result.scalar_one_or_none()
        if stock is None:
            raise ValueError(f"Active stock not found: {symbol}")

        changed = await _scrape_stock(db, stock, force=force)
        return {"symbol": symbol, "changed": changed}


# ── Core scraping logic ───────────────────────────────────────────────────────


async def _get_stocks_needing_scrape(db: AsyncSession, cutoff: date) -> list:
    """Return stocks whose latest financial_statement scraped_at < cutoff."""
    # Subquery: latest scraped_at per stock
    from sqlalchemy import text

    latest_scrape = await db.execute(
        select(
            FinancialStatement.stock_id,
            sa_func.max(FinancialStatement.scraped_at).label("latest"),
        ).group_by(FinancialStatement.stock_id)
    )
    recently_scraped = {
        row.stock_id
        for row in latest_scrape
        if row.latest and row.latest.date() >= cutoff
    }

    all_stocks = await get_active_stocks(db, is_index=False)
    # Include all active stocks — screener_slug falls back to symbol in _scrape_stock
    return [s for s in all_stocks if s.id not in recently_scraped]


async def _scrape_stock(db: AsyncSession, stock, force: bool = False) -> bool:
    """
    Fetch and parse screener.in HTML for one stock.

    Returns True if any statement was inserted/updated.
    """
    slug = (stock.screener_slug or stock.symbol).removesuffix(".NS")
    url = _BASE_URL.format(slug=slug)

    html = await asyncio.to_thread(_fetch_html, url)
    if html is None:
        logger.warning("[screener] %s — HTML fetch returned None for %s", stock.symbol, url)
        return False

    parsed = await asyncio.to_thread(_parse_screener_html, html, stock.id)
    if not parsed:
        logger.warning("[screener] %s — HTML parsed but returned empty result", stock.symbol)
        return False

    stmts = parsed.get("statements", [])
    sh_rows = parsed.get("shareholding", [])
    logger.info(
        "[screener] %s — parsed %d statement rows, %d shareholding rows from %s",
        stock.symbol, len(stmts), len(sh_rows), url,
    )
    # Log which statement types were found and the first few keys of each
    for s in stmts:
        keys = sorted(s.get("data", {}).keys())
        logger.info(
            "[screener] %s %s %s — %d keys: %s",
            stock.symbol, s["statement_type"], s.get("period_end"), len(keys),
            keys[:10],
        )

    any_changed = False

    # Upsert financial statements
    for stmt_row in stmts:
        if force:
            stmt_row = {**stmt_row, "raw_checksum": None}  # force re-upsert
        changed = await upsert_financial_statement(db, stmt_row)
        any_changed = any_changed or changed

    # Upsert shareholding pattern
    for sh_row in parsed.get("shareholding", []):
        await upsert_shareholding(db, sh_row)
        any_changed = True

    return any_changed


# ── HTTP fetch ────────────────────────────────────────────────────────────────


def _fetch_html(url: str) -> Optional[str]:
    """Blocking HTTP GET — run inside asyncio.to_thread()."""
    import httpx

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NiveshBot/1.0; research)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        response = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
        if response.status_code == 200:
            return response.text
        logger.warning(f"[screener] HTTP {response.status_code} for {url}")
        return None
    except Exception as exc:
        logger.warning(f"[screener] fetch error for {url}: {exc}")
        return None


# ── HTML parsing ──────────────────────────────────────────────────────────────


def _parse_screener_html(html: str, stock_id: int) -> dict:
    """
    Parse screener.in consolidated page HTML.

    Returns:
        {
          "statements": [list of financial_statement dicts],
          "shareholding": [list of shareholding_pattern dicts],
        }
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    statements = []
    shareholding = []

    # Map screener section IDs to statement types
    section_map = {
        "profit-loss":    "PL",
        "balance-sheet":  "BS",
        "cash-flow":      "CF",
    }

    for section_id, stmt_type in section_map.items():
        section = soup.find("section", {"id": section_id})
        if section is None:
            continue
        table = section.find("table", {"class": "data-table"})
        if table is None:
            continue

        rows_data, periods = _parse_data_table(table)
        for period_str, data_row in zip(periods, _transpose(rows_data, periods)):
            period_end = _parse_period(period_str)
            if period_end is None:
                continue
            raw_str = json.dumps(data_row, sort_keys=True)
            checksum = hashlib.sha256(raw_str.encode()).hexdigest()
            statements.append(
                {
                    "stock_id":       stock_id,
                    "statement_type": stmt_type,
                    "period_type":    "annual",
                    "period_end":     period_end,
                    "currency":       "INR",
                    "data":           data_row,
                    "raw_data":       data_row,
                    "raw_checksum":   checksum,
                }
            )

    # Shareholding pattern section
    sh_section = soup.find("section", {"id": "shareholding"})
    if sh_section:
        table = sh_section.find("table", {"class": "data-table"})
        if table:
            rows_data, periods = _parse_data_table(table)
            sh_by_period = _extract_shareholding(rows_data, periods, stock_id)
            shareholding.extend(sh_by_period)

    return {"statements": statements, "shareholding": shareholding}


def _parse_data_table(table) -> tuple:
    """
    Parse a screener.in data-table.

    Returns:
        rows_data: list of {"label": str, "values": [str, ...]}
        periods:   list of period header strings (e.g. "Mar 2023")
    """
    header_row = table.find("thead")
    periods = []
    if header_row:
        for th in header_row.find_all("th")[1:]:
            periods.append(th.get_text(strip=True))

    rows_data = []
    tbody = table.find("tbody")
    if tbody:
        for tr in tbody.find_all("tr"):
            cols = tr.find_all("td")
            if not cols:
                continue
            label = cols[0].get_text(strip=True).rstrip("+").strip()
            values = [c.get_text(strip=True).replace(",", "") for c in cols[1:]]
            rows_data.append({"label": label, "values": values})

    return rows_data, periods


def _transpose(rows_data: list, periods: list) -> list:
    """
    Convert rows_data list into a list of per-period dicts.

    Returns list of dicts, one per period.
    """
    result = [{} for _ in periods]
    for row in rows_data:
        label = row["label"]
        for i, val in enumerate(row["values"]):
            if i < len(result):
                result[i][label] = _safe_float(val)
    return result


def _extract_shareholding(rows_data: list, periods: list, stock_id: int) -> list:
    """Extract shareholding_pattern rows from parsed data table rows."""
    label_map = {
        "Promoters":   "promoter_pct",
        "FIIs":        "fii_pct",
        "DIIs":        "dii_pct",
        "Public":      "public_pct",
        "Pledged %":   "pledged_pct",
    }

    per_period = [{} for _ in periods]
    for row in rows_data:
        col_name = label_map.get(row["label"])
        if col_name:
            for i, val in enumerate(row["values"]):
                if i < len(per_period):
                    per_period[i][col_name] = _safe_float(val)

    results = []
    for i, period_str in enumerate(periods):
        period_end = _parse_period(period_str)
        if period_end is None:
            continue
        d = per_period[i]
        if not d:
            continue
        results.append(
            {
                "stock_id":        stock_id,
                "period_end":      period_end,
                "promoter_pct":    d.get("promoter_pct"),
                "fii_pct":         d.get("fii_pct"),
                "dii_pct":         d.get("dii_pct"),
                "public_pct":      d.get("public_pct"),
                "pledged_pct":     d.get("pledged_pct"),
                "promoter_change": None,
                "fii_change":      None,
            }
        )
    return results


def _parse_period(period_str: str) -> Optional[date]:
    """
    Parse screener.in period strings like 'Mar 2023', 'Sep 2023' to date.

    Returns the last day of the given month.
    """
    import calendar

    MONTH_MAP = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
        "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
    }
    parts = period_str.strip().split()
    if len(parts) != 2:
        return None
    month_str, year_str = parts
    month = MONTH_MAP.get(month_str)
    if month is None:
        return None
    try:
        year = int(year_str)
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, last_day)
    except ValueError:
        return None


def _safe_float(val: str) -> Optional[float]:
    """Convert a screener.in cell value to float.

    Handles:
      '1,234.56'   → 1234.56
      '(1,234)'    → -1234.0   (Indian accounting: parentheses = negative)
      '12.3%'      → 12.3
      '-', '—', '' → None
      'N/A', 'NM'  → None      (Not Meaningful — common in bank EBITDA rows)
    """
    if not val or val in ("-", "—", ""):
        return None
    val = str(val).strip()
    if val.lower() in ("n/a", "na", "nil", "nm", "n.m."):
        return None
    # Indian accounting convention: parentheses denote negative values
    is_negative = val.startswith("(") and val.endswith(")")
    if is_negative:
        val = val[1:-1].strip()
    val = val.replace(",", "").replace("%", "").strip()
    try:
        result = float(val)
        return -result if is_negative else result
    except ValueError:
        return None
