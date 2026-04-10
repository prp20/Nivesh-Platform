# Phase 3 — Fundamental Pipeline & Normalizer
> **Duration:** Weeks 5–7  
> **Goal:** Wrap the existing ScreenerScraper, parse Indian-formatted financial data, store normalised statements and shareholding in the DB, expose via API.

---

## Prerequisites
- Phase 1 & 2 complete
- `fundamental_data_extractor.py` in the repo root — **do not modify it**
- `BHARTIARTL.json` available for fixture testing

---

## 3.1 The Normalizer — Most Critical Module

The existing `ScreenerScraper` returns raw strings like `'87,939'` and `'(12,345)'`. Every downstream module (ratios, ratings) depends on correct parsing. **Test this thoroughly before connecting to the DB.**

Create `backend/pipeline/normalizer.py`:

```python
# backend/pipeline/normalizer.py
"""
Converts ScreenerScraper raw output into typed Python dicts.

Input (from ScreenerScraper):
  {
    "headers": ["", "Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
    "rows": [
      {"": "Revenue", "Mar 2020": "87,939", "Mar 2021": "100,616", ...},
      {"": "Net Profit", "Mar 2020": "(1,234)", ...},
      ...
    ]
  }

Output:
  {
    "periods": ["Mar 2020", "Mar 2021", "Mar 2022", "Mar 2023", "Mar 2024"],
    "data": {
      "revenue":    [87939.0, 100616.0, ...],
      "net_profit": [-1234.0, ...],
    }
  }
"""

import re
from typing import Optional


# ─── Core number parser ───────────────────────────────────────────────────────

def parse_indian_number(value: str) -> Optional[float]:
    """
    Parse an Indian-formatted number string to float.

    Handles:
      '87,939'      →  87939.0
      '(12,345)'    → -12345.0   (parenthesis = negative in Indian accounting)
      '12.34%'      →  12.34     (strips % sign)
      '1,23,456'    →  123456.0  (lakh format)
      ''            →  None
      '--'          →  None
      '-'           →  None
      'N/A'         →  None
      '0'           →  0.0
    """
    if value is None:
        return None

    value = str(value).strip()

    if value in ("", "-", "--", "N/A", "NA", "n/a", "nil", "Nil"):
        return None

    # Strip percentage sign — caller decides whether to store as-is or /100
    if value.endswith("%"):
        value = value[:-1].strip()

    # Detect and remove parentheses (negative)
    is_negative = value.startswith("(") and value.endswith(")")
    if is_negative:
        value = value[1:-1].strip()

    # Remove all commas (handles both 1,23,456 and 1,234,567 formats)
    value = value.replace(",", "")

    try:
        result = float(value)
        return -result if is_negative else result
    except ValueError:
        return None


# ─── Table normalizer ─────────────────────────────────────────────────────────

def normalize_financial_table(raw: dict, label_col: str = "") -> dict:
    """
    Normalise one statement table from ScreenerScraper output.

    Args:
        raw:       The dict from scraper e.g. raw['profit_and_loss']
        label_col: The column key used as row labels. Default is "" (empty string).

    Returns:
        {
          "periods": ["Mar 2020", "Mar 2021", ...],
          "data":    {"revenue": [87939.0, None, ...], "net_profit": [...], ...}
        }
    """
    if not raw or "headers" not in raw or "rows" not in raw:
        return {"periods": [], "data": {}}

    headers = raw["headers"]
    # periods = all header values that are not the label column
    periods = [h for h in headers if h and h != label_col]

    result = {"periods": periods, "data": {}}

    for row in raw.get("rows", []):
        # Get the row label
        label = str(row.get(label_col, row.get("", ""))).strip()
        if not label:
            continue

        key = _slugify(label)
        values = [parse_indian_number(str(row.get(p, ""))) for p in periods]
        result["data"][key] = values

    return result


def normalize_shareholding(raw: dict) -> list:
    """
    Parse shareholding_pattern output from ScreenerScraper.

    The scraper returns: {"tables": [{"headers": [...], "rows": [...]}]}
    Returns a list of dicts, one per period:
      [{"period": "Sep 2023", "promoter_pct": 68.1, "fii_pct": 14.2, ...}, ...]
    """
    if not raw or "tables" not in raw:
        return []

    records = []
    for table in raw["tables"]:
        headers = table.get("headers", [])
        if not headers:
            continue

        # First column is the category label (Promoters, FIIs, DIIs, Public)
        periods = [h for h in headers if h and h != headers[0]]

        # Build a dict: {category_slug: [values per period]}
        categories = {}
        for row in table.get("rows", []):
            label = str(row.get(headers[0], "")).strip()
            if not label:
                continue
            key = _slugify(label)
            values = [parse_indian_number(str(row.get(p, ""))) for p in periods]
            categories[key] = values

        # One record per period
        for i, period in enumerate(periods):
            records.append({
                "period":        period,
                "promoter_pct":  _pick(categories, ["promoters", "promoter_promoter_group"], i),
                "fii_pct":       _pick(categories, ["foreign_institutional_investors", "fiis", "foreign_portfolio_investors"], i),
                "dii_pct":       _pick(categories, ["domestic_institutional_investors", "diis"], i),
                "public_pct":    _pick(categories, ["public", "public_non_institutional"], i),
                "pledged_pct":   _pick(categories, ["pledged_shares", "promoters_pledge"], i),
            })

    return records


# ─── Validation ───────────────────────────────────────────────────────────────

REQUIRED_PL_KEYS = {"revenue", "net_profit", "operating_profit"}
REQUIRED_BS_KEYS = {"total_assets", "borrowings"}
REQUIRED_CF_KEYS = {"cash_from_operating_activity"}

def validate_pl(data: dict) -> tuple[bool, set]:
    missing = REQUIRED_PL_KEYS - set(data.get("data", {}).keys())
    return len(missing) == 0, missing

def validate_bs(data: dict) -> tuple[bool, set]:
    missing = REQUIRED_BS_KEYS - set(data.get("data", {}).keys())
    return len(missing) == 0, missing


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """'Net Profit' → 'net_profit', 'EBITDA (%)' → 'ebitda'"""
    text = re.sub(r"[^\w\s]", "", text.lower())      # remove punctuation
    text = re.sub(r"\s+", "_", text.strip())         # spaces to underscores
    text = re.sub(r"_+", "_", text).strip("_")       # collapse multiple underscores
    return text

def _pick(categories: dict, keys: list, index: int) -> Optional[float]:
    """Try multiple possible key names for a category."""
    for key in keys:
        vals = categories.get(key)
        if vals is not None and index < len(vals):
            return vals[index]
    return None
```

