# Nivesh Backend Microservices

High-performance financial analytics backend powered by **FastAPI** and **PostgreSQL**.

## 📖 Documentation
Detailed guides are available in the [docs/](./docs/) directory:

- 🚀 [**Getting Started**](./docs/SETUP.md): Installation and local deployment.
- 🗄️ [**Database Schema**](./docs/DATABASE.md): Table structures and time-series data.
- 🔄 [**API & Sync Guide**](./docs/API_GUIDE.md): Synchronizing NAVs and computing metrics.

## ⚡ Quick Start
```bash
# 1. Start Database
docker-compose up -d

# 2. Run App
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

## 🧪 Testing
```bash
# Run all tests (uses in-memory SQLite, no DB needed)
pytest tests/ -v

# Run specific test file
pytest tests/test_funds.py -v

# Run with coverage
pytest tests/ --cov=app --cov=pipeline
```

**Test Coverage:** 45+ tests across 9 files covering all API endpoints (funds, stocks, metrics, benchmarks, screener, auth, pipeline).

See [docs/TESTING.md](../docs/TESTING.md) for details.

## 🛠️ Main Stack
- **Framework**: FastAPI (Async)
- **Database**: PostgreSQL 16
- **ORM**: SQLAlchemy (Async)
- **Data Source**: mftool (AMFI)
- **Testing**: pytest + pytest-asyncio + in-memory SQLite
