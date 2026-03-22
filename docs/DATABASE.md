# Database Schema & Time-Series Design

Nivesh Elite uses **PostgreSQL** with the **TimescaleDB** extension to effectively manage master data and millions of NAV history points.

## 🐘 Relational Schema

### 💎 Master Data
- `fund_master`: Stores AMFI codes, scheme names, categories, and fund house details.
- `benchmark_master`: Maps market indices (e.g., NIFTY 50) to their respective exchange tickers.

### 📈 Computed Metrics
- `fund_metrics`: Stores daily snapshots of Sharpe, Sortino, and volatility metrics to avoid redundant heavy calculations.

---

## ⚡ Time-Series (TimescaleDB)
Historical values are stored in **Hypertables**, which automatically partition data by time segments (chunks) for optimized indexing and retrieval.

### `fund_nav_history`
- **Primary Keys**: `(scheme_code, nav_date)`
- **Partitioning**: Optimized for range queries over `nav_date`.

### `benchmark_nav_history`
- **Primary Keys**: `(benchmark_code, nav_date)`

---

## 🔄 Sync Tracking
- `sync_jobs`: Tracks the lifecycle of background data fetches. This prevents overlapping syncs for the same asset and provides real-time feedback to the UI.

---

## 🛠️ Migrations
We currently use a script-based migration for simplicity:
1. `seed_benchmarks.py`: Populates core market indices.
2. `migrate_data.py`: Imports legacy mutual fund metadata.