### Normalizer Unit Tests

Create `backend/tests/test_normalizer.py`:

```python
# backend/tests/test_normalizer.py
import pytest
from pipeline.normalizer import parse_indian_number, normalize_financial_table

class TestParseIndianNumber:
    def test_plain_number(self):       assert parse_indian_number("87939")    == 87939.0
    def test_comma_separated(self):    assert parse_indian_number("87,939")   == 87939.0
    def test_lakh_format(self):        assert parse_indian_number("1,23,456") == 123456.0
    def test_negative_parens(self):    assert parse_indian_number("(12,345)") == -12345.0
    def test_percentage(self):         assert parse_indian_number("12.34%")   == 12.34
    def test_empty_string(self):       assert parse_indian_number("")         is None
    def test_dash(self):               assert parse_indian_number("-")        is None
    def test_double_dash(self):        assert parse_indian_number("--")       is None
    def test_na(self):                 assert parse_indian_number("N/A")      is None
    def test_zero(self):               assert parse_indian_number("0")        == 0.0
    def test_decimal(self):            assert parse_indian_number("1,234.56") == 1234.56
    def test_negative_decimal_paren(self): assert parse_indian_number("(1,234.56)") == -1234.56

class TestNormalizeTable:
    def test_basic_pl_table(self):
        raw = {
            "headers": ["", "Mar 2023", "Mar 2024"],
            "rows": [
                {"": "Revenue", "Mar 2023": "87,939", "Mar 2024": "1,00,616"},
                {"": "Net Profit", "Mar 2023": "(1,234)", "Mar 2024": "5,678"},
            ]
        }
        result = normalize_financial_table(raw)
        assert result["periods"] == ["Mar 2023", "Mar 2024"]
        assert result["data"]["revenue"]    == [87939.0, 100616.0]
        assert result["data"]["net_profit"] == [-1234.0, 5678.0]

    def test_empty_raw(self):
        assert normalize_financial_table({}) == {"periods": [], "data": {}}

    def test_bhartiartl_fixture(self):
        """Validate against real scraper output."""
        import json, os
        fixture = os.path.join(os.path.dirname(__file__), "../../BHARTIARTL.json")
        if not os.path.exists(fixture):
            pytest.skip("BHARTIARTL.json not found")
        with open(fixture) as f:
            data = json.load(f)
        result = normalize_financial_table(data["profit_and_loss"])
        assert len(result["periods"]) >= 4
        assert "revenue" in result["data"]
        # Revenue should be large positive numbers (Airtel revenue is 87,939 Cr+)
        assert all(v is None or v > 0 for v in result["data"]["revenue"])
```

