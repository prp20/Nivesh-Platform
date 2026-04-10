# Stock Data Sync — Step-by-Step Guide

> **Purpose:** This document explains how to sync all stock market data end-to-end —
> from raw OHLCV price data through to technical indicators and financial ratios.
> Follow these steps in order when setting up fresh, after a data gap, or when stock results are published.

---

## Overview: The Data Pipeline

```
Step 1  →  Stock Master Setup           (one-time seed)
Step 2  →  Backfill Price History       (one-time or after new stock added)
Step 3  →  Daily Price & Index Sync     (daily, automated via scheduler)
Step 4  →  Price-Dependent Metrics      (daily, after Step 3)
Step 5  →  Technical Analysis           (daily, after Step 4)
Step 6  →  Screener.in Fundamentals     (quarterly, on-demand or scheduled)
Step 7  →  Financial Ratios             (after Step 6)
Step 8  →  Stock Ratings                (after Steps 5 + 7)
```

---

## Step 1 — Stock Master Setup (One-Time)

**When:** First-time setup, or when adding new stocks.

**What it does:** Populates the `stocks` table with symbol, NSE/BSE codes, yfinance ticker, screener.in slug, sector, and market cap category.

**How:**

```bash
cd backend
source venv/bin/activate

# Seed stocks from the CSV master list
python -m scripts.seed.seed_stocks

# Verify count
python -c "
import asyncio, asyncpg
async def check():
    conn = await asyncpg.connect('postgresql://user:pass@localhost:5432/nivesh')
    count = await conn.fetchval('SELECT COUNT(*) FROM stocks WHERE is_active=TRUE')
    print(f'Active stocks: {count}')
asyncio.run(check())
"
```

**Expected result:** `stocks` table populated with all active equities and indices (`is_index=TRUE` for indices).

---

## Step 2 — Backfill Price History (One-Time / On-Demand)

**When:** Fresh setup, or when a new stock is added to the `stocks` table.

**What it does:** Downloads up to 5 years of OHLCV data from Yahoo Finance for all active stocks and upserts into `price_data`.

**How (via API trigger):**

```bash
# Trigger backfill via API (requires auth token)
curl -X POST http://localhost:8000/api/v1/pipeline/prices/backfill \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json"
```

**How (via script — for initial seeding without API):**

```bash
cd backend
source venv/bin/activate
python -m scripts.seed.backfill_prices --period 5y
```

**Verify:**

```sql
SELECT s.symbol, COUNT(p.price_date) AS days, MIN(p.price_date), MAX(p.price_date)
FROM stocks s
JOIN price_data p ON p.stock_id = s.id
GROUP BY s.symbol
ORDER BY days ASC
LIMIT 20;
```

**Expected result:** Each active stock should have ~1250 rows (5 years × 250 trading days).

---

## Step 3 — Daily Price & Index Sync (Automated / Manual Trigger)

**When:** Every trading day (Mon–Fri). Runs automatically at **18:30 IST** (prices) and **18:40 IST** (indices) via APScheduler.

**What it does:** Fetches the last 5 trading days of OHLCV data for all active stocks and indices from Yahoo Finance. Uses `ON CONFLICT DO UPDATE` so re-running is safe.

### Trigger Manually (for catch-up or debugging)

```bash
# Trigger price ingestion for all stocks (background task)
curl -X POST http://localhost:8000/api/v1/pipeline/prices/all \
  -H "Authorization: Bearer <YOUR_TOKEN>"

# Trigger index ingestion separately
curl -X POST http://localhost:8000/api/v1/pipeline/prices/indices \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

**Response:**
```json
{
  "message": "Price ingestion started in background",
  "job_id": 42
}
```

**Verify:**

```sql
-- Check latest price date for each stock
SELECT s.symbol, MAX(p.price_date) AS latest_date
FROM stocks s
LEFT JOIN price_data p ON p.stock_id = s.id
WHERE s.is_active = TRUE AND s.is_index = FALSE
GROUP BY s.symbol
ORDER BY latest_date ASC
LIMIT 10;  -- Stocks with oldest data appear first
```

**Check pipeline_audit for job status:**

```sql
SELECT job_name, status, started_at, ended_at, records_out, error_msg
FROM pipeline_audit
WHERE job_name IN ('price_daily_ingestion', 'index_daily_ingestion')
ORDER BY started_at DESC
LIMIT 10;
```

---

## Step 4 — Price-Dependent Metrics Recompute (Daily, After Step 3)

**When:** Every trading day at **19:00 IST**, automatically chained after Step 3.

**What it does:** Recomputes only the financial ratios that depend on the current market price:
- **PE Ratio** = `latest_close / EPS`
- **PB Ratio** = `latest_close / Book Value Per Share`
- **PS Ratio** = `(latest_close × shares) / Revenue`
- **Dividend Yield** = `Dividend / latest_close`

These ratios are stored in the `financial_ratios` table alongside the stable quarterly fundamentals.

### Trigger Manually

```bash
# Trigger price-dependent ratio refresh for all stocks
curl -X POST http://localhost:8000/api/v1/pipeline/metrics/price-refresh/all \
  -H "Authorization: Bearer <YOUR_TOKEN>"

