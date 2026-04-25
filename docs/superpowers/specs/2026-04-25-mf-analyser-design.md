# MF Analyser — LangGraph Design Spec

**Date:** 2026-04-25  
**Status:** Approved  
**Author:** Brainstormed with Claude Code

---

## Overview

Build an agentic AI workflow (`mf_analyser/`) that performs a complete analysis of a mutual fund using LangGraph. The agent fetches NAV history and benchmark data, computes all risk/return metrics, optionally benchmarks the fund against category peers, generates a structured LLM verdict via Groq, and persists the results to the database. Triggered on-demand via API or on a weekly schedule.

This mirrors the existing `fundamental_scorer/` pattern for stocks and extends it with conditional branching for peer analysis — a capability the stock scorer does not have.

---

## Architecture

### Graph type

Branching DAG with one conditional edge. Seven nodes total. Uses `StateGraph` from LangGraph with `MFAnalysisState` as the shared state type.

### Node map

```
fetch_fund
    → compute_metrics
        → route_peer_analysis()          ← conditional edge
            ↙ (peers ≥ 3)    ↘ (peers < 3)
        fetch_peers          skip_peers
            ↓
        rank_peers
            ↘               ↙
            generate_verdict
                → persist
                    → END
```

### Nodes

| Node | Responsibility |
|------|---------------|
| `fetch_fund` | Load `FundMaster`, `FundNavHistory` (full history), and `BenchmarkNavHistory` from DB using async session |
| `compute_metrics` | Call `analytics.compute_all_metrics()` with nav + benchmark history. Writes `computed_metrics` to state |
| `route_peer_analysis` | Conditional edge function. Counts funds in same `scheme_category` that have a `fund_metrics` row (i.e. metrics have been computed). Routes to `fetch_peers` if ≥ 3 such peers exist, else `skip_peers` |
| `fetch_peers` | Fetch `fund_metrics` rows for all peer funds in same category. Writes `peer_metrics` and `peer_count` |
| `rank_peers` | Call `analytics.rank_funds_for_comparison()` with the fund + peers. Derive `peer_rank` and `peer_percentile`. Compute `category_stats` (median Sharpe, median CAGR 3Y) |
| `skip_peers` | Pass-through node. Sets `peers_available=False`, `peer_count=0`. Ensures graph converges cleanly |
| `generate_verdict` | Single Groq LLM call with structured JSON prompt. Parses `verdict_label`, `verdict_text`, `key_strengths`, `key_risks`. Falls back to deterministic labeling rules if JSON parse fails |
| `persist` | Upsert `fund_analysis` row (full output). Update `fund_metrics.analysis_verdict`, `analysis_summary`, `analysis_at`. Wrap in `audit_job("mf_analysis")` |

---

## State

```python
class MFAnalysisState(TypedDict):
    # Input
    scheme_code: str
    score_version: str                   # "v1.0"

    # Raw data (populated by fetch_fund)
    fund_master: Optional[Dict]
    nav_history: List[Dict]              # [{nav_date, nav_value}, ...]
    benchmark_history: List[Dict]
    scheme_category: str                 # copied for routing convenience

    # Computed metrics (populated by compute_metrics)
    computed_metrics: Optional[Dict]     # full output of analytics.compute_all_metrics()

    # Peer context (populated by fetch_peers / rank_peers / skip_peers)
    peers_available: bool
    peer_count: int
    peer_metrics: List[Dict]             # fund_metrics rows for category peers
    peer_rank: Optional[int]             # 1 = best in category
    peer_percentile: Optional[float]     # 0–100, higher = better
    category_stats: Optional[Dict]       # {median_sharpe, median_cagr_3y}

    # LLM output (populated by generate_verdict)
    verdict_label: str                   # STRONG BUY | BUY | HOLD | AVOID
    verdict_text: str                    # 3–5 sentence narrative
    key_strengths: List[str]             # 2–3 bullets
    key_risks: List[str]                 # 2–3 bullets

    # Workflow metadata
    status: str    # PENDING → FETCHED → SCORED → RANKED → REASONED → COMPLETED | FAILED
    error: Optional[str]
    logs: List[str]
```

