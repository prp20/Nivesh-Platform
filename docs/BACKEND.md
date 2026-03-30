# Backend Design & Data Engine

The Nivesh backend is an asynchronous powerhouse designed to handle complex financial analytics and time-series data at scale.

## 🚀 Engine Architecture
The backend is structured into specialized layers to ensure separation of concerns and high performance.

backend/
├── app/
│   ├── routers/    # API endpoint definitions
│   ├── analytics.py # Core financial calculation engine
│   ├── crud.py      # SQLAlchemy database operations
│   ├── sync.py      # Background data fetching logic
│   ├── models.py    # SQLAlchemy model definitions
│   ├── schemas.py   # Pydantic models for validation
│   ├── security.py  # JWT and password hashing
│   ├── database.py  # Engine and session configuration
│   └── main.py      # FastAPI entry point
│   └── config.py    # Environment settings
```

---

## 📊 Analytics Engine
The analytics layer calculates key risk indicators for mutual funds:
- **Sharpe Ratio**: Measures risk-adjusted return.
- **Sortino Ratio**: Focuses on downside risk.
- **Standard Deviation**: Calculates historical volatility.
- **Max Drawdown**: Analyzes the worst-case peak-to-trough decline.

Data is fetched via `mftool` (AMFI) and processed using `pandas` for vectorized performance.

---

## 🔄 Data Synchronization & Scripts

We employ a robust data lifecycle management strategy using specialized scripts in `backend/scripts/`:

### Core ETL Pipelines
- **`etl_populate_data.py`**: The primary engine for synchronizing fund metadata and computing metrics on-demand.
- **`populate_nav_history.py`**: Fetches and persists historical NAV data for mutual funds.
- **`recompute_funds_metrics.py`**: Refreshes all mathematical ratios (Sharpe, etc.) based on updated NAV histories.

### Seeding & Initialization (`backend/scripts/seed/`)
- **`seed_benchmarks.py`**: Initializes the benchmark index master data.
- **`import_nifty_indices.py`**: Bulk imports historical NAVs for various Nifty indices.
- **`ingest_isins_amfi.py`**: Maps ISINs from AMFI sources to the database records.

---

## 🚀 Engine Architecture
The backend is structured into specialized layers to ensure separation of concerns and high performance.

```text
backend/
├── app/
│   ├── routers/    # API endpoint definitions
│   ├── analytics.py # Core financial calculation engine
│   ├── crud.py      # SQLAlchemy database operations
│   ├── sync.py      # Background data fetching logic
│   ├── models.py    # SQLAlchemy model definitions
│   ├── schemas.py   # Pydantic models for validation
│   └── main.py      # FastAPI entry point
├── scripts/
│   ├── seed/        # One-time initialization scripts
│   └── ...          # Core ETL pipelines
```


## 🔐 Security & Auth
We use **JWT (JSON Web Tokens)** for secure, stateless authentication.
- Password hashing via `bcrypt`.
- Token expiration and refreshes for session management.
- Protected routes using FastAPI's dependency injection system.

---

## 🛠️ Getting Started
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```
