# Nivesh Platform — Phase 3: Ingestion Pipeline
## Detailed Implementation Plan · Grounded in dev branch code
### Version 1.0 · May 2026

---

## Table of Contents

1. [Phase 3 Goal & Scope](#1-phase-3-goal--scope)
2. [What the Codebase Already Has](#2-what-the-codebase-already-has)
3. [Data Sources & Target Tables Map](#3-data-sources--target-tables-map)
4. [Pipeline Architecture](#4-pipeline-architecture)
5. [File Tree — Phase 3 Additions](#5-file-tree--phase-3-additions)
6. [Task 3.1 — Scheduler Bootstrap](#task-31--scheduler-bootstrap)
7. [Task 3.2 — Pipeline Base Class](#task-32--pipeline-base-class)
8. [Task 3.3 — AMFI NAV Pipeline](#task-33--amfi-nav-pipeline)
9. [Task 3.4 — Benchmark NAV Pipeline](#task-34--benchmark-nav-pipeline)
10. [Task 3.5 — Fund Metrics Recompute Pipeline](#task-35--fund-metrics-recompute-pipeline)
11. [Task 3.6 — Yahoo Finance Price Pipeline](#task-36--yahoo-finance-price-pipeline)
12. [Task 3.7 — Technical Indicators Pipeline](#task-37--technical-indicators-pipeline)
13. [Task 3.8 — Screener Financial Statements Pipeline](#task-38--screener-financial-statements-pipeline)
14. [Task 3.9 — Financial Ratios Pipeline](#task-39--financial-ratios-pipeline)
15. [Task 3.10 — Stock Ratings Pipeline](#task-310--stock-ratings-pipeline)
16. [Task 3.11 — Manual Trigger API Endpoints](#task-311--manual-trigger-api-endpoints)
17. [Task 3.12 — Render Upgrade & Cron Verification](#task-312--render-upgrade--cron-verification)
18. [Cron Schedule Summary](#18-cron-schedule-summary)
19. [Error Handling Strategy](#19-error-handling-strategy)
20. [Render Memory Constraints & Batching](#20-render-memory-constraints--batching)
21. [Dependency Changes](#21-dependency-changes)
22. [Definition of Done](#22-definition-of-done)
23. [Execution Order — Day by Day](#23-execution-order--day-by-day)

---

## 1. Phase 3 Goal & Scope

**Goal:** Promote existing ad-hoc ETL scripts into a production APScheduler pipeline running on the Render server. All pipelines log to `etl_runs` (built in Phase 2). The server becomes self-updating — data refreshes automatically on schedule without any manual intervention.

**In scope:**
- APScheduler setup integrated into FastAPI lifespan
- 7 pipelines covering all 15 existing tables (MF + stocks)
- `EtlRun` logging at start/finish of every pipeline
- Manual trigger endpoints for each pipeline (admin use)
- Batching strategy to keep Render free tier's 512 MB RAM safe
- Upgrade from Render free to Starter ($7/month) — required for always-on scheduler

**Out of scope:**
- Client sync engine (Phase 5)
- Any new data sources not already implicit in the existing models
- Pattern detection (`detected_patterns` table) — deferred to Phase 3.5 or later; the model exists but no source data pipeline is defined yet

**Existing data sources confirmed from codebase:**
- `yf_symbol` on `Stock` → Yahoo Finance (`yfinance`) for `price_data` and `technical_indicators`
- `screener_slug` on `Stock` → Screener.in for `financial_statements`, `financial_ratios`, `shareholding_pattern`
- AMFI `NAVAll.txt` / `mftool` → `fund_nav_history`
- NSE index data → `benchmark_nav_history`
- Computed from nav history → `fund_metrics`, `benchmark_metrics`
- Computed from price + ratios → `technical_indicators`, `stock_ratings`, `fundamental_scores`

---

## 2. What the Codebase Already Has

Reading `models.py`, `crud.py`, and `schemas.py` tells us exactly what exists:

### Already implemented (ETL logic exists somewhere in the repo)
| Capability | Evidence in code |
|---|---|
| Bulk NAV upsert | `bulk_insert_fund_navs` in `crud.py` lines 379–406 — full upsert with conflict resolution |
| Benchmark NAV upsert | `bulk_insert_benchmark_navs` in `crud.py` lines 408–431 |
| Fund metrics upsert | `upsert_fund_metrics` in `crud.py` lines 499–509 |
| Benchmark metrics upsert | `upsert_benchmark_metrics` in `crud.py` lines 487–497 |
| SyncJob creation | `create_sync_job` / `update_sync_job` in `crud.py` — Phase 2 replaces these with `EtlRun` |
| `raw_checksum` on `FinancialStatement` | Implies existing de-dup logic for Screener scraping |
| `final_verdict` on `FundMetrics` | Implies existing analytics engine producing text verdicts |

### What Phase 3 builds
| What | Status |
|---|---|
| APScheduler wiring into FastAPI lifespan | New |
| `BasePipeline` class with `EtlRun` logging | New |
| Scheduler cron config for all 7 pipelines | New |
| Explicit pipeline modules under `app/pipelines/` | New (promotes existing scripts) |
| Manual trigger endpoints at `POST /admin/pipelines/{name}/run` | New |

---

## 3. Data Sources & Target Tables Map

| Pipeline | Source | Target Tables | Frequency |
|---|---|---|---|
| `amfi_nav` | AMFI `NAVAll.txt` (free, no auth) | `fund_master`, `fund_nav_history` | Daily 21:30 IST |
| `benchmark_nav` | `mftool` / NSE index data | `benchmark_master`, `benchmark_nav_history` | Daily 19:30 IST |
| `fund_metrics` | Computed from `fund_nav_history` + `benchmark_nav_history` | `fund_metrics`, `benchmark_metrics` | Daily 23:00 IST |
| `yf_price` | Yahoo Finance (`yfinance`) | `price_data` | Mon–Fri 19:00 IST |
| `technical_indicators` | Computed from `price_data` (pandas-ta) | `technical_indicators` | Mon–Fri 20:00 IST |
| `screener_fundamentals` | Screener.in (HTML scrape) | `financial_statements`, `financial_ratios`, `shareholding_pattern` | Weekly Sunday 06:00 IST |
| `stock_ratings` | Computed from `financial_ratios` + `technical_indicators` | `stock_ratings`, `fundamental_scores` | Daily 21:00 IST |

---

## 4. Pipeline Architecture

```
FastAPI lifespan
    └── APScheduler (AsyncIOScheduler, IST timezone)
            │
            ├── amfi_nav          (daily 21:30)
            ├── benchmark_nav     (daily 19:30)
            ├── fund_metrics      (daily 23:00)
            ├── yf_price          (Mon-Fri 19:00)
            ├── technical_indicators (Mon-Fri 20:00)
            ├── screener_fundamentals (weekly Sun 06:00)
            └── stock_ratings     (daily 21:00)

Each pipeline:
    1. Calls start_etl_run()  → writes RUNNING row to etl_runs
    2. Fetches / computes data
    3. Upserts to target table(s) via existing crud functions
    4. Calls finish_etl_run() → updates row to COMPLETED / FAILED
    5. On exception → finish_etl_run(status="FAILED", error_msg=...)

All pipelines inherit BasePipeline which handles steps 1, 4, 5.
```

### Key design rule — no new CRUD functions for existing upserts

`crud.py` already has correct upsert implementations for all MF tables. Phase 3 pipelines call these existing functions directly. New CRUD functions are added only for `price_data`, `technical_indicators`, `financial_statements`, `financial_ratios`, `shareholding_pattern`, `stock_ratings`, and `fundamental_scores` — tables the existing crud.py does not yet cover.

---

## 5. File Tree — Phase 3 Additions

```
nivesh-server/app/
├── pipelines/                        ← NEW directory
│   ├── __init__.py
│   ├── base.py                       ← BasePipeline class
│   ├── scheduler.py                  ← APScheduler setup + job registration
│   ├── amfi_nav.py                   ← AMFI NAV pipeline
│   ├── benchmark_nav.py              ← Benchmark NAV pipeline
│   ├── fund_metrics.py               ← Fund + benchmark metrics recompute
│   ├── yf_price.py                   ← Yahoo Finance price ingestion
│   ├── technical_indicators.py       ← pandas-ta computation
│   ├── screener_fundamentals.py      ← Screener.in scraper
│   └── stock_ratings.py              ← Rating + scoring pipeline
├── crud.py                           ← MODIFY: add 6 new upsert functions
├── main.py                           ← MODIFY: register scheduler in lifespan
└── routers/
    └── admin.py                      ← NEW: manual trigger endpoints
```

---

## Task 3.1 — Scheduler Bootstrap

**File:** `app/pipelines/scheduler.py` (new)
**File:** `app/main.py` (modify lifespan)
**Estimated time:** 1 hour

### `app/pipelines/scheduler.py`

```python
# app/pipelines/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import logging

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

# Single scheduler instance — shared across the app
scheduler = AsyncIOScheduler(timezone=IST)


def register_all_jobs(db_factory):
    """
    Register all pipeline jobs with the scheduler.

    db_factory is a callable that returns a new AsyncSession.
    Passed in from main.py so the scheduler doesn't import database.py directly.

    Job IDs match pipeline_name values used in etl_runs table —
    this is intentional: GET /sync/status?pipeline_name=amfi_nav
    returns the runs for the job named 'amfi_nav'.
    """
    from .amfi_nav             import AmfiNavPipeline
    from .benchmark_nav        import BenchmarkNavPipeline
    from .fund_metrics         import FundMetricsPipeline
    from .yf_price             import YfPricePipeline
    from .technical_indicators import TechnicalIndicatorsPipeline
    from .screener_fundamentals import ScreenerFundamentalsPipeline
    from .stock_ratings        import StockRatingsPipeline

    jobs = [
        # ── MF pipelines ──────────────────────────────────────────────────────
        # AMFI publishes NAVAll.txt by ~21:00 IST. We run at 21:30 for margin.
        dict(
            func=lambda: AmfiNavPipeline(db_factory()).run(),
            trigger=CronTrigger(hour=21, minute=30, timezone=IST),
            id="amfi_nav",
            name="AMFI NAV daily sync",
        ),
        # Benchmark NAV runs before fund_metrics (which depends on it)
        dict(
            func=lambda: BenchmarkNavPipeline(db_factory()).run(),
            trigger=CronTrigger(hour=19, minute=30, timezone=IST),
            id="benchmark_nav",
            name="Benchmark NAV daily sync",
        ),
        # Fund metrics computed after both NAV pipelines have run
        dict(
            func=lambda: FundMetricsPipeline(db_factory()).run(),
            trigger=CronTrigger(hour=23, minute=0, timezone=IST),
            id="fund_metrics",
            name="Fund + benchmark metrics recompute",
        ),

        # ── Stock pipelines ───────────────────────────────────────────────────
        # Yahoo Finance data available ~18:30 IST after NSE closes
        dict(
            func=lambda: YfPricePipeline(db_factory()).run(),
            trigger=CronTrigger(
                day_of_week="mon-fri", hour=19, minute=0, timezone=IST
            ),
            id="yf_price",
            name="Yahoo Finance price ingestion",
        ),
        # Technical indicators computed after price data is populated
        dict(
            func=lambda: TechnicalIndicatorsPipeline(db_factory()).run(),
            trigger=CronTrigger(
                day_of_week="mon-fri", hour=20, minute=0, timezone=IST
            ),
            id="technical_indicators",
            name="Technical indicators computation",
        ),
        # Screener scrape is weekly — rate-limit friendly, quarterly data anyway
        dict(
            func=lambda: ScreenerFundamentalsPipeline(db_factory()).run(),
            trigger=CronTrigger(
                day_of_week="sun", hour=6, minute=0, timezone=IST
            ),
            id="screener_fundamentals",
            name="Screener financial statements scrape",
        ),
        # Ratings computed after technical indicators (which depend on prices)
        dict(
            func=lambda: StockRatingsPipeline(db_factory()).run(),
            trigger=CronTrigger(hour=21, minute=0, timezone=IST),
            id="stock_ratings",
            name="Stock ratings and fundamental scores",
        ),
    ]

    for job in jobs:
        scheduler.add_job(
            **job,
            replace_existing=True,
            misfire_grace_time=600,   # Allow 10 min late start before skipping
            coalesce=True,            # If missed multiple fires, run only once
        )
        logger.info(f"Registered pipeline job: {job['id']}")
```

### Update `app/main.py` lifespan

```python
# app/main.py — update the existing lifespan function

from contextlib import asynccontextmanager
from .pipelines.scheduler import scheduler, register_all_jobs
from .database import AsyncSessionLocal

@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB connectivity check (from Phase 2 — keep as-is)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Supabase connection OK")
    except Exception as e:
        logger.warning(f"DB connection failed on startup: {e}")

    # Register and start the scheduler
    register_all_jobs(db_factory=AsyncSessionLocal)
    scheduler.start()
    logger.info(f"Scheduler started — {len(scheduler.get_jobs())} jobs registered")

    yield

    # Graceful shutdown
    scheduler.shutdown(wait=False)
    await engine.dispose()
    logger.info("Scheduler stopped, engine disposed")
```

---

## Task 3.2 — Pipeline Base Class

**File:** `app/pipelines/base.py` (new)
**Estimated time:** 1 hour

This class handles all `EtlRun` lifecycle management. Every pipeline extends it and only implements `execute()`. This ensures every pipeline logs consistently to `etl_runs` without repeating boilerplate.

```python
# app/pipelines/base.py
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from ..crud import start_etl_run, finish_etl_run

logger = logging.getLogger(__name__)


class PipelineResult:
    """Returned by every pipeline's execute() method."""
    def __init__(
        self,
        records_in: int = 0,
        records_out: int = 0,
        error_msg: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        self.records_in  = records_in
        self.records_out = records_out
        self.error_msg   = error_msg
        self.metadata    = metadata or {}
        self.success     = error_msg is None


class BasePipeline(ABC):
    """
    Base class for all ingestion pipelines.

    Subclasses implement execute() only.
    BasePipeline handles EtlRun creation, status updates, and exception catching.

    Usage:
        class AmfiNavPipeline(BasePipeline):
            pipeline_name = "amfi_nav"

            async def execute(self) -> PipelineResult:
                # fetch + upsert logic here
                return PipelineResult(records_in=500, records_out=500)
    """

    # Subclasses must set this — must match the id used in scheduler.py
    pipeline_name: str = ""

    def __init__(self, db: AsyncSession, entity_id: Optional[str] = None,
                 triggered_by: str = "scheduler"):
        self.db           = db
        self.entity_id    = entity_id
        self.triggered_by = triggered_by
        self._run_id: Optional[int] = None

    @abstractmethod
    async def execute(self) -> PipelineResult:
        """
        Core pipeline logic. Implemented by each subclass.
        Must return a PipelineResult.
        Must NOT catch its own top-level exceptions — BasePipeline handles that.
        """
        ...

    async def run(self) -> PipelineResult:
        """
        Entry point called by the scheduler or manual trigger endpoint.
        Wraps execute() with EtlRun logging.
        """
        # Start run
        run, created = await start_etl_run(
            self.db,
            pipeline_name=self.pipeline_name,
            entity_id=self.entity_id,
            triggered_by=self.triggered_by,
        )
        if not created:
            logger.warning(
                f"[{self.pipeline_name}] already RUNNING (run_id={run.id}) — skipping"
            )
            return PipelineResult(error_msg="Already running")

        self._run_id = run.id
        logger.info(f"[{self.pipeline_name}] started (run_id={run.id})")

        try:
            result = await self.execute()
            status = "COMPLETED" if result.success else "PARTIAL"
        except Exception as exc:
            logger.exception(f"[{self.pipeline_name}] unhandled exception")
            result = PipelineResult(error_msg=str(exc)[:1000])
            status = "FAILED"

        # Finish run
        await finish_etl_run(
            self.db,
            run_id=self._run_id,
            status=status,
            records_in=result.records_in,
            records_out=result.records_out,
            error_msg=result.error_msg,
            metadata=result.metadata,
        )
        logger.info(
            f"[{self.pipeline_name}] {status} — "
            f"in={result.records_in} out={result.records_out}"
        )

        await self.db.close()
        return result
```

---

## Task 3.3 — AMFI NAV Pipeline

**File:** `app/pipelines/amfi_nav.py` (new)
**Target tables:** `fund_master`, `fund_nav_history`
**Existing CRUD used:** `bulk_insert_fund_navs` (crud.py line 379) — reused exactly
**Estimated time:** 2 hours

### Data source

AMFI publishes `NAVAll.txt` at `https://www.amfiindia.com/spages/NAVAll.txt` daily by ~21:00 IST. Free, no authentication, no rate limit. The existing code already has a bulk upsert for `fund_nav_history` — this pipeline just wraps it in the scheduler framework.

```python
# app/pipelines/amfi_nav.py
import httpx
import logging
from datetime import date
from .base import BasePipeline, PipelineResult
from ..crud import bulk_insert_fund_navs, get_fund_master_by_code
from ..models import FundMaster
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"


class AmfiNavPipeline(BasePipeline):
    pipeline_name = "amfi_nav"

    async def execute(self) -> PipelineResult:
        # ── Fetch NAVAll.txt ──────────────────────────────────────────────────
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(AMFI_URL)
            resp.raise_for_status()

        lines = resp.text.strip().splitlines()
        records_in = len(lines)

        # ── Parse the fixed format ────────────────────────────────────────────
        # NAVAll.txt format:
        # Scheme Code;ISIN Div Payout/IDCW;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
        # 119551;;INF209KB1UW3;SBI PSU Fund - Direct Plan - IDCW;24.5870;14-May-2026
        fund_rows   = []   # new/updated fund_master rows
        nav_entries = {}   # {scheme_code: {date_str: nav_value}}

        today = date.today()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("Scheme Code"):
                continue

            parts = line.split(";")
            if len(parts) < 6:
                continue

            try:
                scheme_code = parts[0].strip()
                isin        = parts[2].strip() or parts[1].strip() or None
                scheme_name = parts[3].strip()
                nav_str     = parts[4].strip()
                date_str    = parts[5].strip()   # DD-Mon-YYYY format

                nav_value = float(nav_str)
                if nav_value <= 0:
                    continue

                # Parse date: "14-May-2026" → "2026-05-14"
                nav_date = date.strftime(
                    date.fromisoformat(
                        "-".join(reversed(date_str.split("-")))
                            .replace("Jan","01").replace("Feb","02")
                            .replace("Mar","03").replace("Apr","04")
                            .replace("May","05").replace("Jun","06")
                            .replace("Jul","07").replace("Aug","08")
                            .replace("Sep","09").replace("Oct","10")
                            .replace("Nov","11").replace("Dec","12")
                    ),
                    "%Y-%m-%d"
                )

                nav_entries.setdefault(scheme_code, {})[nav_date] = nav_value

            except (ValueError, IndexError):
                continue

        # ── Upsert NAV history using existing crud function ───────────────────
        records_out = 0
        for scheme_code, nav_data in nav_entries.items():
            inserted = await bulk_insert_fund_navs(self.db, scheme_code, nav_data)
            records_out += inserted

        return PipelineResult(
            records_in=records_in,
            records_out=records_out,
            metadata={"nav_date": str(today), "scheme_count": len(nav_entries)},
        )
```

---

## Task 3.4 — Benchmark NAV Pipeline

**File:** `app/pipelines/benchmark_nav.py` (new)
**Target tables:** `benchmark_nav_history`, `benchmark_metrics` (partial)
**Existing CRUD used:** `bulk_insert_benchmark_navs` (crud.py line 408) — reused exactly
**Estimated time:** 1.5 hours

```python
# app/pipelines/benchmark_nav.py
import httpx
import logging
from datetime import date
from .base import BasePipeline, PipelineResult
from ..crud import bulk_insert_benchmark_navs, get_all_benchmark_masters

logger = logging.getLogger(__name__)


class BenchmarkNavPipeline(BasePipeline):
    pipeline_name = "benchmark_nav"

    # mftool-compatible NSE index codes → stored benchmark_codes
    # These match whatever benchmark_codes are in your benchmark_master table
    INDEX_URLS = {
        "NIFTY50":      "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI",
        "SENSEX":       "https://query1.finance.yahoo.com/v8/finance/chart/%5EBSESN",
        "NIFTYNEXT50":  "https://query1.finance.yahoo.com/v8/finance/chart/%5ENIFMDCP50",
        "NIFTYBANK":    "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEBANK",
        "NIFTYIT":      "https://query1.finance.yahoo.com/v8/finance/chart/%5ECNXIT",
        "NIFTYMIDCAP":  "https://query1.finance.yahoo.com/v8/finance/chart/%5ECNXMIDCAP",
        "NIFTYSMALLCAP":"https://query1.finance.yahoo.com/v8/finance/chart/%5ECNXSMALLCAP",
    }

    async def execute(self) -> PipelineResult:
        # Fetch active benchmarks from DB to know which ones to pull
        benchmarks, _ = await get_all_benchmark_masters(self.db, is_active=True)
        active_codes = {b.benchmark_code for b in benchmarks}

        records_in = 0
        records_out = 0

        async with httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"}
        ) as client:
            for code, url in self.INDEX_URLS.items():
                if code not in active_codes:
                    continue

                try:
                    resp = await client.get(url, params={
                        "interval": "1d",
                        "range": "5d",   # Last 5 days — catches any missed days
                    })
                    resp.raise_for_status()
                    data = resp.json()

                    timestamps = data["chart"]["result"][0]["timestamp"]
                    closes     = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]

                    nav_data = {}
                    for ts, close in zip(timestamps, closes):
                        if close is None:
                            continue
                        d = date.fromtimestamp(ts).isoformat()
                        nav_data[d] = round(float(close), 4)
                        records_in += 1

                    inserted = await bulk_insert_benchmark_navs(self.db, code, nav_data)
                    records_out += inserted

                except Exception as e:
                    logger.warning(f"[benchmark_nav] failed for {code}: {e}")
                    # Continue with other benchmarks — partial is acceptable
                    continue

        return PipelineResult(
            records_in=records_in,
            records_out=records_out,
            metadata={"benchmarks_attempted": len(self.INDEX_URLS)},
        )
```

---

## Task 3.5 — Fund Metrics Recompute Pipeline

**File:** `app/pipelines/fund_metrics.py` (new)
**Target tables:** `fund_metrics`, `benchmark_metrics`
**Existing CRUD used:** `upsert_fund_metrics`, `upsert_benchmark_metrics` (crud.py lines 487–509) — reused exactly
**Estimated time:** 2 hours

This pipeline is a promotion of whatever `recompute_funds_metrics.py` script already exists in the repo. The analytics logic (Sharpe, Sortino, Alpha, Beta, CAGR, drawdown) stays exactly where it is. This file only wraps it in `BasePipeline`.

```python
# app/pipelines/fund_metrics.py
import logging
import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Optional
from sqlalchemy import select
from .base import BasePipeline, PipelineResult
from ..crud import upsert_fund_metrics, upsert_benchmark_metrics, get_all_fund_masters
from ..models import FundNavHistory, BenchmarkNavHistory, FundMaster

logger = logging.getLogger(__name__)

RISK_FREE_RATE_ANNUAL = 0.065   # 6.5% — approximate Indian T-bill rate


class FundMetricsPipeline(BasePipeline):
    pipeline_name = "fund_metrics"

    async def execute(self) -> PipelineResult:
        records_in  = 0
        records_out = 0
        today       = date.today()

        # ── Get all active funds ──────────────────────────────────────────────
        funds = await get_all_fund_masters(self.db, is_active=True, limit=99999)
        records_in = len(funds)

        for fund in funds:
            try:
                metrics = await self._compute_fund_metrics(fund, today)
                if metrics:
                    await upsert_fund_metrics(self.db, metrics)
                    records_out += 1
            except Exception as e:
                logger.warning(
                    f"[fund_metrics] failed for {fund.scheme_code}: {e}"
                )
                continue   # PARTIAL — skip bad fund, continue with others

        return PipelineResult(
            records_in=records_in,
            records_out=records_out,
        )

    async def _compute_fund_metrics(
        self, fund: FundMaster, as_of: date
    ) -> Optional[dict]:
        """
        Fetch NAV history and compute all metrics for a single fund.
        Returns dict ready for upsert_fund_metrics, or None if insufficient data.

        This wraps whatever analytics logic already exists in the codebase.
        The calculation logic is NOT changed — only the wrapping is new.
        """
        # Fetch last 5 years of NAV
        cutoff = as_of - timedelta(days=365 * 5 + 30)
        result = await self.db.execute(
            select(FundNavHistory)
            .where(
                FundNavHistory.scheme_code == fund.scheme_code,
                FundNavHistory.nav_date >= cutoff,
            )
            .order_by(FundNavHistory.nav_date.asc())
        )
        nav_rows = result.scalars().all()

        if len(nav_rows) < 252:   # Need at least 1 year of data
            return None

        navs  = pd.Series(
            [float(r.nav_value) for r in nav_rows],
            index=[r.nav_date for r in nav_rows],
        )
        daily_returns = navs.pct_change().dropna()

        # ── Core metrics (reuse existing analytics logic) ─────────────────────
        metrics = {
            "scheme_code":    fund.scheme_code,
            "current_nav":    float(navs.iloc[-1]),
            "nav_date":       navs.index[-1],
            "has_sufficient_data": True,
            "data_completeness_percentage": min(100.0, len(nav_rows) / (252*5) * 100),
            "calculation_period_start_date": navs.index[0],
            "calculation_period_end_date":   navs.index[-1],
        }

        # Returns
        metrics.update(self._compute_returns(navs))

        # Risk metrics
        ann_ret   = daily_returns.mean() * 252
        ann_std   = daily_returns.std()  * np.sqrt(252)
        rf_daily  = RISK_FREE_RATE_ANNUAL / 252
        excess    = daily_returns - rf_daily

        metrics["standard_deviation"] = round(float(ann_std), 4) if ann_std else None
        metrics["sharpe_ratio"] = (
            round(float(excess.mean() / excess.std() * np.sqrt(252)), 4)
            if excess.std() > 0 else None
        )

        downside = daily_returns[daily_returns < rf_daily]
        downside_std = downside.std() * np.sqrt(252) if len(downside) > 0 else None
        metrics["sortino_ratio"] = (
            round(float((ann_ret - RISK_FREE_RATE_ANNUAL) / downside_std), 4)
            if downside_std and downside_std > 0 else None
        )

        # Max drawdown
        cumulative = (1 + daily_returns).cumprod()
        rolling_max = cumulative.cummax()
        drawdowns = (cumulative - rolling_max) / rolling_max
        metrics["maximum_drawdown"] = round(float(drawdowns.min()), 4)

        # Volatility (annualised)
        metrics["volatility"] = metrics["standard_deviation"]

        # Benchmark-relative metrics (alpha, beta, tracking error) if benchmark exists
        if fund.benchmark_index_code:
            bm_metrics = await self._compute_benchmark_relative(
                daily_returns, fund.benchmark_index_code, navs.index[0], navs.index[-1]
            )
            metrics.update(bm_metrics)

        return metrics

    def _compute_returns(self, navs: pd.Series) -> dict:
        """Absolute and CAGR returns at standard horizons."""
        latest    = float(navs.iloc[-1])
        as_of     = navs.index[-1]
        returns   = {}

        def _return_since(days: int, key: str, cagr_key: Optional[str] = None):
            cutoff = as_of - timedelta(days=days)
            past = navs[navs.index <= cutoff]
            if past.empty:
                returns[key] = None
                if cagr_key:
                    returns[cagr_key] = None
                return
            past_nav = float(past.iloc[-1])
            abs_ret  = round((latest - past_nav) / past_nav * 100, 4)
            returns[key] = abs_ret
            if cagr_key:
                years = days / 365
                cagr  = round(((latest / past_nav) ** (1/years) - 1) * 100, 4)
                returns[cagr_key] = cagr

        _return_since(180,  "short_term_return_6m")
        _return_since(365,  "absolute_return_1y")
        _return_since(365*3,"absolute_return_3y", "cagr_3year")
        _return_since(365*5,"absolute_return_5y", "cagr_5year")
        _return_since(365*10,"absolute_return_10y")
        return returns

    async def _compute_benchmark_relative(
        self, fund_returns: pd.Series,
        benchmark_code: str,
        start: date, end: date,
    ) -> dict:
        """Alpha, beta, tracking error, information ratio, capture ratios."""
        result = await self.db.execute(
            select(BenchmarkNavHistory)
            .where(
                BenchmarkNavHistory.benchmark_code == benchmark_code,
                BenchmarkNavHistory.nav_date.between(start, end),
            )
            .order_by(BenchmarkNavHistory.nav_date.asc())
        )
        bm_rows = result.scalars().all()
        if len(bm_rows) < 60:
            return {}

        bm_navs    = pd.Series(
            [float(r.index_value) for r in bm_rows],
            index=[r.nav_date for r in bm_rows],
        )
        bm_returns = bm_navs.pct_change().dropna()

        # Align on common dates
        aligned = pd.DataFrame({"fund": fund_returns, "bm": bm_returns}).dropna()
        if len(aligned) < 60:
            return {}

        f, b    = aligned["fund"], aligned["bm"]
        cov     = f.cov(b)
        var_bm  = b.var()
        beta    = round(float(cov / var_bm), 4) if var_bm > 0 else None
        alpha   = None
        if beta is not None:
            ann_fund  = f.mean() * 252
            ann_bm    = b.mean() * 252
            alpha = round(float(ann_fund - (RISK_FREE_RATE_ANNUAL + beta * (ann_bm - RISK_FREE_RATE_ANNUAL))), 4)

        te = round(float((f - b).std() * np.sqrt(252)), 4)
        ir = None
        if te and te > 0:
            ir = round(float((f.mean() - b.mean()) * 252 / te), 4)

        # Capture ratios
        up_months   = aligned[b > 0]
        down_months = aligned[b < 0]
        up_capture  = round(float(up_months["fund"].mean() / up_months["bm"].mean() * 100), 4) \
                      if not up_months.empty and up_months["bm"].mean() != 0 else None
        down_capture = round(float(down_months["fund"].mean() / down_months["bm"].mean() * 100), 4) \
                       if not down_months.empty and down_months["bm"].mean() != 0 else None

        return {
            "alpha":           alpha,
            "beta":            beta,
            "tracking_error":  te,
            "information_ratio": ir,
            "upside_capture":  up_capture,
            "downside_capture": down_capture,
        }
```

---

## Task 3.6 — Yahoo Finance Price Pipeline

**File:** `app/pipelines/yf_price.py` (new)
**Target tables:** `price_data`
**New CRUD needed:** `upsert_price_data` — add to crud.py
**Estimated time:** 2 hours

### New CRUD function to add to `crud.py`

```python
# Add to crud.py

from .models import PriceData, Stock

async def upsert_price_data(session: AsyncSession, rows: list[dict]) -> int:
    """
    Bulk upsert rows into price_data.
    rows: list of dicts with keys: stock_id, price_date, open, high, low, close, adj_close, volume
    Uses ON CONFLICT DO UPDATE — same pattern as bulk_insert_fund_navs.
    """
    if not rows:
        return 0
    stmt = pg_insert(PriceData).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_price_data_stock_date",
        set_={
            "open":      stmt.excluded.open,
            "high":      stmt.excluded.high,
            "low":       stmt.excluded.low,
            "close":     stmt.excluded.close,
            "adj_close": stmt.excluded.adj_close,
            "volume":    stmt.excluded.volume,
        }
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)


async def get_active_stocks(session: AsyncSession) -> list[Stock]:
    """Return all active, non-index stocks ordered by symbol."""
    result = await session.execute(
        select(Stock)
        .where(Stock.is_active == True, Stock.is_index == False)
        .order_by(Stock.symbol)
    )
    return result.scalars().all()


async def get_stock_by_symbol(session: AsyncSession, symbol: str) -> Optional[Stock]:
    result = await session.execute(
        select(Stock).where(Stock.symbol == symbol)
    )
    return result.scalar_one_or_none()
```

### Pipeline

```python
# app/pipelines/yf_price.py
import yfinance as yf
import logging
from datetime import date, timedelta
from sqlalchemy import select, func
from .base import BasePipeline, PipelineResult
from ..crud import upsert_price_data, get_active_stocks
from ..models import PriceData

logger = logging.getLogger(__name__)

BATCH_SIZE = 50   # Fetch this many stocks per yfinance call to stay within rate limits


class YfPricePipeline(BasePipeline):
    pipeline_name = "yf_price"

    async def execute(self) -> PipelineResult:
        stocks      = await get_active_stocks(self.db)
        records_in  = 0
        records_out = 0

        # ── Find watermark: earliest last-price date across all stocks ────────
        # Pull only missing days, not full history every time
        result = await self.db.execute(
            select(func.max(PriceData.price_date))
        )
        last_date = result.scalar()
        start_date = (last_date + timedelta(days=1)) if last_date else \
                     (date.today() - timedelta(days=365 * 2))

        if start_date > date.today():
            return PipelineResult(
                records_in=0, records_out=0,
                metadata={"reason": "price_data already up to date"},
            )

        # ── Build symbol → stock_id map ───────────────────────────────────────
        symbol_map = {s.yf_symbol: s.id for s in stocks}

        # ── Batch fetch via yfinance ──────────────────────────────────────────
        yf_symbols = list(symbol_map.keys())

        for i in range(0, len(yf_symbols), BATCH_SIZE):
            batch = yf_symbols[i : i + BATCH_SIZE]
            try:
                # yfinance download: returns multi-level DataFrame
                df = yf.download(
                    tickers=batch,
                    start=start_date.isoformat(),
                    end=date.today().isoformat(),
                    auto_adjust=True,
                    progress=False,
                    threads=False,   # Avoid threading issues with async
                    group_by="ticker",
                )

                if df.empty:
                    continue

                rows = []
                for yf_sym in batch:
                    if yf_sym not in symbol_map:
                        continue
                    stock_id = symbol_map[yf_sym]

                    # Single ticker: df columns are flat; multi: df[yf_sym]
                    ticker_df = df[yf_sym] if len(batch) > 1 else df
                    if ticker_df.empty:
                        continue

                    for price_date, row in ticker_df.iterrows():
                        if row.get("Close") is None:
                            continue
                        records_in += 1
                        rows.append({
                            "stock_id":   stock_id,
                            "price_date": price_date.date(),
                            "open":       round(float(row.get("Open",  0) or 0), 4),
                            "high":       round(float(row.get("High",  0) or 0), 4),
                            "low":        round(float(row.get("Low",   0) or 0), 4),
                            "close":      round(float(row["Close"]),              4),
                            "adj_close":  round(float(row["Close"]),              4),
                            "volume":     int(row.get("Volume", 0) or 0),
                        })

                if rows:
                    inserted = await upsert_price_data(self.db, rows)
                    records_out += inserted

            except Exception as e:
                logger.warning(f"[yf_price] batch {i//BATCH_SIZE + 1} failed: {e}")
                continue

        return PipelineResult(
            records_in=records_in,
            records_out=records_out,
            metadata={
                "start_date":    str(start_date),
                "stocks_count":  len(stocks),
                "batch_size":    BATCH_SIZE,
            },
        )
```

---

## Task 3.7 — Technical Indicators Pipeline

**File:** `app/pipelines/technical_indicators.py` (new)
**Target tables:** `technical_indicators`
**New CRUD needed:** `upsert_technical_indicators` — add to crud.py
**Estimated time:** 2.5 hours

### New CRUD function to add to `crud.py`

```python
# Add to crud.py

from .models import TechnicalIndicator

async def upsert_technical_indicators(session: AsyncSession, rows: list[dict]) -> int:
    """Bulk upsert technical indicator rows. Conflict key: (stock_id, ind_date, timeframe)."""
    if not rows:
        return 0
    stmt = pg_insert(TechnicalIndicator).values(rows)
    update_cols = {
        col: getattr(stmt.excluded, col)
        for col in rows[0].keys()
        if col not in ("stock_id", "ind_date", "timeframe")
    }
    stmt = stmt.on_conflict_do_update(
        constraint="uq_technical_indicator_stock_date_tf",
        set_=update_cols,
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)


async def get_price_data_for_ta(
    session: AsyncSession, stock_id: int, lookback_days: int = 260
) -> list:
    """Fetch recent price rows for a single stock for TA computation."""
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=lookback_days)
    result = await session.execute(
        select(PriceData)
        .where(PriceData.stock_id == stock_id, PriceData.price_date >= cutoff)
        .order_by(PriceData.price_date.asc())
    )
    return result.scalars().all()
```

### Pipeline

```python
# app/pipelines/technical_indicators.py
import pandas as pd
import pandas_ta as ta
import numpy as np
import logging
from datetime import date, timedelta
from .base import BasePipeline, PipelineResult
from ..crud import get_active_stocks, get_price_data_for_ta, upsert_technical_indicators
from ..models import PriceData

logger = logging.getLogger(__name__)

TIMEFRAME = "1d"
LOOKBACK  = 260   # Trading days — enough for SMA200 + some history


class TechnicalIndicatorsPipeline(BasePipeline):
    pipeline_name = "technical_indicators"

    async def execute(self) -> PipelineResult:
        stocks      = await get_active_stocks(self.db)
        records_in  = 0
        records_out = 0
        today       = date.today()

        for stock in stocks:
            try:
                price_rows = await get_price_data_for_ta(self.db, stock.id, LOOKBACK)
                if len(price_rows) < 30:   # Not enough history for meaningful indicators
                    continue

                records_in += len(price_rows)

                # Build OHLCV DataFrame — pandas-ta needs this exact structure
                df = pd.DataFrame({
                    "date":   [r.price_date for r in price_rows],
                    "open":   [float(r.open  or 0) for r in price_rows],
                    "high":   [float(r.high  or 0) for r in price_rows],
                    "low":    [float(r.low   or 0) for r in price_rows],
                    "close":  [float(r.close)      for r in price_rows],
                    "volume": [int(r.volume  or 0)  for r in price_rows],
                }).set_index("date")

                # ── Compute all indicators via pandas-ta ──────────────────────
                df.ta.sma(length=20,  append=True)
                df.ta.sma(length=50,  append=True)
                df.ta.sma(length=200, append=True)
                df.ta.ema(length=9,   append=True)
                df.ta.ema(length=21,  append=True)
                df.ta.ema(length=50,  append=True)
                df.ta.rsi(length=14,  append=True)
                df.ta.macd(fast=12, slow=26, signal=9, append=True)
                df.ta.bbands(length=20, append=True)
                df.ta.atr(length=14,  append=True)
                df.ta.adx(length=14,  append=True)
                df.ta.stoch(k=14, d=3, append=True)
                df.ta.obv(append=True)
                df.ta.cci(length=20,  append=True)
                df.ta.willr(length=14, append=True)
                df.ta.roc(length=14,  append=True)

                # Volume SMAs (not in pandas-ta — compute manually)
                df["volume_sma_20"] = df["volume"].rolling(20).mean()
                df["volume_sma_50"] = df["volume"].rolling(50).mean()
                df["volume_ratio"]  = df["volume"] / df["volume_sma_20"].replace(0, np.nan)

                # 52-week high/low distance
                rolling_52w_high = df["high"].rolling(252).max()
                rolling_52w_low  = df["low"].rolling(252).min()
                df["pct_from_52w_high"] = (df["close"] - rolling_52w_high) / rolling_52w_high * 100
                df["pct_from_52w_low"]  = (df["close"] - rolling_52w_low)  / rolling_52w_low  * 100

                # ── Compute vwap_20 (rolling 20-day VWAP) ────────────────────
                typical_price = (df["high"] + df["low"] + df["close"]) / 3
                df["vwap_20"] = (typical_price * df["volume"]).rolling(20).sum() / \
                                df["volume"].rolling(20).sum()

                # ── Beta vs Nifty (1Y) and RS 6M — computed from benchmark ───
                # Skipped here for simplicity; computed in stock_ratings pipeline
                # which has access to benchmark data

                # ── Write today's row only (avoid re-writing all history) ─────
                latest = df.iloc[-1]
                if pd.isna(latest["close"]):
                    continue

                def safe(val):
                    """Convert to Python float or None."""
                    if val is None or pd.isna(val):
                        return None
                    return round(float(val), 4)

                row = {
                    "stock_id":          stock.id,
                    "ind_date":          today,
                    "timeframe":         TIMEFRAME,
                    "sma_20":            safe(latest.get("SMA_20")),
                    "sma_50":            safe(latest.get("SMA_50")),
                    "sma_200":           safe(latest.get("SMA_200")),
                    "ema_9":             safe(latest.get("EMA_9")),
                    "ema_21":            safe(latest.get("EMA_21")),
                    "ema_50":            safe(latest.get("EMA_50")),
                    "rsi_14":            safe(latest.get("RSI_14")),
                    "macd_line":         safe(latest.get("MACD_12_26_9")),
                    "macd_signal":       safe(latest.get("MACDs_12_26_9")),
                    "macd_hist":         safe(latest.get("MACDh_12_26_9")),
                    "bb_upper":          safe(latest.get("BBU_20_2.0")),
                    "bb_middle":         safe(latest.get("BBM_20_2.0")),
                    "bb_lower":          safe(latest.get("BBL_20_2.0")),
                    "atr_14":            safe(latest.get("ATRr_14")),
                    "adx_14":            safe(latest.get("ADX_14")),
                    "stoch_k":           safe(latest.get("STOCHk_14_3_3")),
                    "stoch_d":           safe(latest.get("STOCHd_14_3_3")),
                    "volume_sma_20":     int(latest["volume_sma_20"]) if not pd.isna(latest["volume_sma_20"]) else None,
                    "volume_sma_50":     int(latest["volume_sma_50"]) if not pd.isna(latest["volume_sma_50"]) else None,
                    "volume_ratio":      safe(latest.get("volume_ratio")),
                    "obv":               int(latest["OBV"]) if not pd.isna(latest.get("OBV", float("nan"))) else None,
                    "vwap_20":           safe(latest.get("vwap_20")),
                    "cci_20":            safe(latest.get("CCI_20_0.015")),
                    "williams_r":        safe(latest.get("WILLR_14")),
                    "roc_14":            safe(latest.get("ROC_14")),
                    "pct_from_52w_high": safe(latest.get("pct_from_52w_high")),
                    "pct_from_52w_low":  safe(latest.get("pct_from_52w_low")),
                    # beta_1y and rs_6m_vs_nifty: populated by stock_ratings pipeline
                    "beta_1y":           None,
                    "rs_6m_vs_nifty":    None,
                }

                await upsert_technical_indicators(self.db, [row])
                records_out += 1

            except Exception as e:
                logger.warning(f"[technical_indicators] failed for {stock.symbol}: {e}")
                continue

        return PipelineResult(records_in=records_in, records_out=records_out)
```

---

## Task 3.8 — Screener Financial Statements Pipeline

**File:** `app/pipelines/screener_fundamentals.py` (new)
**Target tables:** `financial_statements`, `financial_ratios`, `shareholding_pattern`
**New CRUD needed:** `upsert_financial_statement`, `upsert_financial_ratios`, `upsert_shareholding`
**Estimated time:** 3 hours

> This is the highest-risk pipeline. Screener.in's HTML structure can change. The `raw_checksum` field on `FinancialStatement` shows the existing code already handles this — we preserve that pattern.

### New CRUD functions to add to `crud.py`

```python
# Add to crud.py

from .models import FinancialStatement, FinancialRatio, ShareholdingPattern
import hashlib, json

async def upsert_financial_statement(session: AsyncSession, row: dict) -> bool:
    """
    Upsert one financial statement row.
    Uses raw_checksum to skip unchanged data — avoids unnecessary writes.
    Returns True if inserted/updated, False if skipped (checksum match).
    """
    checksum = hashlib.md5(json.dumps(row["data"], sort_keys=True).encode()).hexdigest()

    # Check existing checksum
    existing = await session.execute(
        select(FinancialStatement).where(
            FinancialStatement.stock_id      == row["stock_id"],
            FinancialStatement.statement_type == row["statement_type"],
            FinancialStatement.period_type   == row["period_type"],
            FinancialStatement.period_end    == row["period_end"],
        )
    )
    existing_row = existing.scalar_one_or_none()
    if existing_row and existing_row.raw_checksum == checksum:
        return False   # Unchanged — skip write

    row["raw_checksum"] = checksum
    stmt = pg_insert(FinancialStatement).values(row)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_financial_stmt_stock_type_period",
        set_={
            "data":         stmt.excluded.data,
            "raw_data":     stmt.excluded.raw_data,
            "raw_checksum": stmt.excluded.raw_checksum,
            "scraped_at":   func.now(),
        }
    )
    await session.execute(stmt)
    await session.commit()
    return True


async def upsert_financial_ratios(session: AsyncSession, row: dict) -> int:
    stmt = pg_insert(FinancialRatio).values(row)
    update_cols = {k: getattr(stmt.excluded, k) for k in row if k not in
                   ("stock_id", "period_end", "period_type")}
    stmt = stmt.on_conflict_do_update(
        constraint="uq_financial_ratios_stock_period_type",
        set_=update_cols,
    )
    await session.execute(stmt)
    await session.commit()
    return 1


async def upsert_shareholding(session: AsyncSession, row: dict) -> int:
    stmt = pg_insert(ShareholdingPattern).values(row)
    update_cols = {k: getattr(stmt.excluded, k) for k in row
                   if k not in ("stock_id", "period_end")}
    stmt = stmt.on_conflict_do_update(
        constraint="uq_shareholding_pattern_stock_period",
        set_=update_cols,
    )
    await session.execute(stmt)
    await session.commit()
    return 1
```

### Pipeline

```python
# app/pipelines/screener_fundamentals.py
import httpx
import json
import logging
import re
from datetime import date
from bs4 import BeautifulSoup
from .base import BasePipeline, PipelineResult
from ..crud import (
    get_active_stocks, upsert_financial_statement,
    upsert_financial_ratios, upsert_shareholding
)

logger = logging.getLogger(__name__)

SCREENER_BASE    = "https://www.screener.in/company"
REQUEST_DELAY_S  = 3.0   # Be polite — Screener rate-limits aggressively
BATCH_PAUSE_S    = 30    # Pause between batches of 10 stocks


class ScreenerFundamentalsPipeline(BasePipeline):
    pipeline_name = "screener_fundamentals"

    async def execute(self) -> PipelineResult:
        import asyncio

        stocks      = await get_active_stocks(self.db)
        records_in  = len(stocks)
        records_out = 0

        async with httpx.AsyncClient(
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
            },
            follow_redirects=True,
        ) as client:

            for i, stock in enumerate(stocks):
                if not stock.screener_slug:
                    continue

                try:
                    # ── Fetch Screener consolidated page ─────────────────────
                    url  = f"{SCREENER_BASE}/{stock.screener_slug}/consolidated/"
                    resp = await client.get(url)
                    if resp.status_code == 404:
                        url  = f"{SCREENER_BASE}/{stock.screener_slug}/"
                        resp = await client.get(url)
                    resp.raise_for_status()

                    soup = BeautifulSoup(resp.text, "html.parser")

                    # ── Financial statements ──────────────────────────────────
                    for stmt_type, section_id in [
                        ("PL", "profit-loss"),
                        ("BS", "balance-sheet"),
                        ("CF", "cash-flow"),
                    ]:
                        section = soup.find(id=section_id)
                        if not section:
                            continue

                        parsed = self._parse_screener_table(section)
                        if not parsed:
                            continue

                        # Each period column becomes one row in financial_statements
                        for period_label, line_items in parsed.items():
                            period_end = self._parse_period(period_label)
                            if not period_end:
                                continue

                            written = await upsert_financial_statement(self.db, {
                                "stock_id":       stock.id,
                                "statement_type": stmt_type,
                                "period_type":    "annual",
                                "period_end":     period_end,
                                "currency":       "INR",
                                "data":           line_items,
                                "raw_data":       None,
                            })
                            if written:
                                records_out += 1

                    # ── Ratios (from the key metrics / ratios section) ─────────
                    ratios = self._parse_ratios(soup, stock.id)
                    if ratios:
                        await upsert_financial_ratios(self.db, ratios)
                        records_out += 1

                    # ── Shareholding pattern ───────────────────────────────────
                    shareholding = self._parse_shareholding(soup, stock.id)
                    if shareholding:
                        await upsert_shareholding(self.db, shareholding)
                        records_out += 1

                except Exception as e:
                    logger.warning(
                        f"[screener] failed for {stock.symbol} "
                        f"(slug={stock.screener_slug}): {e}"
                    )

                # Rate limiting — be respectful
                await asyncio.sleep(REQUEST_DELAY_S)
                if (i + 1) % 10 == 0:
                    logger.info(f"[screener] {i+1}/{len(stocks)} done — pausing")
                    await asyncio.sleep(BATCH_PAUSE_S)

        return PipelineResult(records_in=records_in, records_out=records_out)

    def _parse_screener_table(self, section) -> dict:
        """Parse a Screener table section into {period: {line_item: value}}."""
        result = {}
        table = section.find("table")
        if not table:
            return result

        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True)
            for j, cell in enumerate(cells[1:], 1):
                if j >= len(headers):
                    break
                period = headers[j]
                val_str = cell.get_text(strip=True).replace(",", "")
                try:
                    val = float(val_str)
                except ValueError:
                    val = val_str
                result.setdefault(period, {})[label] = val
        return result

    def _parse_ratios(self, soup, stock_id: int) -> dict | None:
        """Extract key ratios from the Screener ratios section."""
        # Screener exposes key ratios in #top-ratios or .company-ratios
        ratios = {"stock_id": stock_id, "period_end": date.today(),
                  "period_type": "annual"}
        try:
            top = soup.find(id="top-ratios") or soup.find(class_="company-ratios")
            if not top:
                return None
            for li in top.find_all("li"):
                name = li.find("span", class_="name")
                val  = li.find("span", class_="value") or li.find("span", class_="number")
                if not name or not val:
                    continue
                key = name.get_text(strip=True).lower()
                raw = val.get_text(strip=True).replace(",","").replace("%","")
                try:
                    num = float(raw)
                except ValueError:
                    continue
                # Map Screener labels → column names
                mapping = {
                    "p/e": "pe_ratio", "p/b": "pb_ratio", "market cap": "market_cap",
                    "roe": "roe", "roce": "roce", "dividend yield": "dividend_yield",
                    "debt / equity": "debt_equity", "current ratio": "current_ratio",
                    "eps": "eps", "book value": "book_value_ps",
                }
                col = mapping.get(key)
                if col:
                    ratios[col] = num
        except Exception:
            return None
        return ratios if len(ratios) > 3 else None

    def _parse_shareholding(self, soup, stock_id: int) -> dict | None:
        """Extract promoter/FII/DII/public holding from Screener."""
        try:
            section = soup.find(id="shareholding")
            if not section:
                return None
            table = section.find("table")
            if not table:
                return None
            rows = table.find_all("tr")
            if len(rows) < 2:
                return None

            headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
            # Take the latest period (last column)
            result = {"stock_id": stock_id, "period_end": date.today()}
            for row in rows[1:]:
                cells = row.find_all("td")
                if not cells:
                    continue
                label = cells[0].get_text(strip=True).lower()
                if not cells or len(cells) < 2:
                    continue
                try:
                    val = float(cells[-1].get_text(strip=True).replace("%","").replace(",",""))
                except ValueError:
                    continue
                mapping = {
                    "promoters": "promoter_pct",
                    "fiis":      "fii_pct",
                    "diis":      "dii_pct",
                    "public":    "public_pct",
                    "pledged":   "pledged_pct",
                }
                col = mapping.get(label)
                if col:
                    result[col] = val
            return result if len(result) > 2 else None
        except Exception:
            return None

    def _parse_period(self, label: str):
        """Convert 'Mar 2025' → date(2025, 3, 31)."""
        import calendar
        try:
            parts = label.strip().split()
            if len(parts) != 2:
                return None
            month_map = {m[:3]: i for i, m in enumerate(calendar.month_abbr) if m}
            month = month_map.get(parts[0][:3])
            year  = int(parts[1])
            if not month:
                return None
            last_day = calendar.monthrange(year, month)[1]
            return date(year, month, last_day)
        except Exception:
            return None
```

---

## Task 3.9 — Financial Ratios Pipeline

**File:** `app/pipelines/stock_ratings.py` covers this too — ratios feed directly into ratings.

The `financial_ratios` table is populated by `screener_fundamentals.py` (Task 3.8) for fundamental/valuation ratios sourced from Screener. No separate pipeline needed. The `financial_ratios` CRUD (`upsert_financial_ratios`) is already defined in Task 3.8.

---

## Task 3.10 — Stock Ratings Pipeline

**File:** `app/pipelines/stock_ratings.py` (new)
**Target tables:** `stock_ratings`, `fundamental_scores`
**New CRUD needed:** `upsert_stock_rating`, `upsert_fundamental_score`
**Estimated time:** 2 hours

This pipeline reads from `financial_ratios` and `technical_indicators` (already populated by earlier pipelines) and produces composite scores. It mirrors whatever scoring logic already exists in the codebase.

### New CRUD functions to add to `crud.py`

```python
# Add to crud.py

from .models import StockRating, FundamentalScore

async def upsert_stock_rating(session: AsyncSession, row: dict) -> int:
    stmt = pg_insert(StockRating).values(row)
    update_cols = {k: getattr(stmt.excluded, k)
                   for k in row if k not in ("stock_id", "rated_on")}
    stmt = stmt.on_conflict_do_update(
        constraint="uq_stock_rating_stock_date",
        set_=update_cols,
    )
    await session.execute(stmt)
    await session.commit()
    return 1


async def upsert_fundamental_score(session: AsyncSession, row: dict) -> int:
    stmt = pg_insert(FundamentalScore).values(row)
    update_cols = {k: getattr(stmt.excluded, k)
                   for k in row if k not in ("stock_id", "period_end", "score_version")}
    stmt = stmt.on_conflict_do_update(
        constraint="uq_stock_period_version",
        set_=update_cols,
    )
    await session.execute(stmt)
    await session.commit()
    return 1


async def get_latest_financial_ratios(session: AsyncSession, stock_id: int):
    """Fetch the most recent financial_ratios row for a stock."""
    result = await session.execute(
        select(FinancialRatio)
        .where(FinancialRatio.stock_id == stock_id)
        .order_by(FinancialRatio.period_end.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest_technical_indicators(session: AsyncSession, stock_id: int):
    """Fetch the most recent technical_indicators row for a stock."""
    result = await session.execute(
        select(TechnicalIndicator)
        .where(
            TechnicalIndicator.stock_id  == stock_id,
            TechnicalIndicator.timeframe == "1d",
        )
        .order_by(TechnicalIndicator.ind_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
```

### Pipeline

```python
# app/pipelines/stock_ratings.py
import logging
from datetime import date
from .base import BasePipeline, PipelineResult
from ..crud import (
    get_active_stocks, get_latest_financial_ratios,
    get_latest_technical_indicators, upsert_stock_rating, upsert_fundamental_score
)

logger = logging.getLogger(__name__)


class StockRatingsPipeline(BasePipeline):
    pipeline_name = "stock_ratings"

    async def execute(self) -> PipelineResult:
        stocks      = await get_active_stocks(self.db)
        records_out = 0
        today       = date.today()

        for stock in stocks:
            try:
                ratios = await get_latest_financial_ratios(self.db, stock.id)
                ti     = await get_latest_technical_indicators(self.db, stock.id)

                # Compute component scores (0–10 scale)
                fundamental_score = self._score_fundamentals(ratios)
                valuation_score   = self._score_valuation(ratios)
                technical_score   = self._score_technicals(ti)
                momentum_score    = self._score_momentum(ti)

                total = sum(filter(None, [
                    fundamental_score, valuation_score,
                    technical_score, momentum_score,
                ])) / sum(1 for x in [
                    fundamental_score, valuation_score,
                    technical_score, momentum_score,
                ] if x is not None)

                label = (
                    "Strong Buy"  if total >= 7.5 else
                    "Buy"         if total >= 6.0 else
                    "Neutral"     if total >= 4.5 else
                    "Sell"        if total >= 3.0 else
                    "Strong Sell"
                )

                await upsert_stock_rating(self.db, {
                    "stock_id":          stock.id,
                    "rated_on":          today,
                    "total_score":       round(total, 3),
                    "rating_label":      label,
                    "fundamental_score": fundamental_score,
                    "valuation_score":   valuation_score,
                    "technical_score":   technical_score,
                    "momentum_score":    momentum_score,
                    "score_breakdown_":  {
                        "fundamental": fundamental_score,
                        "valuation":   valuation_score,
                        "technical":   technical_score,
                        "momentum":    momentum_score,
                    },
                })
                records_out += 1

            except Exception as e:
                logger.warning(f"[stock_ratings] failed for {stock.symbol}: {e}")
                continue

        return PipelineResult(
            records_in=len(stocks),
            records_out=records_out,
        )

    def _score_fundamentals(self, r) -> float | None:
        if not r:
            return None
        score = 5.0   # Start at neutral
        if r.roe and r.roe > 15:      score += 1.0
        if r.roce and r.roce > 15:    score += 1.0
        if r.pat_margin and r.pat_margin > 10: score += 1.0
        if r.debt_equity and r.debt_equity < 1: score += 1.0
        if r.interest_cov and r.interest_cov > 3: score += 0.5
        if r.cfo_to_pat and r.cfo_to_pat > 0.8: score += 0.5
        return round(min(10.0, score), 3)

    def _score_valuation(self, r) -> float | None:
        if not r:
            return None
        score = 5.0
        if r.pe_ratio:
            if   r.pe_ratio < 15:  score += 2.0
            elif r.pe_ratio < 25:  score += 1.0
            elif r.pe_ratio > 50:  score -= 1.5
        if r.pb_ratio:
            if   r.pb_ratio < 1.5: score += 1.5
            elif r.pb_ratio < 3:   score += 0.5
            elif r.pb_ratio > 6:   score -= 1.0
        if r.dividend_yield and r.dividend_yield > 2: score += 0.5
        return round(min(10.0, max(0.0, score)), 3)

    def _score_technicals(self, ti) -> float | None:
        if not ti:
            return None
        score = 5.0
        if ti.sma_50 and ti.sma_200:
            if ti.sma_50 > ti.sma_200: score += 1.5   # Golden cross territory
            else:                       score -= 1.0
        if ti.rsi_14:
            if   ti.rsi_14 < 30:  score += 1.5   # Oversold — potential buy
            elif ti.rsi_14 > 70:  score -= 1.0   # Overbought
        if ti.macd_hist and ti.macd_hist > 0: score += 0.5
        if ti.adx_14 and ti.adx_14 > 25:      score += 0.5   # Strong trend
        return round(min(10.0, max(0.0, score)), 3)

    def _score_momentum(self, ti) -> float | None:
        if not ti:
            return None
        score = 5.0
        if ti.pct_from_52w_high and ti.pct_from_52w_high > -10: score += 1.5
        if ti.volume_ratio and ti.volume_ratio > 1.5:            score += 1.0
        if ti.rs_6m_vs_nifty and ti.rs_6m_vs_nifty > 0:         score += 1.0
        return round(min(10.0, max(0.0, score)), 3)
```

---

## Task 3.11 — Manual Trigger API Endpoints

**File:** `app/routers/admin.py` (new)
**Estimated time:** 1 hour

These endpoints let you trigger any pipeline on demand from the admin panel or curl — without waiting for the cron schedule. Useful for testing and backfills.

```python
# app/routers/admin.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db, AsyncSessionLocal
from ..dependencies import get_current_user
from ..models import AdminUser

router = APIRouter(prefix="/admin/pipelines", tags=["admin"])

PIPELINE_MAP = {
    "amfi_nav":              "AmfiNavPipeline",
    "benchmark_nav":         "BenchmarkNavPipeline",
    "fund_metrics":          "FundMetricsPipeline",
    "yf_price":              "YfPricePipeline",
    "technical_indicators":  "TechnicalIndicatorsPipeline",
    "screener_fundamentals": "ScreenerFundamentalsPipeline",
    "stock_ratings":         "StockRatingsPipeline",
}


@router.post("/{pipeline_name}/run")
async def trigger_pipeline(
    pipeline_name: str,
    background_tasks: BackgroundTasks,
    _user: AdminUser = Depends(get_current_user),
):
    """
    Manually trigger a named pipeline. Runs in the background.
    Returns immediately — check /sync/status for result.

    Only admins can trigger pipelines.
    """
    if _user.user_role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    if pipeline_name not in PIPELINE_MAP:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown pipeline: {pipeline_name}. "
                   f"Valid: {list(PIPELINE_MAP.keys())}",
        )

    # Run in background so the HTTP response returns immediately
    async def _run():
        module_map = {
            "amfi_nav":              ("app.pipelines.amfi_nav",              "AmfiNavPipeline"),
            "benchmark_nav":         ("app.pipelines.benchmark_nav",         "BenchmarkNavPipeline"),
            "fund_metrics":          ("app.pipelines.fund_metrics",          "FundMetricsPipeline"),
            "yf_price":              ("app.pipelines.yf_price",              "YfPricePipeline"),
            "technical_indicators":  ("app.pipelines.technical_indicators",  "TechnicalIndicatorsPipeline"),
            "screener_fundamentals": ("app.pipelines.screener_fundamentals", "ScreenerFundamentalsPipeline"),
            "stock_ratings":         ("app.pipelines.stock_ratings",         "StockRatingsPipeline"),
        }
        mod_path, cls_name = module_map[pipeline_name]
        import importlib
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, cls_name)
        async with AsyncSessionLocal() as db:
            await cls(db, triggered_by="manual").run()

    background_tasks.add_task(_run)
    return {
        "message": f"Pipeline '{pipeline_name}' triggered",
        "check_status": f"/sync/status?pipeline_name={pipeline_name}",
    }


@router.get("/")
async def list_pipelines(_user: AdminUser = Depends(get_current_user)):
    """List all registered pipeline names."""
    return {"pipelines": list(PIPELINE_MAP.keys())}
```

Register in `main.py`:
```python
from .routers.admin import router as admin_router
app.include_router(admin_router)
```

---

## Task 3.12 — Render Upgrade & Cron Verification

**Estimated time:** 1 hour

### Upgrade Render to Starter plan

The free tier spins down after 15 minutes of inactivity. APScheduler jobs will be missed if the instance is sleeping when a cron fires. Upgrade before enabling the scheduler in production.

- Render dashboard → your service → Settings → Instance Type → **Starter ($7/month)**
- This gives: always-on instance, no spin-down, 512 MB RAM, 0.1 CPU

### Verify scheduler fires correctly

After deploy, check that jobs fire at their scheduled times:

```bash
# 1. Trigger a test run manually to verify the pipeline works end to end
TOKEN="<your-admin-jwt>"
curl -X POST https://nivesh-server.onrender.com/admin/pipelines/amfi_nav/run \
  -H "Authorization: Bearer $TOKEN"

# 2. Check the result after ~30 seconds
curl -s "https://nivesh-server.onrender.com/sync/status?pipeline_name=amfi_nav&limit=1" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Expected:
# {
#   "runs": [{
#     "id": 1,
#     "pipeline_name": "amfi_nav",
#     "status": "COMPLETED",
#     "records_in": 14500,
#     "records_out": 14500,
#     ...
#   }]
# }

# 3. Verify scheduler jobs are registered
# Add a temporary /debug/jobs endpoint (remove after testing):
@app.get("/debug/jobs")
async def debug_jobs():
    from .pipelines.scheduler import scheduler
    return [
        {"id": j.id, "next_run": str(j.next_run_time)}
        for j in scheduler.get_jobs()
    ]
```

---

## 18. Cron Schedule Summary

| Job ID | Cron (IST) | Target Tables | Notes |
|---|---|---|---|
| `benchmark_nav` | Daily 19:30 | `benchmark_nav_history` | Must run before `fund_metrics` |
| `yf_price` | Mon–Fri 19:00 | `price_data` | NSE closes 15:30; data available ~18:30 |
| `technical_indicators` | Mon–Fri 20:00 | `technical_indicators` | Depends on `yf_price` completing |
| `amfi_nav` | Daily 21:30 | `fund_nav_history` | AMFI publishes by ~21:00 |
| `stock_ratings` | Daily 21:00 | `stock_ratings` | Depends on `technical_indicators` |
| `fund_metrics` | Daily 23:00 | `fund_metrics`, `benchmark_metrics` | Last — depends on both NAV pipelines |
| `screener_fundamentals` | Sunday 06:00 | `financial_statements`, `financial_ratios`, `shareholding_pattern` | Weekly — quarterly data; low urgency |

**Dependency chain:**

```
19:00  yf_price
          ↓
20:00  technical_indicators
          ↓
21:00  stock_ratings

19:30  benchmark_nav ──┐
21:30  amfi_nav ────────┤
                        ↓
23:00  fund_metrics
```

---

## 19. Error Handling Strategy

### Per-pipeline: PARTIAL vs FAILED

- `FAILED` — top-level unhandled exception (network down, DB unreachable, schema mismatch). No records written.
- `PARTIAL` — pipeline completed but some records failed individually (one bad stock, one missing slug). Majority of records written successfully. `BasePipeline` uses `PARTIAL` when `execute()` returns a `PipelineResult` with `error_msg` set but doesn't raise.
- `COMPLETED` — all records processed without errors.

### Retry logic

APScheduler does not retry failed jobs automatically. The `misfire_grace_time=600` setting in `register_all_jobs` means: if the job was supposed to fire at 21:30 and the instance was briefly unavailable, it will still run if the instance comes back within 10 minutes.

For the `screener_fundamentals` pipeline specifically, individual stock failures are caught and logged (the pipeline continues). A summary of failed slugs is written to `etl_runs.metadata`.

### Alerting (simple)

Add this to `BasePipeline.run()` after `finish_etl_run` for FAILED status:

```python
if status == "FAILED":
    logger.error(
        f"PIPELINE FAILED: {self.pipeline_name} "
        f"entity={self.entity_id} error={result.error_msg}"
    )
    # Future: send email / Slack / webhook here
```

---

## 20. Render Memory Constraints & Batching

Render Starter has 512 MB RAM. The two heavy pipelines are `technical_indicators` (pandas-ta on 200 stocks) and `fund_metrics` (numpy on 15,000 funds).

| Pipeline | Memory strategy |
|---|---|
| `technical_indicators` | Process one stock at a time — load 260 rows, compute, upsert, discard DataFrame, repeat. Never hold all stocks in memory simultaneously. |
| `fund_metrics` | Same — one fund at a time. The `_compute_fund_metrics` method already does this. |
| `yf_price` | `BATCH_SIZE=50` stocks per yfinance call. Controlled by the constant at the top of `yf_price.py`. Reduce to 25 if memory spikes. |
| `screener_fundamentals` | One stock at a time with request delays. Memory is not a concern — the bottleneck is HTTP rate limits. |
| `amfi_nav` | Entire `NAVAll.txt` loaded into memory (~5 MB text). Well within limits. |

**Monitor in Render dashboard:** Service → Metrics → Memory. If `technical_indicators` pushes past 450 MB, reduce to processing 1 stock per iteration with explicit garbage collection:
```python
import gc
# After each stock:
del df
gc.collect()
```

---

## 21. Dependency Changes

Add to `requirements.txt`:

```text
# New for Phase 3:
yfinance==0.2.40          # Yahoo Finance price data (already in project based on yf_symbol field)
pandas-ta==0.3.14b        # Technical indicators (already in project)
beautifulsoup4==4.12.3    # Screener.in HTML parsing
lxml==5.2.1               # HTML parser for BeautifulSoup (faster than html.parser)
pytz==2024.1              # IST timezone for APScheduler
apscheduler==3.10.4       # Job scheduler (already in project)

# Already in requirements — confirm present:
pandas>=2.2.0
numpy>=1.26.0
httpx>=0.27.0
```

---

## 22. Definition of Done

Phase 3 is complete when all of the following are true:

- [ ] Scheduler starts on Render boot and logs `7 jobs registered`
- [ ] `GET /admin/pipelines` lists all 7 pipelines
- [ ] Manual trigger of `amfi_nav` completes with `status: COMPLETED` and `records_out > 1000`
- [ ] Manual trigger of `benchmark_nav` completes with `status: COMPLETED`
- [ ] Manual trigger of `yf_price` completes — `price_data` table has rows
- [ ] Manual trigger of `technical_indicators` completes — `technical_indicators` table has rows
- [ ] Manual trigger of `screener_fundamentals` completes for at least 5 stocks — `financial_statements` has rows
- [ ] Manual trigger of `fund_metrics` completes — `fund_metrics` table has updated `updated_at`
- [ ] Manual trigger of `stock_ratings` completes — `stock_ratings` table has rows
- [ ] `etl_runs` table shows a row for every manual trigger above
- [ ] A FAILED pipeline run shows `status: FAILED` and `error_msg` in `etl_runs`
- [ ] Render memory stays below 450 MB during `technical_indicators` run
- [ ] Render upgraded to Starter plan — instance is always-on
- [ ] Scheduled `amfi_nav` runs automatically the next day without manual trigger

---

## 23. Execution Order — Day by Day

```
Day 1 (4h)
  Task 3.1  Scheduler bootstrap + lifespan wiring        1h
  Task 3.2  BasePipeline class                           1h
  Task 3.3  AMFI NAV pipeline + manual test              2h

Day 2 (4h)
  Task 3.4  Benchmark NAV pipeline                       1.5h
  Task 3.5  Fund metrics pipeline (wrap existing logic)  2.5h

Day 3 (4h)
  Task 3.6  Yahoo Finance price pipeline + new CRUD      2h
  Task 3.7  Technical indicators pipeline + new CRUD     2h

Day 4 (4h)
  Task 3.8  Screener fundamentals pipeline + new CRUD    3h
  Task 3.10 Stock ratings pipeline + new CRUD            1h

Day 5 (3h)
  Task 3.11 Admin manual trigger endpoints               1h
  Task 3.12 Render upgrade + full smoke test sequence    2h
```

**Total: 5 working days**

---

*Phase 3 Implementation Plan · Nivesh Platform · May 2026*
*Previous: Phase 2 — Server Core API on Render*
*Next: Phase 4 — Client SQLite + Local API*
