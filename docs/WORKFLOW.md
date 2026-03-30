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

## 🔄 Data Migration Procedures

### Initial Setup
After the first launch, follow these steps to populate your local database:
1.  **Seed Benchmarks**: `python scripts/seed_benchmarks.py` (Adds NIFTY 50, MIDCAP 150, etc.).
2.  **Migrate Master Data**: `python scripts/migrate_data.py` (Imports your legacy fund records).
3.  **Import Equity Data**: `python scripts/import_new_equity.py` (Imports any missing equity funds).
4.  **Populate NAV History**: `python scripts/populate_nav_history.py` (Populates historical NAV for all funds via mftool).
5.  **Import Nifty Indices**: `python scripts/import_nifty_indices.py` (Loads indices from CSV).

### Maintaining Data
The platform is designed to self-maintain via **Initial Sync** and **JIT Fetching**. Manual syncs are only needed if AMFI data is suspected to be outdated or corrupted.

---

## 🧪 Testing & Verification
- **API Testing**: Use the built-in Swagger UI at `/docs`.
- **Frontend Verification**: Verify UI responsiveness across different viewport sizes using browser dev tools.
- **Data Verification**: Cross-reference computed Sharpe/Sortino ratios against official AMFI/Valueresearch data points for accuracy.
