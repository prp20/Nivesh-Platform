# Developer & Contributing Guide

Thank you for contributing to Nivesh Elite! This document outlines the development workflow, coding standards, and testing procedures.

---

## 🛠️ Development Workflow

### 1. Feature Development
When adding a new financial indicator or feature:
1.  **Backend Logic**: Extend the core calculation engine (e.g., `app/analytics.py` or `pipeline/ratio_engine.py`).
2.  **Database**: Update SQLAlchemy `models.py` and run migrations if necessary.
3.  **API**: Add or update Pydantic `schemas.py` and implement the route in `app/routers/`.
4.  **Frontend**: 
    - Update the corresponding API service in `src/api/`.
    - Update the Redux slice (e.g., `fundsSlice.js`) to handle the new data.
    - Expose the data point in the relevant UI component/page using **Califino** design tokens.

### 2. Style & Design (CALIFINO)
- All styling should follow the **CALIFINO** design system.
- Use HSL variables defined in `index.css` for all colors.
- Maintain the glassmorphic aesthetic (blur, subtle borders, frosted backgrounds).

---

## 🔄 Data Initialization

After a fresh setup, run these scripts from the `backend/` directory (with venv activated):

1.  **Seed Benchmark Indices**: `python scripts/seed_indices.py`
2.  **Seed Fund Master**: `python scripts/seed_funds.py`
3.  **Sync NAV History + Metrics**: `python scripts/sync_data.py` *(30–60 min)*
4.  **Seed Stock Master**: `python scripts/seed/seed_stock_master.py`
5.  **Backfill Price History**: `python scripts/seed/backfill_prices.py 5y` *(20–40 min)*
6.  **Seed Fundamentals** *(optional)*: `python scripts/seed/seed_fundamentals.py`

---

## 🧪 Testing

We use `pytest` with `pytest-asyncio` for backend testing.

### Quick Start
```bash
cd backend
pytest tests/ -v
```

### Coverage
```bash
pytest tests/ --cov=app --cov=pipeline
```

### Test Architecture
- **In-memory SQLite**: Tests use SQLite to ensure speed and isolation (no PostgreSQL needed).
- **Fixtures**: Common data and clients are defined in `conftest.py`.
- **Async Tracking**: All API tests should use the `async_client` fixture and be marked with `@pytest.mark.asyncio`.

---

## 📝 Coding Standards

- **Asynchronous Code**: Prefer `async/await` for all I/O bound operations. Use `asyncio.to_thread()` when calling synchronous libraries like `yfinance` or `requests`.
- **Typing**: Use Pydantic models for request/response validation. Use Python type hints for better DX.
- **Environment Driven**: Never hardcode URLs or secrets. Always use `.env` files via `pydantic-settings`.
- **Error Handling**: Use standard HTTP status codes. Provide descriptive error messages in the response body.

---

## 🔐 Git Workflow

1.  Create a feature branch from `main`: `git checkout -b feature/your-feature-name`.
2.  Commit with clear messages (e.g., `feat(api): add new fundamental ratio`).
3.  Ensure tests pass locally before pushing.
4.  Open a Pull Request with a descriptive summary of your changes.
