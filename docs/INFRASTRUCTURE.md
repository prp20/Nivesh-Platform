# Infrastructure & Docker Setup

Nivesh Elite's infrastructure is designed for portability and consistent deployments using **Docker Compose**.

## 🐋 Docker Services

### 🧬 database (PostgreSQL)
The core data engine, based on the official PostgreSQL image (`postgres:16-alpine`).
- **Data Persistence**: Uses a named volume `nivesh_pg_data` to ensure persistence across container restarts.
- **Auto-Initialization**: Custom initialization scripts can be placed in `.docker-init/` (optional).
- **Indexing**: B-Tree indexes on time-series columns for efficient range queries.

---

## 🏗️ Volumes & Networking
- **`nivesh_pg_data`**: A named volume for persistent database storage.
- **Port Mapping**: The database is exposed on host port `5432` for external inspection (e.g., via TablePlus or pgAdmin).

---

## ⚙️ Environment Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | SQLAlchemy connection string | `postgresql+asyncpg://nivesh_admin:nivesh_password_123@localhost:5432/nivesh_db` |
| `SECRET_KEY` | JWT signing key | *Auto-generated for security* |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Session duration | `1440` (24 hours) |

---

## 🚀 Deployment Command
```bash
# In the root or backend directory
docker-compose up -d
```