# For a single stock
curl -X POST http://localhost:8000/api/v1/pipeline/metrics/price-refresh/RELIANCE \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

**Verify:**

```sql
SELECT s.symbol, fr.pe_ratio, fr.pb_ratio, fr.ps_ratio, fr.computed_at
FROM financial_ratios fr
JOIN stocks s ON s.id = fr.stock_id
WHERE fr.period_type = 'annual'
ORDER BY fr.computed_at DESC
LIMIT 10;
```

---

## Step 5 — Technical Analysis Computation (Daily, After Step 4)

**When:** Every trading day at **19:30 IST**, automatically after price ingestion.

**What it does:** Reads `price_data` for each stock and computes the full set of technical indicators using `ta-lib`:

| Indicator | Column in DB |
|---|---|
| Simple Moving Averages | `sma_20`, `sma_50`, `sma_200` |
| Exponential Moving Averages | `ema_9`, `ema_21`, `ema_50` |
| Relative Strength Index | `rsi_14` |
| MACD | `macd_line`, `macd_signal`, `macd_hist` |
| Bollinger Bands | `bb_upper`, `bb_middle`, `bb_lower` |
| Average True Range | `atr_14` |
| Average Directional Index | `adx_14` |
| Stochastic Oscillator | `stoch_k`, `stoch_d` |
| Volume SMA | `volume_sma_20` |

Results are stored in `technical_indicators` table keyed by `(stock_id, ind_date, timeframe)`.

### Trigger Manually

```bash
# Trigger TA for all stocks (background task)
curl -X POST http://localhost:8000/api/v1/pipeline/technical/all \
  -H "Authorization: Bearer <YOUR_TOKEN>"

# Trigger TA for a single stock (synchronous, returns results)
curl -X POST http://localhost:8000/api/v1/pipeline/technical/RELIANCE \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

**Response for single stock:**
```json
{
  "symbol": "RELIANCE",
  "computed_on": "2026-04-09",
  "indicators": {
    "sma_20": 1342.50,
    "sma_50": 1298.30,
    "sma_200": 1198.75,
    "rsi_14": 62.5,
    "macd_line": 14.2,
    "macd_signal": 11.8,
    "macd_hist": 2.4
  }
}
```

**Check status of TA computation:**

```bash
curl http://localhost:8000/api/v1/pipeline/technical/status \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

**Verify in DB:**

```sql
SELECT s.symbol, ti.ind_date, ti.rsi_14, ti.sma_50, ti.sma_200, ti.macd_hist
FROM technical_indicators ti
JOIN stocks s ON s.id = ti.stock_id
WHERE ti.timeframe = '1d'
ORDER BY ti.ind_date DESC, s.symbol
LIMIT 20;
```

---

## Step 6 — Screener.in Fundamental Data Sync (Quarterly / On-Demand)

**When:** Quarterly (after Q1/Q2/Q3/Q4 results season). Runs automatically every **Sunday at 02:00 IST**, scraping stocks not updated in 90+ days.

**What it does:** 
- Scrapes screener.in for each stock's P&L, Balance Sheet, Cash Flow, and Shareholding Pattern.
- Uses checksum deduplication — skips stocks with no change in data.
- Stores raw + normalized data in `financial_statements` and `shareholding_pattern` tables.

