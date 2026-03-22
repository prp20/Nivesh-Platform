# Backend Design & Data Engine

The Nivesh backend is an asynchronous powerhouse designed to handle complex financial analytics and time-series data at scale.

## 🚀 Engine Architecture
The backend is structured into specialized layers to ensure separation of concerns and high performance.

```text
backend/
├── app/
│   ├── routers/    # API endpoint definitions (Auth, Sync, Metrics)
│   ├── crud/       # SQLAlchemy database operations
│   ├── analytics/  # Core financial calculation engine
│   ├── sync/       # Background data fetching logic
│   ├── models.py   # SQLAlchemy model definitions
│   └── main.py     # FastAPI entry point
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

## 🔄 Data Synchronization
We employ a multi-tier synchronization strategy:
1. **Initial Seed**: Using `migrate_data.py` to move legacy records.
2. **On-Demand (JIT)**: Triggered when a user visits a previously unsynced asset.
3. **Bulk Sync**: A background process to refresh all active assets in the database.

---

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