Run before connecting to DB: `pytest backend/tests/test_normalizer.py -v`

---

## 3.2 Fundamental Scraping Pipeline

Create `backend/pipeline/fundamental_scraper.py`:

```python
# backend/pipeline/fundamental_scraper.py
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

# Import the EXISTING scraper — do not modify that file
sys.path.insert(0, ".")
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
```

---

## 3.3 Enable Fundamental Jobs in Scheduler

```python
# In pipeline/scheduler.py — uncomment:
from pipeline.fundamental_scraper import run_fundamental_scrape_all

scheduler.add_job(
    run_fundamental_scrape_all,
    CronTrigger(day_of_week="sun", hour=2, minute=0),
    max_instances=1,
    id="fundamental_scrape"
)
```

---

## 3.4 API Endpoints — Fundamentals & Shareholding

Add to `backend/app/routers/stocks.py`:

```python
# Append to existing stocks.py

@router.get("/stocks/{symbol}/fundamentals")
async def get_fundamentals(
    symbol:         str,
    statement_type: str = Query("PL", regex="^(PL|BS|CF)$"),
    period_type:    str = Query("annual", regex="^(annual|quarterly)$"),
    limit:          int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    stock = await _get_stock_id(symbol, db)
    if not stock:
        raise HTTPException(404, f"Stock '{symbol}' not found")

    sql = """
        SELECT period_end, period_type, data, scraped_at
        FROM financial_statements
        WHERE stock_id      = :sid
          AND statement_type = :st
          AND period_type    = :pt
        ORDER BY period_end DESC
        LIMIT :limit
    """
    result = await db.execute(text(sql), {
        "sid": stock["id"], "st": statement_type, "pt": period_type, "limit": limit
    })
    rows = [dict(r._mapping) for r in result.fetchall()]
    return {"symbol": symbol.upper(), "statement_type": statement_type, "records": rows}


@router.get("/stocks/{symbol}/shareholding")
async def get_shareholding(
    symbol: str,
    limit:  int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    stock = await _get_stock_id(symbol, db)
    if not stock:
        raise HTTPException(404, f"Stock '{symbol}' not found")

    sql = """
        SELECT period_end, promoter_pct, fii_pct, dii_pct, public_pct, pledged_pct,
               promoter_change, fii_change
        FROM shareholding_pattern
        WHERE stock_id = :sid
        ORDER BY period_end DESC
        LIMIT :limit
    """
    result = await db.execute(text(sql), {"sid": stock["id"], "limit": limit})
    return {"symbol": symbol.upper(), "records": [dict(r._mapping) for r in result.fetchall()]}
```

---

## 3.5 Frontend — Fundamentals Tab in StockDetail

Implement `frontend/src/pages/StockDetail.jsx` with tabs:

```jsx
// frontend/src/pages/StockDetail.jsx (skeleton — expand in later phases)
import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { fetchStockDetail } from "../store/slices/stocksSlice";
import stockService from "../api/stockService";

export default function StockDetail({ symbol }) {
  const dispatch = useDispatch();
  const { detail, status } = useSelector(s => s.stocks);
  const [activeTab, setActiveTab] = useState("overview");
  const [fundamentals, setFundamentals] = useState(null);
  const [stmtType, setStmtType] = useState("PL");

  useEffect(() => {
    if (symbol) dispatch(fetchStockDetail(symbol));
  }, [symbol]);

  useEffect(() => {
    if (symbol && activeTab === "fundamentals") {
      stockService.getFundamentals(symbol, { statement_type: stmtType, limit: 5 })
        .then(setFundamentals);
    }
  }, [symbol, activeTab, stmtType]);

  if (status === "loading" || !detail) return <div className="cal-loading-skeleton" />;

  return (
    <div className="cal-page">
      {/* Header */}
      <div className="cal-stock-header">
        <div>
          <h1 className="cal-heading">{detail.symbol}</h1>
          <p className="cal-subheading">{detail.company_name}</p>
        </div>
        <div className="cal-price-block">
          <span className="cal-price">₹{detail.latest_close?.toFixed(2)}</span>
          <span className={detail.change_pct >= 0 ? "cal-positive" : "cal-negative"}>
            {detail.change_pct > 0 ? "+" : ""}{detail.change_pct?.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="cal-tabs">
        {["overview", "fundamentals", "chart", "analysis"].map(tab => (
          <button
            key={tab}
            className={`cal-tab ${activeTab === tab ? "cal-tab--active" : ""}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "overview"       && <OverviewTab detail={detail} />}
      {activeTab === "fundamentals"   && (
        <FundamentalsTab
          data={fundamentals}
          stmtType={stmtType}
          onStmtChange={setStmtType}
        />
      )}
      {activeTab === "chart"          && <div className="cal-placeholder">Chart — Phase 5</div>}
      {activeTab === "analysis"       && <div className="cal-placeholder">Analysis — Phase 5/6</div>}
    </div>
  );
}