### Trigger Manually — All Stocks

```bash
# Trigger scrape for all overdue stocks (> 90 days since last scrape)
curl -X POST http://localhost:8000/api/v1/pipeline/screener/all \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

> ⚠️ **This is a slow operation.** With 2.5s delays between stocks, 500 stocks = ~20 minutes.

### Trigger Manually — Single Stock

```bash
# Trigger immediate scrape for a specific stock
curl -X POST http://localhost:8000/api/v1/pipeline/screener/RELIANCE \
  -H "Authorization: Bearer <YOUR_TOKEN>"

# Force re-scrape even if data hasn't changed (bypass checksum check)
curl -X POST "http://localhost:8000/api/v1/pipeline/screener/RELIANCE?force=true" \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

**Check which stocks are overdue for scraping:**

```bash
curl http://localhost:8000/api/v1/pipeline/screener/status \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

**Verify in DB:**

```sql
-- Check last scrape date per stock
SELECT s.symbol, MAX(fs.scraped_at) AS last_scraped
FROM stocks s
LEFT JOIN financial_statements fs ON fs.stock_id = s.id
WHERE s.is_active = TRUE AND s.is_index = FALSE
GROUP BY s.symbol
ORDER BY last_scraped ASC NULLS FIRST
LIMIT 20;
```

---

## Step 7 — Financial Ratio Computation (After Screener Scrape)

**When:** Every **Sunday at 09:00 IST**, automatically after the screener scrape (Step 6). Also triggered automatically after a manual single-stock screener sync (Step 6).

**What it does:** Reads from `financial_statements` and computes all fundamental ratios:
- ROE, ROCE, ROA
- PAT Margin, EBITDA Margin
- Debt/Equity, Interest Coverage, Current Ratio
- Revenue Growth, PAT Growth, EPS Growth
- EPS, Book Value Per Share, CFO-to-PAT

Results are stored in `financial_ratios` with the period date.

### Trigger Manually

```bash
# Recompute ratios for all stocks that have financial statements
curl -X POST http://localhost:8000/api/v1/pipeline/ratios/all \
  -H "Authorization: Bearer <YOUR_TOKEN>"

# Recompute ratios for a single stock
curl -X POST http://localhost:8000/api/v1/pipeline/ratios/RELIANCE \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

**Verify:**

```sql
SELECT s.symbol, fr.pe_ratio, fr.roe, fr.roce, fr.debt_equity, fr.computed_at
FROM financial_ratios fr
JOIN stocks s ON s.id = fr.stock_id
ORDER BY fr.computed_at DESC
LIMIT 20;
```

---

## Step 8 — Stock Rating Computation (After Steps 5 + 7)

**When:** Every trading day at **20:15 IST**, after TA and metric recomputes are done.

**What it does:** Computes a composite score for each stock across 5 dimensions:
- **Fundamental Score** — from ROE, ROCE, D/E, margins (from `financial_ratios`)
- **Valuation Score** — based on PE, PB relative to sector peers
- **Technical Score** — from RSI, MACD, moving average alignment (from `technical_indicators`)
- **Momentum Score** — based on price performance (from `price_data`)
- **Shareholding Score** — from promoter holding, FII trend (from `shareholding_pattern`)

Total score is stored in `stock_ratings` with a `rating_label` (Strong Buy / Buy / Neutral / Sell).

### Trigger Manually

```bash
# Recompute ratings for all stocks
curl -X POST http://localhost:8000/api/v1/pipeline/ratings/all \
  -H "Authorization: Bearer <YOUR_TOKEN>"

# Single stock
curl -X POST http://localhost:8000/api/v1/pipeline/ratings/RELIANCE \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

---

## Full Sync: All Steps in Sequence

> Use this for a complete data refresh after a gap or fresh deployment.

```bash
#!/bin/bash
BASE_URL="http://localhost:8000/api/v1"
TOKEN="Bearer <YOUR_TOKEN>"

echo "Step 2: Backfill price history..."
curl -s -X POST "$BASE_URL/pipeline/prices/backfill" -H "Authorization: $TOKEN"
sleep 5  # Give it time to start

