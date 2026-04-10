# Nivesh Elite Platform

> **Premium Financial Analytics & Portfolio Management Platform**

A modern, full-stack financial analytics ecosystem for mutual fund tracking, stock market analysis, and professional portfolio screeners. Built with FastAPI, React 19, and PostgreSQL.

---

## ✨ Key Features

- 📊 **Advanced Analytics** — Sharpe, Sortino, Information Ratio metrics
- 🏦 **Mutual Fund Intelligence** — NAV tracking, benchmark comparison, risk profiling
- 📈 **Stock Market Ecosystem** — Real-time NSE/BSE data, fundamental analysis, technical indicators
- 🔍 **Professional Screener** — 15+ filters for intelligent stock selection
- ⚡ **Automated Pipeline** — Daily price sync, weekly fundamentals, scheduled ratio/rating computation
- 🔐 **Enterprise Auth** — JWT-based authentication with role-based access control
- 📱 **Production-Ready** — React SPA served via FastAPI backend, fully containerized

---

## 🚀 Quick Start

### Requirements

- **Python** 3.10+
- **Node.js** 18+
- **Docker** (optional — can use external PostgreSQL)
- **PostgreSQL** 13+ (via Docker or external)

### One-Command Setup

```bash
# Linux / macOS
chmod +x setup/setup.sh && ./setup/setup.sh

# Windows (PowerShell — Recommended)
powershell -ExecutionPolicy RemoteSigned -File setup\setup.ps1

# Windows (CMD)
setup\setup.bat
```

The setup script will install dependencies, configure the database, build the frontend, and start the API server at **http://localhost:8000**.

**Detailed setup guide:** See [Installation Guide](./docs/INSTALLATION.md)

---

## 📖 Documentation

| Document | Purpose |
|----------|---------|
| **[Installation Guide](./docs/INSTALLATION.md)** | System requirements, step-by-step setup, troubleshooting |
| **[System Overview](./docs/OVERVIEW.md)** | Architecture, design decisions, data flow |
| **[API Reference](./docs/API_REFERENCE.md)** | All REST endpoints with examples and authentication |
| **[Database Schema](./docs/DATABASE.md)** | Database models, table relationships, storage patterns |
| **[Frontend Architecture](./docs/FRONTEND.md)** | React components, state management, design system |
| **[Backend Architecture](./docs/BACKEND.md)** | FastAPI structure, async patterns, analytics engine |
| **[Development Workflow](./docs/WORKFLOW.md)** | Git workflow, branching strategy, commit conventions |
| **[Setup Scripts Guide](./setup/README.md)** | Detailed guide for all three setup scripts |
| **[Developer Guidelines](./CLAUDE.md)** | Code style, project structure, common commands |

---

## 🏗️ Tech Stack

**Frontend:** React 19 + Vite + Tailwind CSS + Redux Toolkit  
**Backend:** FastAPI + SQLAlchemy 2.0 + asyncpg  
**Database:** PostgreSQL 16  
**Data Processing:** pandas, NumPy, TA-Lib  
**Scheduling:** APScheduler (background jobs)

---

## 🎯 Project Structure

```
stock_nivesh_platform/
├── backend/              # FastAPI application
│   ├── app/             # Core API logic
│   ├── pipeline/        # Scheduled data jobs
│   ├── scripts/         # Seed & ETL scripts
│   ├── alembic/         # Database migrations
│   └── requirements.txt
├── frontend/            # React 19 + Vite SPA
│   ├── src/
│   │   ├── pages/      # Route components
│   │   ├── components/ # Reusable UI
│   │   ├── store/      # Redux state
│   │   └── api/        # API service layer
│   └── package.json
├── setup/              # Installation scripts
│   ├── setup.sh       # Linux/macOS
│   ├── setup.ps1      # Windows PowerShell
│   └── setup.bat      # Windows CMD
├── docs/              # Comprehensive documentation
└── CLAUDE.md          # Developer guidelines
```

---

## 🚀 Development

After running the setup script, start development with:

```bash
# Backend (terminal 1)
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# Frontend (terminal 2)
cd frontend
npm run dev
```

See [Development Workflow](./docs/WORKFLOW.md) for detailed guidelines.

---

## 🔐 Security

- JWT authentication (HS256) with bcrypt hashing
- Role-based access control on write endpoints
- CORS configured for frontend origin
- Sensitive config stored in `.env` (not in git)

For production, set in `backend/.env`:
```
ENABLE_AUTH=true
SECRET_KEY=<use: secrets.token_urlsafe(32)>
```

---

## 🤝 Contributing

1. Create a feature branch (`git checkout -b feature/your-feature`)
2. Commit with clear messages
3. Push to your fork
4. Open a Pull Request

See [Development Workflow](./docs/WORKFLOW.md) for detailed guidelines.

---

## 📝 License

Released under the **MIT License**. See individual file headers for attribution.

---

## 🆘 Need Help?

- **Setup Issues** → See [Installation Guide](./docs/INSTALLATION.md#troubleshooting)
- **API Questions** → See [API Reference](./docs/API_REFERENCE.md)
- **Architecture** → See [System Overview](./docs/OVERVIEW.md)
- **Database** → See [Database Schema](./docs/DATABASE.md)

---

**Built with ❤️ for serious investors | © 2024–2026**
