# Getting Started

Welcome to the Nivesh Elite Platform! This guide will walk you through setting up the project locally.

## 🛠️ Prerequisites

Ensure you have the following installed:
- **Python 3.10+**: [Download here](https://www.python.org/downloads/)
- **Node.js 18+**: [Download here](https://nodejs.org/)
- **Docker Desktop**: Recommended for local PostgreSQL. [Download here](https://www.docker.com/get-started/)
- **Git**: [Download here](https://git-scm.com/downloads)

---

## 🚀 One-Command Setup

The easiest way to get started is using the provided setup scripts which automate dependency installation, database configuration, and initial data seeding.

```bash
# Linux / macOS
chmod +x setup/setup.sh && ./setup/setup.sh

# Windows (PowerShell — Recommended)
powershell -ExecutionPolicy RemoteSigned -File setup\setup.ps1

# Windows (CMD)
setup\setup.bat
```

---

## 🔑 External Services Setup

### 1. Groq API Key
Used for AI-powered financial insights.
1. Sign in to the [Groq Console](https://console.groq.com/).
2. Create a new API Key (e.g., `nivesh-dev`).
3. Store it for use in your `.env` file.

### 2. Supabase (Managed Database)
If you prefer not to use local Docker, you can use Supabase:
1. Sign up at [Supabase](https://supabase.com).
2. Create a new project and set a secure database password.
3. In **Project Settings > Database**, go to the **Connection string** tab.
4. Select **Session Pooler** and copy the URI (use port **6543**, not 5432).
5. Replace `[YOUR-PASSWORD]` with your actual password and set in `backend/.env` as:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
   ```

> **⚠️ Important:** `asyncpg` is **not** compatible with Supabase's port 5432 (PgBouncer transaction mode). Always use the **Session Pooler** on port **6543**.

---

## 💻 Manual Local Setup

If the automate script doesn't fit your needs, follow these manual steps:

### 1. Database
```bash
docker-compose up -d
```
*Verification*: Connect to `localhost:5432` with user `nivesh_admin` and password `nivesh_password_123`.

### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate.bat on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
- **Local Dev Server**: [http://localhost:5173](http://localhost:5173)

---

## 🏗️ Initial Data Load

To populate your environment with initial data (run from the `backend/` directory):
```bash
# Activate the virtual environment first
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate.bat  # Windows

# 1. Seed benchmark indices (from local CSV files)
python scripts/seed_indices.py

# 2. Seed fund master records
python scripts/seed_funds.py

# 3. Fetch NAV history and compute metrics (30–60 min)
python scripts/sync_data.py

# 4. Seed stock master (18 large-cap + 3 index symbols)
python scripts/seed/seed_stock_master.py

# 5. Backfill 5 years of OHLCV price history (20–40 min)
python scripts/seed/backfill_prices.py 5y
```

---

## 🛠️ Troubleshooting

### Python 3.10+ Not Found
Ensure `python --version` returns 3.10 or higher. On Linux, use `sudo apt-get install python3.10`.

### PostgreSQL Connection Failed
If Docker is running but connection fails:
```bash
docker compose -f backend/docker-compose.yml logs postgres
docker compose -f backend/docker-compose.yml restart postgres
```

### Port 8000 Already in Use
If another process is using port 8000:
- **Linux/macOS**: `lsof -i :8000` then `kill -9 <PID>`
- **Backend Port Change**: `NIVESH_PORT=8001 uvicorn app.main:app --reload`

### ta-lib Compilation Fails (Linux)
Install system dependencies: `sudo apt-get install libta-lib-dev libta-lib0`.

---

## 🔐 Security & Production
- **JWT Auth**: Enable by setting `ENABLE_AUTH=true` in `backend/.env`.
- **Secret Key**: Generate a secure key using `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- **CORS**: Configure allowed origins in `app/main.py`.

For more details, see [ARCHITECTURE.md](./ARCHITECTURE.md) and [CONTRIBUTING.md](./CONTRIBUTING.md).
