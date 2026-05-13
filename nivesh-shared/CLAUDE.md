# nivesh-shared — Shared Pydantic Schemas

## Purpose

Pip-installable package containing the shared Pydantic response schemas. This is the **API contract artifact** — both `nivesh-server` and `nivesh-client` import from here. A breaking schema change requires bumping the version in `pyproject.toml`.

## Install

```bash
pip install -e ./nivesh-shared          # from monorepo root
pip install nivesh-shared==0.1.0        # from PyPI (future)
```

## Schema Files

| File | Contains |
|---|---|
| `schemas/funds.py` | Fund NAV, metrics, master, comparison schemas |
| `schemas/stocks.py` | Stock list, detail, screener, OHLCV, fundamental score schemas |
| `schemas/market.py` | Benchmark, market snapshot, sector returns, FII/DII, sync job schemas |
| `schemas/auth.py` | TokenResponse, LoginRequest, RefreshRequest, UserBase |

## Import Pattern

```python
# In nivesh-server or nivesh-client:
from schemas.funds import FundMasterRead, FundMetricsResponse, ComparisonResponse
from schemas.stocks import StockListResponse, StockDetailResult, OHLCVRow
from schemas.market import MarketSnapshot, SectorReturn, FIIDIIFlow, BenchmarkMasterRead
from schemas.auth import TokenResponse, LoginRequest, RefreshRequest
```

## Versioning Rules

- **Patch (0.1.x):** Add optional fields — backwards compatible
- **Minor (0.x.0):** Add new schemas or required fields — clients may need updating
- **Major (x.0.0):** Remove or rename fields — breaking change, requires coordinated deploy

## Adding New Schemas

1. Add to the appropriate file (`funds.py`, `stocks.py`, `market.py`, or `auth.py`)
2. Export from `schemas/__init__.py` if needed
3. Bump version in `pyproject.toml`
4. Re-install: `pip install -e ./nivesh-shared`

## What Belongs Here vs Server-Local

**In `nivesh-shared/` (this package):**
- All API response schemas (what the server returns, what the client expects)
- All request body schemas for server endpoints
- Shared enum types

**In `nivesh-server/app/schemas.py` (server-local only):**
- LangGraph internal state types (e.g. `ScoringStateSchema`)
- Admin-only request types not used by client
- Internal pipeline schemas never exposed via API
