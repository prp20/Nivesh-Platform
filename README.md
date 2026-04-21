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

**Detailed setup guide:** See [Getting Started](./docs/GETTING_STARTED.md)

---

## 📖 Documentation

| Document | Purpose |
|----------|---------|
| **[Getting Started](./docs/GETTING_STARTED.md)** | Installation, prerequisites, local development setup |
| **[Architecture](./docs/ARCHITECTURE.md)** | System design, database schema, tech stack |
| **[Core Features](./docs/FEATURES.md)** | Data pipeline, scoring engines, stock screener |
| **[API Reference](./docs/API_REFERENCE.md)** | All REST endpoints with examples and authentication |
| **[Contributing](./docs/CONTRIBUTING.md)** | Developer workflow, branching strategy, testing |
| **[Fundamental Design](./docs/fundamental_scoring_design.md)** | Deep dive into financial scoring logic |
| **[Sector Scoring](./docs/sector_specific_scoring.md)** | Sector-specific metric definitions |
| **[Developer Guidelines](./CLAUDE.md)** | Code style, project structure, common commands |
| **[Release Notes](./RELEASE_NOTES.md)** | Version history and change logs |

---

## 🏗️ Tech Stack

**Frontend:** React 19 + Vite + Tailwind CSS + Redux Toolkit  
**Backend:** FastAPI + SQLAlchemy 2.0 + asyncpg  
**Database:** PostgreSQL 16  
**Data Processing:** pandas, NumPy, TA-Lib  
**Scheduling:** APScheduler (background jobs)  
**Testing:** pytest + pytest-asyncio + in-memory SQLite

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

See [Contributing](./docs/CONTRIBUTING.md) for detailed guidelines.

---

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v                    # Run all tests
pytest tests/test_funds.py -v      # Single test file
pytest tests/ --cov=app            # With coverage
```

- **45+ test cases** covering all API endpoints
- Uses **in-memory SQLite** (no database needed)
- ~52 seconds for full suite
- See [Contributing](./docs/CONTRIBUTING.md) for details

### Frontend Tests

Frontend tests can be added using Vitest + React Testing Library.

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

See [Contributing](./docs/CONTRIBUTING.md) for detailed guidelines.

---

## 📝 License

Released under the **MIT License**. See individual file headers for attribution.

---

## 🆘 Need Help?

- **Setup Issues** → See [Getting Started](./docs/GETTING_STARTED.md#troubleshooting)
- **API Questions** → See [API Reference](./docs/API_REFERENCE.md)
- **Architecture** → See [Architecture](./docs/ARCHITECTURE.md)
- **Database** → See [Architecture](./docs/ARCHITECTURE.md#database-schema)

---

**Built with ❤️ for serious investors | © 2024–2026**
