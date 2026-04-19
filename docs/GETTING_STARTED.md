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
3. In **Project Settings > Database**, copy the **Direct Connection String** (Session Pooler recommended).
4. Replace `[YOUR-PASSWORD]` with your actual password.

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

To populate your environment with initial data:
```bash
# Seed benchmark indices
python scripts/seed_benchmarks.py

# Migrate existing mutual fund data
python scripts/migrate_data.py
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