echo "Step 3: Sync latest prices..."
curl -s -X POST "$BASE_URL/pipeline/prices/all" -H "Authorization: $TOKEN"
curl -s -X POST "$BASE_URL/pipeline/prices/indices" -H "Authorization: $TOKEN"
sleep 5

echo "Step 4: Recompute price-dependent metrics..."
curl -s -X POST "$BASE_URL/pipeline/metrics/price-refresh/all" -H "Authorization: $TOKEN"
sleep 3

echo "Step 5: Run technical analysis..."
curl -s -X POST "$BASE_URL/pipeline/technical/all" -H "Authorization: $TOKEN"
sleep 3

echo "Step 6: Scrape screener.in fundamentals (slow)..."
curl -s -X POST "$BASE_URL/pipeline/screener/all" -H "Authorization: $TOKEN"
# Note: This takes 20-40 minutes for all stocks

echo "Step 7: Compute financial ratios..."
curl -s -X POST "$BASE_URL/pipeline/ratios/all" -H "Authorization: $TOKEN"
sleep 3

echo "Step 8: Compute stock ratings..."
curl -s -X POST "$BASE_URL/pipeline/ratings/all" -H "Authorization: $TOKEN"

echo "Done. Check pipeline_audit table for status."
```

---

## Checking Pipeline Health

```sql
-- View all recent pipeline job runs and their status
SELECT job_name, status, started_at, ended_at,
       EXTRACT(EPOCH FROM (ended_at - started_at))::int AS duration_sec,
       records_out, error_msg
FROM pipeline_audit
ORDER BY started_at DESC
LIMIT 50;

-- Check for any FAILED jobs
SELECT job_name, status, error_msg, started_at
FROM pipeline_audit
WHERE status = 'FAILED'
ORDER BY started_at DESC
LIMIT 20;

-- Check stocks with no price data (potential data gap)
SELECT s.symbol, s.company_name
FROM stocks s
WHERE s.is_active = TRUE AND s.is_index = FALSE
  AND NOT EXISTS (
    SELECT 1 FROM price_data p WHERE p.stock_id = s.id
  );

-- Check stocks with no technical indicators
SELECT s.symbol FROM stocks s
WHERE s.is_active = TRUE AND s.is_index = FALSE
  AND NOT EXISTS (
    SELECT 1 FROM technical_indicators ti WHERE ti.stock_id = s.id
  );
```

---

## Automated Schedule Summary

| Time (IST) | Job | What Happens |
|---|---|---|
| Mon–Fri 18:30 | Price Ingestion | Last 5 days OHLCV → `price_data` |
| Mon–Fri 18:40 | Index Ingestion | Last 5 days indices → `price_data` |
| Mon–Fri 19:00 | Price Metric Refresh | PE/PB/PS updated → `financial_ratios` |
| Mon–Fri 19:30 | Technical Analysis | All TA indicators → `technical_indicators` |
| Mon–Fri 20:15 | Rating Compute | Composite score → `stock_ratings` |
| Sunday 02:00 | Screener Scrape | Fundamentals → `financial_statements` |
| Sunday 09:00 | Ratio Compute | ROE/ROCE/etc → `financial_ratios` |

---

## Troubleshooting

### Yahoo Finance Rate Limits
- Symptom: `yfinance download failed for chunk`
- Fix: Reduce `CHUNK_SIZE` in `price_ingestion.py` from 50 to 20, increase sleep between chunks.

### Screener.in 429 / Blocked
- Symptom: `scrape failed` errors in `pipeline_audit`
- Fix: Increase `delay_seconds` in `ScreenerScraper(delay_seconds=5.0)`. Use the `screener_slug` field correctly — some companies need `?consolidated=false`.

### Missing Financial Ratios (NULL PE/PB)
- Symptom: `pe_ratio` is NULL for stocks that have price data
- Cause: `eps` is NULL in `financial_ratios` → no screener data scraped yet
- Fix: Run Step 6 (screener scrape) for that stock, then Step 7 (ratio compute), then Step 4 (price refresh).

### Technical Indicators Not Updating
- Symptom: `rsi_14`, `sma_50` etc. are stale or NULL
- Cause: `technical_analysis_daily` job not running, or insufficient price history
- Fix: Ensure `price_data` has at least 200 rows for the stock (needed for SMA-200). Run Step 2 (backfill) if missing.
