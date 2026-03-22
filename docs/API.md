# API Reference & Data Sync

Nivesh Elite provides a robust set of RESTful endpoints for financial data management, authentication, and synchronization.

## 🔑 Authentication
- **Base Endpoint**: `/api/v1/auth`
- **Login**: `POST /login` (Returns JWT)
- **Me**: `GET /me` (Requires JWT)

---

## 📊 Mutual Funds
- **Listing**: `GET /api/v1/funds/` (Supports `skip` and `limit`)
- **Detail**: `GET /api/v1/funds/{scheme_code}`
- **Metrics**: `GET /api/v1/metrics/{scheme_code}` (Triggers **JIT Sync** if data is missing)
- **Compute**: `POST /api/v1/metrics/{scheme_code}/compute` (Manual re-calculation)

---

## 📈 Benchmarks (Indices)
- **Listing**: `GET /api/v1/benchmarks/`
- **History**: `GET /api/v1/benchmark-navs/{benchmark_code}`

---

## 🔄 Data Synchronization
- **Sync Fund**: `POST /api/v1/sync/fund/{scheme_code}` (Force sync 1 fund)
- **Sync All**: `POST /api/v1/sync/all` (Trigger global background sync)

---

## 🛠️ Administrative CRUD
These endpoints require a valid JWT with administrative privileges:
- **Create**: `POST /api/v1/funds/`
- **Update**: `PUT /api/v1/funds/{scheme_code}`
- **Delete**: `DELETE /api/v1/funds/{scheme_code}`
