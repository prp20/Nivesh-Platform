# Nivesh Elite Platform 🏆

A premium, high-performance financial analytics and mutual fund management ecosystem. Built with a focus on aesthetic excellence, real-time data accuracy, and professional risk profiling.

## 💎 Key Features
- **Professional Analytics**: Sharpe, Sortino, and Volatility metrics computed on-the-fly.
- **Stock Market Ecosystem**: Real-time NSE/BSE data, fundamental screener, and technical analysis.
- **CALIFINO Design**: Luxe, permanent dark-mode interface with glassmorphic UI.
- **Just-In-Time Sync**: Automated historical data fetching for previously unsynced assets.
- **Market Intelligence**: Dedicated dashboard for tracking global market benchmarks and indices.
- **Administrative CRUD**: Complete lifecycle management for financial assets.

---

## 📖 Project Documentation
Explore our detailed guides in the [docs/](./docs/) directory:

- 🏗️ [**System Overview**](./docs/OVERVIEW.md): Architecture and security model.
- 🎨 [**Frontend Architecture**](./docs/FRONTEND.md): Design philosophy and project structure.
- 🚀 [**Backend & Analytics**](./docs/BACKEND.md): Data engine and security.
- 🗄️ [**Database Schema**](./docs/DATABASE.md): Models and database schema.
- 🔌 [**API Reference**](./docs/API_REFERENCE.md): Endpoint usage and authentication.
- 🐋 [**Infrastructure Setup**](./docs/INFRASTRUCTURE.md): Docker and environment config.
- 🔄 [**Development Workflow**](./docs/WORKFLOW.md): Migrations and dev procedures.

---

## ⚡ Quick Start

### 1. Database Infrastructure
```bash
cd backend
docker-compose up -d
```

### 2. Backend Launch
```bash
# In backend/
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

### 3. Frontend Launch
```bash
# In frontend/
npm install
npm run dev
```

---

## 🧩 Tech Stack
**Frontend**: React, Vite, Vanilla CSS  
**Backend**: FastAPI, Async SQLAlchemy, pandas  
**Database**: PostgreSQL 16  
**Data Sources**: mftool (AMFI)

---

## 🛡️ License
Nivesh Elite is an open-source financial assistant. Please refer to individual file headers for specific attribution.
