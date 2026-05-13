# Getting Started

This guide walks you through setting up the Nivesh Platform from a fresh clone — including creating a Supabase project, running Alembic migrations, and seeding the database with initial data.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | `python --version` |
| pip | Latest | comes with Python |
| Git | Any | `git --version` |
| psycopg2-binary | (pip) | installed via requirements below |

No Docker required. The database lives on Supabase (free tier is sufficient).

---

## 1. Clone and Install

```bash
git clone https://github.com/prp20/Nivesh-Platform.git
cd Nivesh-Platform

# Install all three packages + dev tools in editable mode
pip install -r requirements-dev.txt
```

`requirements-dev.txt` installs `nivesh-shared`, `nivesh-server`, and `nivesh-client` in editable mode so imports resolve correctly across the monorepo.

---

## 2. Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign in.
2. Click **New Project** — choose a name (e.g., `nivesh-platform`), region closest to you, and a strong database password. **Save this password.**
3. Wait ~2 minutes for the project to provision.

### Get your connection strings

In the Supabase dashboard: **Project Settings → Database → Connection string**

You need **two** URLs:

| URL | Where to find it | Port | Used for |
|-----|-----------------|------|---------|
| Supavisor Pooler | Connection string tab → **Session Pooler** | `6543` | Runtime (FastAPI) |
| Direct | Connection string tab → **Direct connection** | `5432` | Alembic migrations only |

Both URLs look like:
```
postgresql://postgres.[ref]:[password]@...supabase.com:[port]/postgres
```

Replace `[YOUR-PASSWORD]` with the password you saved above.

---

## 3. Configure Environment

```bash
cd nivesh-server
cp .env.example .env
```

Edit `.env` and fill in:

```env
# Runtime — Supavisor pooler (port 6543) — used by FastAPI
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres

# Migrations — Direct connection (port 5432) — used only by Alembic
ALEMBIC_URL=postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres

# Generate a secret key:
# python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=replace-with-256-bit-random-string

ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
ENVIRONMENT=development
ENABLE_AUTH=false
```

> **Important:** Never commit `.env`. It is in `.gitignore`.

---

## 4. Run Alembic Migrations

This creates all 18 tables in your Supabase database.

```bash
# From nivesh-server/
export ALEMBIC_URL="postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres"

alembic upgrade head
```

Expected output (abridged):
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001, base extensions + trigger function
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, admin_users table
INFO  [alembic.runtime.migration] Running upgrade 002 -> 003, etl_runs table
...
INFO  [alembic.runtime.migration] Running upgrade 017 -> 018, fundamental_scores table
```

If a migration fails, fix the issue and re-run `alembic upgrade head` — it resumes from where it left off.

To check current state:
```bash
alembic current
alembic history --verbose
```

---

## 5. Seed the Database

Seed scripts read from CSV files in `nivesh-server/data/` and upsert into the database using the Supavisor pooler URL (port 6543).

```bash
# From nivesh-server/
export DATABASE_URL="postgresql://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

# Run all seeds in dependency order (benchmarks → stocks → funds)
python scripts/seed/run_all_seeds.py
```

### What gets seeded

| Script | Table | Source CSV | Rows |
|--------|-------|-----------|------|
| `seed_benchmarks.py` | `benchmark_master` | `data/indices.csv` | ~10 indices |
| `seed_stocks.py` | `stocks` | `data/stocks.csv` + `data/indices.csv` | ~500+ equities + indices |
| `seed_funds.py` | `fund_master` | `data/scheme_master_with_benchmark.csv` | ~2518 funds |

### Preview without writing (dry run)

```bash
python scripts/seed/run_all_seeds.py --dry-run
```

### Run individual seeds

```bash
python scripts/seed/seed_benchmarks.py
python scripts/seed/seed_stocks.py
python scripts/seed/seed_funds.py
```

---

## 6. Verify in Supabase

In the Supabase dashboard, open **Table Editor** and confirm:

- `benchmark_master` — has rows for NIFTY50, SENSEX, NIFTYBANK, etc.
- `stocks` — has equity rows + index rows (is_index=true)
- `fund_master` — has ~2500 mutual fund rows

You can also run SQL directly in **SQL Editor**:
```sql
SELECT COUNT(*) FROM benchmark_master;
SELECT COUNT(*) FROM stocks;
SELECT COUNT(*) FROM fund_master;
SELECT COUNT(*) FROM etl_runs;
```

---

## 7. Run the Server Locally

```bash
# From repo root
cd nivesh-server
uvicorn app.main:app --port 8000 --reload
```

API docs: http://localhost:8000/docs

Health check:
```bash
curl http://localhost:8000/health
```

---

## Troubleshooting

### `ALEMBIC_URL not set` error
Make sure you `export ALEMBIC_URL=...` in the same shell session before running `alembic upgrade head`. Or set it in `.env` — but note Alembic reads it from the env var, not the `.env` file directly (unless you add `python-dotenv` loading to `env.py`).

### `psycopg2` not installed
```bash
pip install psycopg2-binary
```

### Migration fails on extension
Supabase free tier has `pg_trgm` and `uuid-ossp` pre-installed. If you see "extension already exists", that's fine — migrations use `CREATE EXTENSION IF NOT EXISTS`.

### Alembic says `Target database is not up to date`
Someone ran a partial migration. Run `alembic current` to see where it stopped, then `alembic upgrade head` to continue.

### Connection refused on port 5432
You are using the pooler URL (6543) for Alembic. Switch to the **direct connection** URL (5432) for migrations. The pooler runs in transaction mode and doesn't support DDL reliably.

### Seed script: `no such table`
Migrations haven't been applied yet. Run `alembic upgrade head` first.
