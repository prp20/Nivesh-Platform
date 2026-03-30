# Database Schema & Time-Series Design

Nivesh Elite uses **PostgreSQL** with the **TimescaleDB** extension to effectively manage master data and millions of NAV history points.

## 🐘 Relational Schema

### 💎 Master Data
- `fund_master`: Stores AMFI codes, scheme names, categories, ISIN, and fund house details.
- `benchmark_master`: Maps market indices (e.g., NIFTY 50) to their respective exchange tickers.

### 📈 Computed Metrics
- `fund_metrics`: Stores daily risk/return metrics:
    - **Performance**: 1Y/3Y/5Y/10Y absolute returns, 3Y/5Y rolling returns, 6M short-term return.
    - **Risk**: Sharpe, Sortino, Std Dev, Max Drawdown.
    - **Relative**: Alpha, Beta, Tracking Error, Information Ratio.
    - **Capture**: Upside/Downside capture ratios.
    - **Metadata**: Data completeness percentage and calculation period.

### 📑 Other Data
- `fund_expense_ratio`: Stores historical Total Expense Ratio (TER) data for funds.

---

## ⚡ Time-Series (TimescaleDB)
Historical values are stored in **Hypertables**, partitioned by `nav_date`.

### `fund_nav_history`
- **Primary Keys**: `(scheme_code, nav_date)`

### `benchmark_nav_history`
- **Primary Keys**: `(benchmark_code, nav_date)`

---

## 🔄 Sync Tracking
- `sync_jobs`: Manages asynchronous data fetches.
    - **Statuses**: `RUNNING`, `COMPLETED`, `FAILED`.
    - **Concurrency**: Prevent overlapping jobs for the same `scheme_code` using a partial unique index.

---

## 🛠️ Migrations
We currently use a script-based migration for simplicity:
1. `seed_benchmarks.py`: Populates core market indices.
2. `migrate_data.py`: Imports legacy mutual fund metadata.
