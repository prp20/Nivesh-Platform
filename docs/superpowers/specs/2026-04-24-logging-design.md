# Logging Integration Design

**Date:** 2026-04-24
**Branch:** feature/improve_ratios
**Status:** Approved

---

## Goal

Add centralized, file-based logging to the entire Nivesh Platform backend. All log output (API requests, pipeline jobs, scheduler events, errors) is captured to a daily-rotating log file at `logs/app.log` in the project root, while also continuing to appear on the console.

---

## Requirements

| # | Requirement |
|---|-------------|
| 1 | Logs written to `<project_root>/logs/app.log` |
| 2 | Daily rotation at midnight; 30 days of backups retained |
| 3 | Logs also streamed to stdout (console unchanged) |
| 4 | Default log level: `INFO` |
| 5 | Every HTTP request logged: method, path, status code, duration (ms) |
| 6 | No changes required to existing `pipeline/` or `app/` module loggers |
| 7 | No log files created during `pytest` runs |
| 8 | Third-party library noise suppressed at `WARNING` level |

---

## Architecture

### Central setup module

A single `backend/app/logging_config.py` exposes one public function:

```python
def setup_logging(log_dir: Path) -> None
```

It configures the **Python root logger** with two handlers:

1. **`TimedRotatingFileHandler`**
   - Path: `log_dir / "app.log"`
   - Rotation: `when="midnight"`, `backupCount=30`
   - Creates `log_dir` automatically if it does not exist (`mkdir(parents=True, exist_ok=True)`)

2. **`StreamHandler`** — stdout

Both handlers use a shared formatter:
```
%(asctime)s | %(levelname)-8s | %(name)s | %(message)s
```

Root logger level: `INFO`.

The following third-party loggers are clamped to `WARNING` to suppress internal chatter:
- `sqlalchemy.engine`
- `httpx`, `httpcore`
- `apscheduler`
- `urllib3`
- `asyncio`
- `uvicorn.access` (replaced by our request middleware)

A double-initialization guard checks `logging.root.handlers` before adding new handlers — safe to call multiple times.

### Entry point

`setup_logging()` is called once at the top of `lifespan()` in `backend/app/main.py`, before DB init, scheduler start, or anything else:

```python
from pathlib import Path
from .logging_config import setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(Path(__file__).resolve().parents[2] / "logs")
    # ... rest of startup
```

### Request logging middleware

A `RequestLoggingMiddleware` (Starlette `BaseHTTPMiddleware`) added to `main.py` logs every HTTP request at `INFO`:

```
2026-04-24 18:32:01,452 | INFO     | app.main | GET /api/v1/stocks 200 34ms
```

Health check path (`/api/health`) is excluded to avoid log spam from scheduler/uptime pings.

### Existing module loggers

All `pipeline/` and `app/` modules already call `logging.getLogger(__name__)`. They inherit the root config automatically — **zero changes needed in those files**.

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/logging_config.py` | **Create** | `setup_logging()` function |
| `backend/app/main.py` | **Modify** | Call `setup_logging()` in lifespan; add `RequestLoggingMiddleware` |
| `logs/.gitkeep` | **Create** | Tracks `logs/` dir in git without committing log files |
| `.gitignore` | **Modify** | Add `logs/*.log*` to exclude rotated log files |

Total: 2 new files, 2 modified files.

---

## Log Format

```
2026-04-24 18:32:01,452 | INFO     | app.main            | Application startup complete
2026-04-24 18:32:01,788 | INFO     | app.main            | GET /api/v1/funds 200 12ms
2026-04-24 18:35:00,001 | INFO     | pipeline.scheduler  | Price ingestion job started
2026-04-24 18:35:04,221 | INFO     | pipeline.price_ingestion | Upserted 90 rows for RELIANCE.NS
2026-04-24 19:00:00,001 | WARNING  | pipeline.ratio_engine | No financial data found for stock_id=7
2026-04-24 19:01:14,332 | ERROR    | pipeline.rating_engine | Rating compute failed for TCS: division by zero
```

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| `logs/` directory missing | Created automatically at startup |
| `logs/` directory not writable | Raises `PermissionError` at startup — intentional hard failure |
| `setup_logging()` called twice | Guard on `logging.root.handlers` — no duplicate handlers added |
| `pytest` runs | `lifespan()` not called; no log files created; no test changes needed |
| Log rotation on midnight | Handled by `TimedRotatingFileHandler`; old files suffixed `.YYYY-MM-DD` |
| uvicorn access log duplication | `uvicorn.access` clamped to `WARNING`; our middleware handles request logging |

---

## Out of Scope

- Structured JSON logging (not needed for file-based log review)
- Log shipping to external services (Datadog, ELK, etc.)
- Per-subsystem log files (single `app.log` is sufficient)
- Frontend logging
