# Nivesh Backend Microservices

This is the high-performance backend for the Nivesh Platform, built with FastAPI and TimescaleDB.

## 🚀 Quick Start

### 1. Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- [Python 3.9+](https://www.python.org/downloads/)

### 2. Infrastructure Setup
Start the TimescaleDB (PostgreSQL) instance:
```bash
docker-compose up -d
```
*Note: This will automatically create the `nivesh_db` and initialize the time-series hypertables.*

### 3. Application Setup
Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run the Server
Start the FastAPI application using Uvicorn:
```bash
uvicorn app.main:app --reload --reload-dir app --port 8000
```

### 5. Verify & Documentation
- **API Health**: [http://localhost:8000/](http://localhost:8000/)
- **Interactive Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🛠️ Core Features

- **Auth**: JWT-based login (`/api/v1/auth/login`) - Default: `admin` / `admin123`.
- **Master Data**: Manage Mutual Funds and Benchmarks.
- **Time-Series**: Bulk upload and query historical NAV data.
- **Analytics**: On-demand computation of Sharpe, Sortino, and Max Drawdown.
- **Sync**: Background jobs to refresh data via `mftool`.

## 📦 Initial Data Sync
Once the server is running, you can populate the master data and sync NAVs:
1. Visit `/docs`.
2. Use the `POST /api/v1/sync/all` endpoint to trigger a global data refresh.