**Status transitions:**
- `PENDING` → `FETCHED` (after fetch_fund)
- `FETCHED` → `SCORED` (after compute_metrics)
- `SCORED` → `RANKED` (after rank_peers) or stays `SCORED` (after skip_peers)
- `RANKED`/`SCORED` → `REASONED` (after generate_verdict)
- `REASONED` → `COMPLETED` (after persist) or `FAILED` (on any error)

---

## Database Schema

### New table: `fund_analysis`

```python
class FundAnalysis(Base):
    __tablename__ = "fund_analysis"
    __table_args__ = (
        UniqueConstraint('scheme_code', 'score_version',
                         name='uq_fund_analysis_scheme_version'),
        Index('ix_fund_analysis_scheme_code', 'scheme_code'),
    )

    id                      = Column(Integer, primary_key=True)
    scheme_code             = Column(String(50), ForeignKey("fund_master.scheme_code",
                                    ondelete="CASCADE"), nullable=False)
    score_version           = Column(String(10), nullable=False, default="v1.0")

    # Key metrics snapshot
    cagr_3y                 = Column(Numeric(10, 4))
    cagr_5y                 = Column(Numeric(10, 4))
    sharpe_ratio            = Column(Numeric(10, 4))
    sortino_ratio           = Column(Numeric(10, 4))
    alpha                   = Column(Numeric(10, 4))
    max_drawdown            = Column(Numeric(10, 4))

    # Peer context
    peers_analyzed          = Column(Integer)           # 0 if peer branch skipped
    peer_rank               = Column(Integer)           # NULL if peers_analyzed < 3
    peer_percentile         = Column(Numeric(5, 2))
    category_median_sharpe  = Column(Numeric(10, 4))
    category_median_cagr_3y = Column(Numeric(10, 4))

    # LLM verdict
    verdict_label           = Column(String(20))        # STRONG BUY | BUY | HOLD | AVOID
    verdict_text            = Column(Text)
    key_strengths           = Column(JSONB)             # ["...", "..."]
    key_risks               = Column(JSONB)

    computed_at             = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at              = Column(TIMESTAMP(timezone=True), onupdate=func.now())
```

### Additions to existing `FundMetrics`

Three new columns — summary fields for the existing `GET /metrics/{scheme_code}` API to serve without a join:

```python
analysis_verdict  = Column(String(20))           # mirrors verdict_label
analysis_summary  = Column(String(500))          # 1-sentence digest of verdict_text
analysis_at       = Column(TIMESTAMP(timezone=True))
```

### Migration

New Alembic migration: `002_add_fund_analysis.py`
- Creates `fund_analysis` table with all indexes
- Adds 3 columns to `fund_metrics`
- Idempotent (uses `IF NOT EXISTS` / `IF column NOT IN`)

---

## LLM Verdict Node

### Prompt structure

**System:** `"You are a SEBI-registered mutual fund analyst. Analyze the data and return a JSON object only — no prose outside JSON."`

**User:** Structured block with 3 sections:
1. Fund identity (name, category, AMC, AUM, expense ratio)
2. Performance & risk metrics (CAGR, Sharpe, Sortino, alpha, drawdown, beta, capture ratios)
3. Peer context section — included only if `peers_available=True` (rank, percentile, category medians)

**Required JSON keys:** `verdict_label`, `verdict_text`, `key_strengths` (list), `key_risks` (list)

### Deterministic fallback

If the Groq call fails or returns unparseable JSON, `generate_verdict` computes the label deterministically and sets `verdict_text` to a template string. The graph never blocks at this node.

| Label | Condition |
|-------|-----------|
| `STRONG BUY` | Sharpe > 1.2 AND alpha > 0.05 AND peer_percentile > 75 (if available) |
| `BUY` | Sharpe > 0.8 AND alpha > 0 AND peer_percentile > 50 (if available) |
| `HOLD` | Sharpe 0.4–0.8 OR alpha near 0 |
| `AVOID` | Sharpe < 0.4 OR alpha < 0 |

### LLM config

