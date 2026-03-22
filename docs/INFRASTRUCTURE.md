# Infrastructure & Docker Setup

Nivesh Elite's infrastructure is designed for portability and consistent deployments using **Docker Compose**.

## 🐋 Docker Services

### 🧬 database (TimescaleDB)
The core data engine, based on the official TimescaleDB image (`timescale/timescaledb:latest-pg14`).
- **Data Persistence**: Uses a named volume `db_data` to ensure persistence across container restarts.
- **Auto-Initialization**: Custom initialization scripts can be placed in `.docker-init/` (optional).
- **Time-Series Optimization**: Pre-configured to handle massive amounts of financial data points.

---

## 🏗️ Volumes & Networking
- **`db_data`**: A named volume for persistent database storage.
- **Port Mapping**: The database is exposed on host port `5432` for external inspection (e.g., via TablePlus or pgAdmin).

---

## ⚙️ Environment Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | SQLAlchemy connection string | `postgresql+asyncpg://postgres:postgres@localhost:5432/nivesh_db` |
| `SECRET_KEY` | JWT signing key | *Auto-generated for security* |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Session duration | `1440` (24 hours) |

---

## 🚀 Deployment Command
```bash
# In the root or backend directory
docker-compose up -d
```