function OverviewTab({ detail }) {
  const ratios = [
    ["P/E Ratio",    detail.pe_ratio?.toFixed(2)],
    ["P/B Ratio",    detail.pb_ratio?.toFixed(2)],
    ["ROE",          detail.roe ? `${detail.roe?.toFixed(1)}%` : null],
    ["Debt/Equity",  detail.debt_equity?.toFixed(2)],
    ["RSI (14)",     detail.rsi_14?.toFixed(1)],
  ];
  return (
    <div className="cal-overview-grid">
      {ratios.map(([label, value]) => (
        <div key={label} className="cal-metric-card">
          <span className="cal-metric-label">{label}</span>
          <span className="cal-metric-value">{value ?? "—"}</span>
        </div>
      ))}
    </div>
  );
}

function FundamentalsTab({ data, stmtType, onStmtChange }) {
  if (!data) return <div className="cal-loading-skeleton" />;

  const labels = { PL: "Profit & Loss", BS: "Balance Sheet", CF: "Cash Flow" };

  return (
    <div>
      <div className="cal-stmt-tabs">
        {["PL", "BS", "CF"].map(t => (
          <button
            key={t}
            className={`cal-chip ${stmtType === t ? "cal-chip--active" : ""}`}
            onClick={() => onStmtChange(t)}
          >{labels[t]}</button>
        ))}
      </div>
      <div className="cal-table-scroll">
        <table className="cal-table cal-table--financial">
          <thead>
            <tr>
              <th>Metric</th>
              {data.records.map(r => (
                <th key={r.period_end}>{r.period_end}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.records[0] && Object.keys(data.records[0].data).map(key => (
              <tr key={key}>
                <td className="cal-metric-label">{key.replace(/_/g, " ")}</td>
                {data.records.map(r => (
                  <td key={r.period_end} className="cal-number">
                    {r.data[key] != null ? r.data[key].toLocaleString("en-IN") : "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

---

## 3.6 Validation Checklist

```bash
# 1. Run normalizer unit tests — ALL must pass before scraping
pytest backend/tests/test_normalizer.py -v

# 2. Test scraper on BHARTIARTL manually
cd backend && python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from fundamental_data_extractor import ScreenerScraper
from pipeline.normalizer import normalize_financial_table
s = ScreenerScraper(delay_seconds=1.5)
raw = s.scrape_ticker('BHARTIARTL', consolidated=True)
pl = normalize_financial_table(raw['profit_and_loss'])
print('Periods:', pl['periods'])
print('Revenue:', pl['data'].get('revenue'))
print('Net Profit:', pl['data'].get('net_profit'))
"

# 3. Manually trigger scrape for one stock
curl -X POST http://localhost:8000/api/v1/admin/pipeline/fundamentals/trigger \
  -H "Authorization: Bearer <token>" \
  -d '{"symbol": "BHARTIARTL"}'

# 4. Verify DB storage
psql -U user -d nivesh -c "
  SELECT statement_type, period_end, data->>'revenue', data->>'net_profit'
  FROM financial_statements
  WHERE stock_id = (SELECT id FROM stocks WHERE symbol = 'BHARTIARTL')
  ORDER BY period_end DESC LIMIT 5;
"

# 5. Test APIs
curl "http://localhost:8000/api/v1/stocks/BHARTIARTL/fundamentals?statement_type=PL" | jq '.records | length'
curl "http://localhost:8000/api/v1/stocks/BHARTIARTL/shareholding" | jq '.records[0]'
```

---

## 3.7 Deliverables for Phase 3

- [ ] `pipeline/normalizer.py` implemented
- [ ] All 12 normalizer unit tests pass
- [ ] `BHARTIARTL.json` fixture validates correctly through normalizer
- [ ] `pipeline/fundamental_scraper.py` implemented
- [ ] `_parse_period_label` tested for `'Mar 2024'`, `'Sep 2023'`, `'Dec 2022'`
- [ ] Partial scrape run for 10–20 stocks — DB rows in `financial_statements`
- [ ] `GET /stocks/{symbol}/fundamentals` returns data for scraped stocks
- [ ] `GET /stocks/{symbol}/shareholding` returns shareholding history
- [ ] `StockDetail.jsx` Fundamentals tab renders P&L, BS, CF tables
- [ ] Full Sunday scrape job scheduled (Sunday 02:00 IST)
- [ ] Checksum deduplication tested — re-running scrape on same stock does not duplicate rows