- Model: `llama3-70b-8192` via `langchain-groq` (already in `requirements.txt`)
- Temperature: `0.2` (low — we want consistent, factual output)
- Max tokens: `600`
- LangSmith tracing: enabled via `@traceable` decorator (already configured)

---

## File Structure

```
backend/
├── mf_analyser/
│   ├── __init__.py
│   ├── graph.py              # StateGraph + run_mf_analyser() entry point
│   ├── state.py              # MFAnalysisState TypedDict
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── data_nodes.py     # fetch_fund_node, persist_node
│   │   ├── compute_nodes.py  # compute_metrics_node
│   │   ├── peer_nodes.py     # fetch_peers_node, rank_peers_node, skip_peers_node
│   │   └── verdict_nodes.py  # generate_verdict_node (Groq LLM call)
│   └── prompts/
│       └── verdict_prompt.py # system + user prompt template builders
│
├── app/
│   ├── models.py             # + FundAnalysis, 3 new cols on FundMetrics
│   ├── routers/
│   │   └── mf_analysis.py    # POST + GET /api/v1/mf-analysis/{scheme_code}
│   └── main.py               # register mf_analysis router
│
├── alembic/versions/
│   └── 002_add_fund_analysis.py
│
└── scripts/
    └── run_mf_analyser.py    # CLI: python run_mf_analyser.py 119551
```

---

## API Endpoints

### `POST /api/v1/mf-analysis/{scheme_code}`

Triggers analysis for one fund. Validates scheme exists, enqueues `run_mf_analyser()` as a FastAPI `BackgroundTask`, returns immediately.

**Response `202`:**
```json
{ "status": "STARTED", "scheme_code": "119551" }
```

**Response `404`:** Fund not found.

### `GET /api/v1/mf-analysis/{scheme_code}`

Returns latest analysis result.

**Response `200`:** Full `fund_analysis` row as JSON.  
**Response `404`:** Analysis never run for this fund.

### `POST /api/v1/pipeline/mf-analysis/all` *(admin-gated)*

Triggers bulk analysis for all active funds. Requires `require_admin` dependency. Wrapped in `audit_job("mf_analysis_bulk")`.

---

## Scheduler Integration

Added to `pipeline/scheduler.py`:

```python
scheduler.add_job(
    run_bulk_mf_analysis,
    CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="Asia/Kolkata"),
    id="mf_analysis_weekly",
    replace_existing=True,
)
```

Runs at 03:00 IST Sunday — after the 02:00 fundamental scrape, ensuring freshest data is available.

---

## Error Handling

| Failure point | Behaviour |
|--------------|-----------|
| `fetch_fund` — fund not found | Sets `status=FAILED`, `error="Fund not found"`, exits early |
| `fetch_fund` — insufficient NAV history (< 90 days) | Sets `status=FAILED`, `error="Insufficient NAV data"` |
| `compute_metrics` — analytics exception | Logs error, sets `status=FAILED` |
| `fetch_peers` — DB error | Logs error, routes to `skip_peers` (graceful degradation, not failure) |
| `generate_verdict` — Groq API error / timeout | Falls back to deterministic label + template text, continues to persist |
| `persist` — DB write error | Sets `status=FAILED`, surfaces via audit log |

All nodes append to `state["logs"]` on every operation (success and failure) for observability via LangSmith.

---

## What Gets Reused (No Changes)

| Existing code | Reused by |
|--------------|-----------|
| `analytics.compute_all_metrics()` | `compute_metrics_node` |
| `analytics.rank_funds_for_comparison()` | `rank_peers_node` |
| `pipeline/audit.py → audit_job()` | `persist_node` |
| `app/database.py → raw_connection()` | All data nodes |
| `fundamental_scorer/graph.py` pattern | `mf_analyser/graph.py` structure |
| Groq + LangSmith config in `.env` | `verdict_nodes.py` |

---

## Out of Scope

- Frontend UI changes (displaying the new verdict fields) — separate task
- Equity-specific analysis (sector allocation, holdings overlap) — no data source yet
- Portfolio-level analysis across multiple funds — future phase
- Real-time streaming of analysis progress to frontend — future enhancement
