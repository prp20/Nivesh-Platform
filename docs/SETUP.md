# Getting Started


## 🛠️ Prerequisites
- **Docker & Docker Compose**: For the database layer.
- **Python 3.9+**: For the FastAPI application.

## 🚀 Local Setup

### 1. Database Infrastructure
Start the PostgreSQL database container:
```bash
docker-compose up -d
```
*Verification*: Connect to `localhost:5432` with user `nivesh_admin` and password `nivesh_password_123`.

### 2. Python Environment
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Application Launch
```bash
uvicorn app.main:app --port 8000
```
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: `curl http://localhost:8000/`

---

### 4. Frontend Environment
```bash
cd frontend
npm install
npm run dev
```
- **Local Dev Server**: [http://localhost:5173](http://localhost:5173)
- **Vite Configuration**: Proxies API requests to `localhost:8000`.

---

## 🏗️ Initial Data Load

To populate your local environment with benchmark indices:
```bash
python scripts/seed_benchmarks.py
```

To migrate existing mutual fund master data (equity only):
```bash
python scripts/migrate_data.py
```

---

## 🔑 Authentication
The platform uses JWT-based security for administrative endpoints.
- **Default Username**: `admin`
- **Default Password**: `admin123`
