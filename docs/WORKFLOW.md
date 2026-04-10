# Development Workflow & Data Migration

This guide outlines the standard procedures for developing and maintaining the Nivesh Elite ecosystem.

## 🛠️ Developer Workflow

### 1. Feature Development
When adding a new financial indicator:
1.  Extend the `analytics` engine logic.
2.  Update the `FundMetrics` SQLAlchemy model if needed.
3.  Add the corresponding field to the `FundMetricsRead` schema.
4.  Expose the new data point in the **MF Detail** page on the frontend.
5.  Update the corresponding Redux slice (e.g., `syncSlice.js`) if the data point involves asynchronous background processing.

### 2. Style Refinement (CALIFINO)
All styling is centralized in `index.css` (tokens) and component-level CSS files. Ensure all colors use the established HSL palette constants for brand consistency.

---

## 🔄 Data Migration & Initialization Procedures

### Initial Setup
After the first launch, follow these steps to populate your local database:
1.  **Initialize DB**: `python scripts/db_init.py` (Creates tables if not using Alembic).
2.  **Seed Benchmarks**: `python scripts/seed_indices.py` (Adds NIFTY 50, MIDCAP 150, etc.).
3.  **Seed Funds**: `python scripts/seed_funds.py` (Populates fund master data).
4.  **Seed Stocks**: `python scripts/seed/seed_stock_master.py` (Initializes stock master data).
5.  **Backfill Data**:
    - For Funds: `python scripts/sync_data.py` (Fetches historical NAVs).
    - For Stocks: `python scripts/seed/backfill_prices.py` (Fetches historical OHLCV).

### Maintaining Data
The platform is designed for automated maintenance:
- **JIT Fetching (MFs)**: Missing data is fetched on-demand via the `/metrics/{code}` trigger.
- **Pipeline Sync (Stocks)**: The `backend/pipeline` module handles scheduled data refreshes for equity symbols.
- **Bulk Setup**: Use `scripts/setup_data.sh` for a one-click initialization of the entire ecosystem.

---

## 🧪 Testing & Verification
- **API Testing**: Use the built-in Swagger UI at `/docs`.
- **Frontend Verification**: Verify UI responsiveness across different viewport sizes using browser dev tools.
- **Data Verification**: Cross-reference computed Sharpe/Sortino ratios against official AMFI/Valueresearch data points for accuracy.
