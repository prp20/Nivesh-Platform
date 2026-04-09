# Backend Design & Data Engine

The Nivesh backend is an asynchronous powerhouse designed to handle complex financial analytics and time-series data at scale.

## 🚀 Engine Architecture
The backend is structured into specialized layers to ensure separation of concerns and high performance.

```text
backend/
├── app/
│   ├── routers/    # API endpoint definitions (REST)
│   ├── analytics.py # Core financial calculation engine (MFs)
│   ├── crud.py      # SQLAlchemy database operations
│   ├── sync.py      # JIT data fetching logic (MFs)
│   ├── models.py    # SQLAlchemy model definitions
│   ├── schemas.py   # Pydantic models for validation
│   ├── security.py  # JWT and password hashing
│   ├── database.py  # Engine and session configuration
│   └── main.py      # FastAPI entry point
├── pipeline/       # Equity Data Pipeline (New)
│   ├── price_ingestion.py     # yfinance OHLCV sync
│   ├── fundamental_scraper.py # Screener.in extraction
│   ├── ratio_engine.py       # 17+ Financial ratio calculation
│   ├── normalizer.py         # Indian number parsing & cleaning
│   └── audit.py              # Pipeline job tracking
├── scripts/
│   ├── seed/        # One-time initialization (Benchmarks, Indices)
│   └── ...          # Bulk ETL tasks (NAV history backfills)
```

---

## 📊 Analytics & Ratio Engine
The backend features two distinct analytical cores:

### 1. Mutual Fund Analytics (`app/analytics.py`)
Computes key risk indicators on-the-fly:
- **Sharpe/Sortino**: Risk-adjusted returns.
- **Capture Ratios**: Upside/Downside performance vs benchmark.
- **Drawdowns**: Peak-to-trough analysis.

### 2. Equity Ratio Engine (`pipeline/ratio_engine.py`)
Vectorized computation of 17 fundamental ratios including PE, PB, ROE, ROCE, and YoY Growth rates. It features a **Safe Division** pattern and **Indian Number Normalization** to handle various data formats.

For a detailed look at the data structure, see [DATABASE.md](./DATABASE.md).

---

## 🔄 Data Synchronization
We employ two primary sync strategies:
- **JIT Sync (Mutual Funds)**: Triggered automatically upon request if data is missing or stale.
- **Pipeline Sync (Stocks)**: Multi-stage batch processing (Price → Fundamentals → Ratios) with full audit logging in `pipeline_audit`.

---

## 🔐 Security & Auth
We use **JWT (JSON Web Tokens)** for secure, stateless authentication.
- Password hashing via `bcrypt`.
- Protected routes using FastAPI's dependency injection system.
- Audit logging for all data mutation jobs.

---

## 🛠️ Getting Started
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```
