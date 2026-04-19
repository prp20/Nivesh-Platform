# Fundamental Scoring System — Architecture & Low-Level Design

> **Version**: v1.0 | **Date**: 2026-04-18  
> **Platform**: Nivesh Elite — Stock Fundamentals Module  
> **Constraint**: Fully deterministic, rule-based. No AI/ML/LLM used.  
> **Scope**: Generic scoring (sector-neutral) — see `docs/sector_specific_scoring.md` for overrides.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Low-Level Design (LLD)](#2-low-level-design-lld)
3. [Scoring Algorithms](#3-scoring-algorithms)
4. [Pseudocode](#4-pseudocode)
5. [Database Design](#5-database-design)
6. [API Integration Plan](#6-api-integration-plan)
7. [Implementation Plan](#7-implementation-plan)

---

## 1. System Overview

### 1.1 Purpose

The Fundamental Scoring System computes a **deterministic, explainable score (0–100)** for each listed stock across three financial statement dimensions:

| Dimension | Source Endpoint | Table |
|---|---|---|
| Profit & Loss | `?statement_type=PL` | `financial_statements` |
| Balance Sheet | `?statement_type=BS` | `financial_statements` |
| Cash Flow | `?statement_type=CF` | `financial_statements` |

The three scores are blended into a **composite fundamental score** that feeds the existing `stock_ratings` table via `rating_engine.py`.

### 1.2 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    DATA SOURCE LAYER                             │
│   financial_statements (JSONB: PL | BS | CF, annual/quarterly)  │
└───────────────────────────────┬──────────────────────────────────┘
                                │  SQL fetch (up to 5 annual periods)
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                 TRANSFORMATION LAYER                             │
│   pipeline/statement_scorer.py                                   │
│   _get_merged_statement()   →  {periods[], data{key: [vals]}}    │
│   _clean_series()           →  typed float list (None = n/a)     │
└───────┬──────────────────────────────────────────────────────────┘
        │
        ├──────────────────────────────────────────────────────────┐
        │   score_pl(periods, data)         → PLScoreResult        │
        ├──────────────────────────────────────────────────────────┘
        │
        ├──────────────────────────────────────────────────────────┐
        │   score_bs(periods, data)         → BSScoreResult        │
        ├──────────────────────────────────────────────────────────┘
        │
        ├──────────────────────────────────────────────────────────┐
        │   score_cf(periods, cf_data,      → CFScoreResult        │
        │            pl_data=None)                                  │
        └──────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│           LANGGRAPH ORCHESTRATION & REASONING                    │
│   1. Parallel Fetch Nodes (fetch_pl, fetch_bs, fetch_cf)         │
│   2. Deterministic Compute Node (composite_fundamental_score)    │
│      ├── Adaptive weight blending (skips None statements)        │
│   3. LLM Reasoning Node (FINAL LAYER ONLY)                       │
│      ├── Inputs: Scores, metrics, industry                       │
│      ├── Prompt: Analyze the deterministic metrics               │
│      └── Outputs: reasoning_text, reasoning_label                │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                 PERSISTENCE LAYER                                │
│   fundamental_scores table  (UPSERT on conflict)                 │
│   → feeds rating_engine.py → stock_ratings.fundamental_score     │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 Data Flow

```
Scheduler (nightly)
  └─► run_fundamental_scrape_all()        # scrape screener.in → financial_statements
  └─► run_ratio_compute_all()             # compute financial_ratios
  └─► run_statement_score_all()           ← NEW: compute fundamental_scores
  └─► run_rating_compute_all()            # update stock_ratings (uses composite score)
```

---

## 2. Low-Level Design (LLD)

### 2.1 Module Breakdown

```
backend/
├── fundamental_scorer/            ← NEW: Standalone LangGraph App
│   ├── state.py                   ← TypedDict definition for Graph state
│   ├── nodes/
│   │   ├── fetcher.py             ← Async DB fetch (PL, BS, CF)
│   │   ├── determ_scorer.py       ← Wrapping deterministic bracket rules
│   │   └── reasoning.py           ← Final LLM node for explanation
│   ├── graph.py                   ← LangGraph workflow definition
│   ├── run.py                     ← App entrypoint (CLI / Trigger)
│   ├── engine/
│   │   └── statement_scorer.py    ← Pure math/rules (NO LLM inference here)
├── pipeline/
│   ├── scheduler.py               ← MODIFY: hook LangGraph entrypoint
│   └── rating_engine.py           ← MODIFY (optional): use composite score
├── app/
│   ├── models.py                  ← MODIFY: add FundamentalScore model
│   └── routers/
│       └── pipeline.py            ← MODIFY: add admin trigger endpoint
└── alembic/versions/
    └── xxxx_add_fundamental_scores.py  ← NEW: migration
```

### 2.2 Layer Responsibilities

#### Data Fetch Layer — `_get_merged_statement(stock_id, stmt_type)`

- Queries `financial_statements` for up to **5 most recent annual periods**.
- Returns a merged dict: `{"periods": [...], "data": {"revenue": [...], ...}}`.
- Values ordered **oldest → newest** (index 0 = oldest, index -1 = latest).
- Returns `None` if no rows found for that statement type.

#### Transformation Layer — `_clean_series()`, `_cagr()`, `_norm()`, `_stddev()`

- Converts raw JSONB float values to typed lists; `None` for missing/invalid entries.
- Computes derived metrics: CAGR, standard deviation, min-max normalization.
- Never raises exceptions — all edge cases return `None` or neutral values.

#### Scoring Engine — `score_pl()`, `score_bs()`, `score_cf()`

- Deterministic bracket-based scoring for each sub-component.
- Each sub-score is clamped to `[0, 100]`.
- Returns a flat dict with all sub-scores and a `details` dict for explainability.

#### LLM Reasoning Layer (LangGraph Node)

- **Strict isolation:** Receives the *computed deterministic scores* + the raw metrics. The LLM has zero authority to alter the `0–100` scores.
- Prompts an LLM to generate `reasoning_text` (1-2 paragraph qualitative summary of financial health) and a `reasoning_label` (e.g. "Excellent Quality", "Debt Trap").
- Adds human-understandable context to the hard numbers.

#### Persistence Layer — `_upsert_fundamental_scores()`

- Upserts into `fundamental_scores` using `ON CONFLICT (stock_id, period_end, period_type)`.
- Runs via raw asyncpg connection for performance (no ORM overhead on bulk ops).
- Records `computed_at = NOW()` and `score_version = 'v1'`.

### 2.3 Function-Level Signatures

```python
# ── Shared Utilities ─────────────────────────────────────────────────────────
def _clean_series(vals: list) -> list[float | None]: ...
def _last(series: list) -> float | None: ...
def _cagr(series: list, years: int) -> float | None: ...
def _norm(value: float | None, lo: float, hi: float) -> float: ...
def _stddev(series: list) -> float | None: ...
def safe_div(num, denom) -> float | None: ...

# ── Bracket Scorers ───────────────────────────────────────────────────────────
def _score_de(de: float | None) -> float: ...           # D/E → 0–100
def _score_current_ratio(cr: float | None) -> float: ...
def _score_cfo_pat(ratio: float | None) -> float: ...
def _score_financing(cfo: float | None, cff: float | None) -> float: ...

# ── Statement Scorers ─────────────────────────────────────────────────────────
def score_pl(periods: list[str], data: dict[str, list]) -> dict: ...
def score_bs(periods: list[str], data: dict[str, list]) -> dict: ...
def score_cf(periods: list[str], cf_data: dict[str, list],
             pl_data: dict[str, list] | None = None) -> dict: ...

# ── Orchestration ─────────────────────────────────────────────────────────────
async def _get_merged_statement(stock_id: int, stmt_type: str) -> dict | None: ...
async def compute_statement_scores_for_stock(stock_id: int) -> None: ...
async def _upsert_fundamental_scores(...) -> None: ...
async def run_statement_score_all() -> None: ...
```

---

## 3. Scoring Algorithms

All scores are **normalized to [0, 100]**. Missing data defaults to `None` (not `0`), preventing unfair penalization of stocks with limited history. Composite scores use **adaptive weighting** — if a statement is entirely missing, its weight is redistributed proportionally to the available statements.

### 3.1 Profit & Loss Scoring — `score_pl()`

**Data Keys Required** (from `financial_statements.data` JSONB):

| Normalized Key | Screener.in Label | Role |
|---|---|---|
| `sales` / `revenue` | Sales / Revenue | Growth baseline |
| `operating_profit` | Operating Profit | OPM numerator |
| `net_profit` | Net Profit / PAT | PAT growth, loss check |
| `eps_in_rs` / `eps` | EPS in Rs | Per-share earnings trend |

**Sub-Components (each 0–100, equally weighted at 25%)**:

#### A. Revenue & PAT Growth Score (`pl_growth_score`)

```
rev_cagr = CAGR(sales_series, years=5)
pat_cagr = CAGR(net_profit_series, years=5)

Revenue CAGR → Score:
  ≥ 20%      → 100
  15–20%     → 80
  10–15%     → 60
  5–10%      → 40
  0–5%       → 20
  < 0%       → 0
  None       → 50  (neutral, insufficient data)

PAT CAGR → Score:
  ≥ 25%      → 100
  20–25%     → 85
  15–20%     → 70
  10–15%     → 55
  5–10%      → 35
  0–5%       → 15
  < 0%       → 0
  None       → 50  (neutral)

Loss Year Penalty (applied to pat_cagr_score):
  loss_years = count(periods where net_profit < 0)
  penalty    = min(loss_years × 15, 30)
  pat_cagr_score = max(0, pat_cagr_score - penalty)

pl_growth_score = (rev_cagr_score + pat_cagr_score) / 2
```

#### B. Margin Quality Score (`pl_margin_score`)

```
latest_opm = operating_profit[-1] / sales[-1] × 100

OPM → Base Score:
  ≥ 25%      → 100
  20–25%     → 85
  15–20%     → 65
  10–15%     → 45
  5–10%      → 25
  < 5%       → 0

Stability Adjustment (std dev of OPM across all periods):
  σ ≤ 3%     → +10  (highly consistent margins)
  3% < σ ≤ 10% → ±0 (neutral)
  σ > 10%    → -10  (highly volatile)

pl_margin_score = clamp(base_score + stability_adj, 0, 100)
```

#### C. EPS Consistency Score (`pl_eps_score`)

```
eps_series = _clean_series(data["eps_in_rs"])
growth_years = count(i where eps[i] > eps[i-1], i ∈ 1..N-1)
total_pairs  = N - 1

eps_growth_rate = growth_years / total_pairs  # [0, 1]
base_score = eps_growth_rate × 100

Acceleration Bonus:
  if eps[-1] > mean(eps) × 1.2 → +10  (latest EPS well above historical avg)

pl_eps_score = clamp(base_score + bonus, 0, 100)
```

#### D. No-Loss Consistency Score (`pl_consistency_score`)

```
loss_years = count(periods where net_profit < 0 or net_profit is None)
pl_consistency_score = max(0, 100 - loss_years × 20)
# Each loss year docks 20 pts; 5 loss years → 0
```

#### Composite PL Score

```
pl_score = (
    0.25 × pl_growth_score
  + 0.25 × pl_margin_score
  + 0.25 × pl_eps_score
  + 0.25 × pl_consistency_score
)
```

**Return Dict**:
```python
{
  "pl_score": float,               # 0–100
  "pl_growth_score": float,
  "pl_margin_score": float,
  "pl_eps_score": float,
  "pl_consistency_score": float,
  "details": {
    "rev_cagr": float | None,      # % CAGR
    "pat_cagr": float | None,
    "latest_opm": float | None,    # %
    "opm_stddev": float | None,
    "loss_years": int,
    "eps_consistency_pct": float   # 0–100
  }
}
```

---

### 3.2 Balance Sheet Scoring — `score_bs()`

**Data Keys Required**:

| Normalized Key | Screener.in Label | Role |
|---|---|---|
| `total_assets` | Total Assets | Asset base growth |
| `borrowings` | Borrowings | Leverage (D/E numerator) |
| `current_liabilities` | Current Liabilities | Liquidity risk |
| `current_assets` | Current Assets | Liquidity buffer |
| `cwip` | CWIP | Execution risk flag |
| `reserves` | Reserves | Retained earnings |
| `equity_capital` | Equity Capital | Paid-up capital |

**Sub-Components**:

#### A. Leverage Score (`bs_leverage_score`) — Weight 30%

```
de_ratio = borrowings[-1] / (reserves[-1] + equity_capital[-1])

D/E → Score:
  ≤ 0.25     → 100
  ≤ 0.50     → 85
  ≤ 1.00     → 65
  ≤ 1.50     → 45
  ≤ 2.50     → 25
  > 2.50     → 10
  None       → 50  (neutral — insufficient data)
```

#### B. Liquidity Score (`bs_liquidity_score`) — Weight 20%

```
current_ratio = current_assets[-1] / current_liabilities[-1]

CR → Score:
  ≥ 2.5      → 100
  2.0–2.5    → 85
  1.5–2.0    → 65
  1.0–1.5    → 40
  < 1.0      → 0
  None       → 50

CWIP Risk Penalty:
  cwip_pct = cwip[-1] / total_assets[-1]
  if cwip_pct > 0.15 → penalty = -10

bs_liquidity_score = clamp(cr_score + cwip_penalty, 0, 100)
```

#### C. Asset Growth Score (`bs_asset_score`) — Weight 20%

```
ta_cagr = CAGR(total_assets_series, years=5)

Total Asset CAGR → Score:
  ≥ 15%      → 100
  10–15%     → 75
  5–10%      → 50
  0–5%       → 25
  < 0%       → 0
  None       → 50
```

#### D. Networth Score (`bs_networth_score`) — Weight 30%

```
res_cagr = CAGR(reserves_series, years=5)

Reserves CAGR → Score:
  ≥ 15%      → 100
  10–15%     → 80
  5–10%      → 60
  0–5%       → 35
  < 0%       → 0
  None       → 50
```

#### Composite BS Score

```
bs_score = (
    0.30 × bs_leverage_score
  + 0.20 × bs_liquidity_score
  + 0.20 × bs_asset_score
  + 0.30 × bs_networth_score
)
```

**Return Dict**:
```python
{
  "bs_score": float,
  "bs_leverage_score": float,
  "bs_liquidity_score": float,
  "bs_asset_score": float,
  "bs_networth_score": float,
  "details": {
    "de_ratio": float | None,
    "current_ratio": float | None,
    "cwip_pct": float | None,       # fraction, not %
    "ta_cagr": float | None,        # %
    "res_cagr": float | None        # %
  }
}
```

---

### 3.3 Cash Flow Scoring — `score_cf()`

**Data Keys Required** (from `financial_statements.data` where `statement_type = 'CF'`):

| Normalized Key | Screener.in Label | Role |
|---|---|---|
| `cash_from_operating_activity` | Cash from Operating Activity | CFO quality |
| `cash_from_investing_activity` | Cash from Investing Activity | Capex proxy |
| `cash_from_financing_activity` | Cash from Financing Activity | Capital structure |
| `net_profit` (from PL, optional) | Net Profit | CFO/PAT ratio denominator |
| `sales` (from PL, optional) | Revenue | FCF margin denominator |

> **Note**: CF data from screener.in can have limited field coverage. Missing sub-fields receive **50 (neutral)** rather than 0, to avoid penalizing stocks unfairly.

**Sub-Components**:

#### A. Operating CFO Quality (`cf_operating_score`) — Weight 40%

```
cfo_series = _clean_series(cf_data["cash_from_operating_activity"])
pat_series = _clean_series(pl_data["net_profit"]) if pl_data else []

cfo_pat_ratio = cfo[-1] / pat[-1]  # (aligned by period)

CFO/PAT → Score:
  ≥ 1.2      → 100
  1.0–1.2    → 85
  0.8–1.0    → 65
  0.5–0.8    → 40
  0–0.5      → 10
  < 0        → 0
  None       → 50  (neutral)

CFO Consistency Adjustment:
  positive_cfo_years = count(cfo > 0)
  consistency_rate   = positive_cfo_years / len(cfo_series)

  consistency_rate > 0.80 → +10  (almost always cash-generative)
  consistency_rate < 0.50 → -15  (often cash-negative operations)

cf_operating_score = clamp(cfo_pat_score + consistency_adj, 0, 100)
```

#### B. FCF / Capex Score (`cf_capex_score`) — Weight 35%

```
cfi_series = _clean_series(cf_data["cash_from_investing_activity"])
# Investing CF is typically negative (capex outflows)
# FCF = CFO + CFI  (CFI is negative)

fcf_series  = [cfo + cfi for cfo, cfi paired by period, both non-None]
rev_series  = _clean_series(pl_data["sales"]) if pl_data else []

# FCF Margin (preferred, requires revenue)
if rev_series available:
    fcf_margin = fcf[-1] / rev[-1]  # latest period
    FCF Margin → Score:
      ≥ 15%    → 100
      10–15%   → 80
      5–10%    → 60
      0–5%     → 35
      < 0%     → 0
      None     → 50
else:
    # Fallback: raw FCF sign-based score
    fcf_score = 75 if fcf[-1] > 0 else 20

FCF Trend Adjustment (last 3 periods):
  all_3_positive = all(fcf[-3:] > 0) → +10
  declining_fcf  = fcf[-1] < fcf[-2] → -10  # latest worse than prior

cf_capex_score = clamp(fcf_margin_score + trend_adj, 0, 100)
```

#### C. Financing Quality Score (`cf_financing_score`) — Weight 25%

```
latest_cfo = cfo_series[-1]   (most recent period)
latest_cff = cff_series[-1]   (most recent period)

CFO vs CFF Sign Matrix:
  CFO > 0  AND  CFF < 0  → 85  (repaying debt from strong operations: best)
  CFO > 0  AND  CFF > 0  → 60  (expansion mode, raising capital: acceptable)
  CFO < 0  AND  CFF < 0  → 30  (forced repayment with weak operations: bad)
  CFO < 0  AND  CFF > 0  → 10  (distressed: burning cash + raising more: worst)
  Either None             → 50  (neutral)
```

#### Composite CF Score

```
cf_score = (
    0.40 × cf_operating_score
  + 0.35 × cf_capex_score
  + 0.25 × cf_financing_score
)
```

**Return Dict**:
```python
{
  "cf_score": float,
  "cf_operating_score": float,
  "cf_capex_score": float,
  "cf_financing_score": float,
  "details": {
    "cfo_pat_ratio": float | None,
    "cfo_consistency_pct": float,    # 0–100
    "fcf_margin": float | None,      # %
    "fcf_trend_adj": int,            # +10, -10, or 0
    "latest_cfo": float | None,
    "latest_cff": float | None
  }
}
```

### 3.4 Overall / Composite Score

```
# Default weights:
W_PL = 0.40  |  W_BS = 0.35  |  W_CF = 0.25

# Adaptive weighting: redistribute weight of missing statements
available = [(pl_score, W_PL), (bs_score, W_BS), (cf_score, W_CF)]
valid     = [(s, w) for s, w in available if s is not None]
total_w   = sum(w for _, w in valid)

composite_fundamental_score = round(
    sum(s × (w / total_w) for s, w in valid), 3
) if valid else None
```

### 3.5 Normalization Reference Table

| Metric | Score = 0 | Score = 100 | Direction |
|---|---|---|---|
| Revenue CAGR | 0% | 20% | Higher = better |
| PAT CAGR | < 0% | ≥ 25% | Higher = better |
| OPM % | < 5% | ≥ 25% | Higher = better |
| EPS consistency | 0% of years | 100% of years | Higher = better |
| D/E Ratio | > 2.5× | ≤ 0.25× | **Lower = better** |
| Current Ratio | < 1.0 | ≥ 2.5 | Higher = better |
| CWIP / Total Assets | — | — | Penalty flag (−10) if > 15% |
| Total Asset CAGR | 0% | ≥ 15% | Higher = better |
| Reserves CAGR | 0% | ≥ 15% | Higher = better |
| CFO / PAT | < 0 | ≥ 1.2 | Higher = better |
| FCF Margin | < 0% | ≥ 15% | Higher = better |

### 3.6 Edge Case Handling

| Case | Handling |
|---|---|
| Only 1 annual period available | CAGR = `None` → neutral 50; bracket scores from latest period still computed |
| `net_profit < 0` (loss year) | Used in loss_years count; `safe_div(cfo, pat)` returns `None` if denom ≤ 0 |
| Division by zero | `safe_div(num, denom)` returns `None` |
| All periods None for a metric | Sub-score = `None` → excluded from weighted average |
| Entire statement missing (no rows) | Statement score = `None` → adaptive composite weighting |
| NaN or string values in JSONB | `_clean_series()` maps to `None` |
| Stock without PL for CF scoring | `pl_data=None` → FCF margin fallback; CFO/PAT = neutral 50 |

---

## 4. Pseudocode

### 4.1 PL Scoring

```
FUNCTION score_pl(periods, data):
    sales    = _clean_series(data["sales"]   OR data["revenue"])
    pat      = _clean_series(data["net_profit"])
    opm_vals = _clean_series(data["operating_profit"])
    eps      = _clean_series(data["eps_in_rs"] OR data["eps"])

    # --- pl_growth_score ---
    rev_cagr = _cagr(sales, years=5)
    pat_cagr = _cagr(pat, years=5)

    rev_cagr_score = _bracket_rev_cagr(rev_cagr)   # lookup table
    pat_cagr_score = _bracket_pat_cagr(pat_cagr)

    loss_years = COUNT(v in pat WHERE v < 0)
    pat_cagr_score = MAX(0, pat_cagr_score - MIN(loss_years * 15, 30))

    pl_growth_score = (rev_cagr_score + pat_cagr_score) / 2

    # --- pl_margin_score ---
    opm_series = [safe_div(opm_vals[i], sales[i]) * 100 for i in periods]
    latest_opm = _last(opm_series)
    base_margin = _bracket_opm(latest_opm)
    sigma = _stddev(opm_series)
    stability = +10 if sigma <= 3 else (-10 if sigma > 10 else 0)
    pl_margin_score = CLAMP(base_margin + stability, 0, 100)

    # --- pl_eps_score ---
    growth_count = COUNT(i WHERE eps[i] > eps[i-1])
    base_eps = (growth_count / (len(eps) - 1)) * 100
    bonus = +10 if eps[-1] > MEAN(eps) * 1.2 else 0
    pl_eps_score = CLAMP(base_eps + bonus, 0, 100)

    # --- pl_consistency_score ---
    pl_consistency_score = MAX(0, 100 - loss_years * 20)

    # --- composite ---
    pl_score = 0.25*pl_growth_score + 0.25*pl_margin_score
             + 0.25*pl_eps_score    + 0.25*pl_consistency_score

    RETURN {
        pl_score, pl_growth_score, pl_margin_score,
        pl_eps_score, pl_consistency_score,
        details: {rev_cagr, pat_cagr, latest_opm, sigma, loss_years}
    }
```

### 4.2 BS Scoring

```
FUNCTION score_bs(periods, data):
    borr  = _clean_series(data["borrowings"])
    res   = _clean_series(data["reserves"])
    eq    = _clean_series(data["equity_capital"])
    ca    = _clean_series(data["current_assets"])
    cl    = _clean_series(data["current_liabilities"])
    ta    = _clean_series(data["total_assets"])
    cwip  = _clean_series(data["cwip"])

    # --- bs_leverage_score ---
    de = safe_div(borr[-1], (res[-1] + eq[-1]) if res[-1] or eq[-1] else None)
    bs_leverage_score = _score_de(de)

    # --- bs_liquidity_score ---
    cr = safe_div(ca[-1], cl[-1])
    cr_score = _score_current_ratio(cr)
    cwip_pct = safe_div(cwip[-1], ta[-1])
    cwip_penalty = -10 if cwip_pct and cwip_pct > 0.15 else 0
    bs_liquidity_score = CLAMP(cr_score + cwip_penalty, 0, 100)

    # --- bs_asset_score ---
    ta_cagr = _cagr(ta, years=5)
    bs_asset_score = _bracket_ta_cagr(ta_cagr)

    # --- bs_networth_score ---
    res_cagr = _cagr(res, years=5)
    bs_networth_score = _bracket_res_cagr(res_cagr)

    # --- composite ---
    bs_score = 0.30*bs_leverage_score + 0.20*bs_liquidity_score
             + 0.20*bs_asset_score    + 0.30*bs_networth_score

    RETURN {
        bs_score, bs_leverage_score, bs_liquidity_score,
        bs_asset_score, bs_networth_score,
        details: {de, cr, cwip_pct, ta_cagr, res_cagr}
    }
```

### 4.3 CF Scoring

```
FUNCTION score_cf(periods, cf_data, pl_data=None):
    cfo = _clean_series(cf_data["cash_from_operating_activity"])
    cfi = _clean_series(cf_data["cash_from_investing_activity"])
    cff = _clean_series(cf_data["cash_from_financing_activity"])
    pat = _clean_series(pl_data["net_profit"]) if pl_data else []
    rev = _clean_series(pl_data["sales"])      if pl_data else []

    # --- cf_operating_score ---
    cfo_pat = safe_div(cfo[-1], pat[-1]) if pat else None
    base_op  = _score_cfo_pat(cfo_pat)
    pos_cfo  = COUNT(v in cfo WHERE v > 0) / len(cfo)
    cons_adj = +10 if pos_cfo > 0.80 else (-15 if pos_cfo < 0.50 else 0)
    cf_operating_score = CLAMP(base_op + cons_adj, 0, 100)

    # --- cf_capex_score ---
    fcf = [cfo[i] + cfi[i] for i in range(len(cfo)) WHERE both non-None]
    IF rev:
        fcf_margin = safe_div(fcf[-1], rev[-1])
        base_capex = _bracket_fcf_margin(fcf_margin)
    ELSE:
        base_capex = 75 if fcf[-1] > 0 else 20
    trend_adj = +10 if ALL(fcf[-3:] > 0) else (-10 if fcf[-1] < fcf[-2] else 0)
    cf_capex_score = CLAMP(base_capex + trend_adj, 0, 100)

    # --- cf_financing_score ---
    cf_financing_score = _score_financing(cfo[-1], cff[-1])

    # --- composite ---
    cf_score = 0.40*cf_operating_score + 0.35*cf_capex_score
             + 0.25*cf_financing_score

    RETURN {
        cf_score, cf_operating_score, cf_capex_score, cf_financing_score,
        details: {cfo_pat, pos_cfo*100, fcf_margin, trend_adj, cfo[-1], cff[-1]}
    }
```

### 4.4 Overall Score Aggregation

```python
# LangGraph Orchestrator Flow

def graph_node_fetch(state: ScoringState):
    # Parallel fetch of PL, BS, CF from DB
    state.pl = await fetch_statement(state.stock_id, "PL")
    state.bs = await fetch_statement(state.stock_id, "BS")
    state.cf = await fetch_statement(state.stock_id, "CF")
    return state

def graph_node_score(state: ScoringState):
    # 100% Deterministic execution
    state.pl_scores = score_pl(state.pl)
    state.bs_scores = score_bs(state.bs)
    state.cf_scores = score_cf(state.cf, state.pl)
    state.composite = compute_adaptive_weights(...)
    return state

def graph_node_reasoning(state: ScoringState):
    # LLM Step (Synthesis ONLY)
    prompt = build_prompt(state.pl_scores, state.bs_scores, state.cf_scores)
    response = llm.predict(prompt)  # Structured output
    state.reasoning_label = response.label
    state.reasoning_text = response.text
    return state

def graph_node_persist(state: ScoringState):
    await upsert_to_db(state)
    return state
```

---

## 5. Database Design

### 5.1 New Table: `fundamental_scores`

```sql
CREATE TABLE fundamental_scores (
    id                          SERIAL PRIMARY KEY,

    -- Foreign key to stocks master
    stock_id                    INTEGER NOT NULL
                                    REFERENCES stocks(id) ON DELETE CASCADE,

    -- Scoring period (aligned to financial year end)
    period_end                  DATE    NOT NULL,
    period_type                 VARCHAR(10) NOT NULL DEFAULT 'annual',

    -- Statement-level scores (0–100 scale, 3 decimal precision)
    pl_score                    NUMERIC(6, 3),
    bs_score                    NUMERIC(6, 3),
    cf_score                    NUMERIC(6, 3),

    -- P&L sub-components
    pl_growth_score             NUMERIC(6, 3),   -- revenue & PAT CAGR blend
    pl_margin_score             NUMERIC(6, 3),   -- OPM quality + stability
    pl_eps_score                NUMERIC(6, 3),   -- EPS YoY consistency
    pl_consistency_score        NUMERIC(6, 3),   -- no-loss-year track record

    -- Balance Sheet sub-components
    bs_leverage_score           NUMERIC(6, 3),   -- D/E ratio bracket
    bs_liquidity_score          NUMERIC(6, 3),   -- current ratio + CWIP flag
    bs_asset_score              NUMERIC(6, 3),   -- total asset CAGR
    bs_networth_score           NUMERIC(6, 3),   -- reserves CAGR

    -- Cash Flow sub-components
    cf_operating_score          NUMERIC(6, 3),   -- CFO/PAT + consistency
    cf_capex_score              NUMERIC(6, 3),   -- FCF margin & trend
    cf_financing_score          NUMERIC(6, 3),   -- financing CF quality

    -- Composite (adaptive weighted blend of PL+BS+CF)
    composite_fundamental_score NUMERIC(6, 3),

    -- LLM Final Reasoning Layer outputs
    reasoning_label             VARCHAR(50),     -- e.g., "Strong Base", "High Leverage Risk"
    reasoning_text              TEXT,            -- Human-readable synthesized reasoning

    -- Versioning & audit
    score_version               VARCHAR(10)  NOT NULL DEFAULT 'v1',
    computed_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- Prevent duplicate scores for same stock+period+type
    CONSTRAINT uq_fundamental_scores_stock_period
        UNIQUE (stock_id, period_end, period_type)
);
```

### 5.2 Indexing Strategy

```sql
-- Primary lookup: latest score per stock
CREATE INDEX ix_fundamental_scores_stock_period
    ON fundamental_scores (stock_id, period_end DESC);

-- Screener-style queries: rank all stocks by composite score
CREATE INDEX ix_fundamental_scores_composite
    ON fundamental_scores (composite_fundamental_score DESC NULLS LAST)
    WHERE period_type = 'annual';

-- Version-based queries (for A/B comparison during threshold tuning)
CREATE INDEX ix_fundamental_scores_version
    ON fundamental_scores (score_version, computed_at DESC);
```

### 5.3 SQLAlchemy Model

```python
# backend/app/models.py  — add to existing file

class FundamentalScore(Base):
    __tablename__ = "fundamental_scores"
    __table_args__ = (
        UniqueConstraint(
            'stock_id', 'period_end', 'period_type',
            name='uq_fundamental_scores_stock_period'
        ),
        Index('ix_fundamental_scores_stock_period', 'stock_id', 'period_end'),
        Index('ix_fundamental_scores_composite',    'composite_fundamental_score'),
    )

    id                          = Column(Integer, primary_key=True, autoincrement=True)
    stock_id                    = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    period_end                  = Column(Date, nullable=False)
    period_type                 = Column(String(10), nullable=False, default="annual")

    pl_score                    = Column(Numeric(6, 3))
    bs_score                    = Column(Numeric(6, 3))
    cf_score                    = Column(Numeric(6, 3))

    pl_growth_score             = Column(Numeric(6, 3))
    pl_margin_score             = Column(Numeric(6, 3))
    pl_eps_score                = Column(Numeric(6, 3))
    pl_consistency_score        = Column(Numeric(6, 3))

    bs_leverage_score           = Column(Numeric(6, 3))
    bs_liquidity_score          = Column(Numeric(6, 3))
    bs_asset_score              = Column(Numeric(6, 3))
    bs_networth_score           = Column(Numeric(6, 3))

    cf_operating_score          = Column(Numeric(6, 3))
    cf_capex_score              = Column(Numeric(6, 3))
    cf_financing_score          = Column(Numeric(6, 3))

    composite_fundamental_score = Column(Numeric(6, 3))
    reasoning_label             = Column(String(50))
    reasoning_text              = Column(Text)

    score_version               = Column(String(10), nullable=False, default="v1")
    computed_at                 = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    stock = relationship("Stock", back_populates="fundamental_scores")
```

### 5.4 Alembic Migration

```python
# backend/alembic/versions/xxxx_add_fundamental_scores.py

"""Add fundamental_scores table

Revision ID: xxxx
Revises: <previous_revision>
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        "fundamental_scores",
        sa.Column("id",                          sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("stock_id",                    sa.Integer(), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_end",                  sa.Date(),    nullable=False),
        sa.Column("period_type",                 sa.String(10), nullable=False, server_default="annual"),
        sa.Column("pl_score",                    sa.Numeric(6, 3)),
        sa.Column("bs_score",                    sa.Numeric(6, 3)),
        sa.Column("cf_score",                    sa.Numeric(6, 3)),
        sa.Column("pl_growth_score",             sa.Numeric(6, 3)),
        sa.Column("pl_margin_score",             sa.Numeric(6, 3)),
        sa.Column("pl_eps_score",                sa.Numeric(6, 3)),
        sa.Column("pl_consistency_score",        sa.Numeric(6, 3)),
        sa.Column("bs_leverage_score",           sa.Numeric(6, 3)),
        sa.Column("bs_liquidity_score",          sa.Numeric(6, 3)),
        sa.Column("bs_asset_score",              sa.Numeric(6, 3)),
        sa.Column("bs_networth_score",           sa.Numeric(6, 3)),
        sa.Column("cf_operating_score",          sa.Numeric(6, 3)),
        sa.Column("cf_capex_score",              sa.Numeric(6, 3)),
        sa.Column("cf_financing_score",          sa.Numeric(6, 3)),
        sa.Column("composite_fundamental_score", sa.Numeric(6, 3)),
        sa.Column("reasoning_label",             sa.String(50)),
        sa.Column("reasoning_text",              sa.Text()),
        sa.Column("score_version",               sa.String(10), nullable=False, server_default="v1"),
        sa.Column("computed_at",                 sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("stock_id", "period_end", "period_type", name="uq_fundamental_scores_stock_period"),
    )
    op.create_index("ix_fundamental_scores_stock_period", "fundamental_scores", ["stock_id", "period_end"])
    op.create_index("ix_fundamental_scores_composite",    "fundamental_scores", ["composite_fundamental_score"])
    op.create_index("ix_fundamental_scores_version",      "fundamental_scores", ["score_version", "computed_at"])

def downgrade():
    op.drop_index("ix_fundamental_scores_version",   table_name="fundamental_scores")
    op.drop_index("ix_fundamental_scores_composite", table_name="fundamental_scores")
    op.drop_index("ix_fundamental_scores_stock_period", table_name="fundamental_scores")
    op.drop_table("fundamental_scores")
```

### 5.5 Historical Tracking Design

- Each `(stock_id, period_end, period_type)` tuple is unique → one score row per financial year end.
- Re-running the scorer **upserts** (overwrites) — scores are recomputed deterministically from the same source data.
- `score_version` flag enables A/B comparison when thresholds are tuned (change version string before re-running to preserve old rows).
- `computed_at` timestamp enables audit trail of when each score was last recalculated.
- Historical querying: `ORDER BY period_end DESC LIMIT 1` for latest; remove `LIMIT` for trend analysis.

---

## 6. API Integration Plan

### 6.1 Data Source — Existing Endpoints

The scorer **reads from** the same data that backs the existing fundamentals endpoints:

```
GET /api/v1/stocks/{symbol}/fundamentals?statement_type=PL
GET /api/v1/stocks/{symbol}/fundamentals?statement_type=BS
GET /api/v1/stocks/{symbol}/fundamentals?statement_type=CF
```

The SQL used internally mirrors the endpoint query:

```sql
SELECT period_end, data
FROM   financial_statements
WHERE  stock_id      = $1
  AND  statement_type = $2
  AND  period_type    = 'annual'
ORDER  BY period_end DESC
LIMIT  5;
```

### 6.2 New Admin Trigger Endpoint

```python
# backend/app/routers/pipeline.py — add to existing router

@router.post(
    "/statement-scores/run",
    summary="Trigger fundamental statement scoring for all stocks",
    status_code=202,
)
async def trigger_statement_scoring(
    background_tasks: BackgroundTasks,
    current_user: str = Depends(security.require_admin),
):
    """
    Runs score_pl, score_bs, score_cf for every stock with financial_statements.
    Upserts results into fundamental_scores. Non-blocking (background task).
    """
    from pipeline.statement_scorer import run_statement_score_all
    background_tasks.add_task(run_statement_score_all)
    return {
        "status": "accepted",
        "message": "Statement scoring job queued",
        "endpoint": "/api/v1/pipeline/statement-scores/run",
    }


@router.post(
    "/statement-scores/run/{symbol}",
    summary="Trigger fundamental scoring for a single stock",
)
async def trigger_statement_scoring_single(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(security.require_admin),
):
    from pipeline.statement_scorer import compute_statement_scores_for_stock
    stock = await crud.get_stock_by_symbol(db, symbol.upper())
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{symbol}' not found")
    await compute_statement_scores_for_stock(stock.id)
    return {"status": "ok", "symbol": symbol, "message": "Scoring complete"}
```

### 6.3 Score Read Endpoint (Optional — for UI display)

```python
# Can be added to existing stocks router

@router.get(
    "/{symbol}/fundamental-score",
    summary="Get latest fundamental scores for a stock",
)
async def get_fundamental_score(
    symbol: str,
    db: AsyncSession = Depends(get_db),
):
    sql = """
        SELECT fs.*
        FROM   fundamental_scores fs
        JOIN   stocks s ON s.id = fs.stock_id
        WHERE  s.symbol     = $1
          AND  fs.period_type = 'annual'
        ORDER  BY fs.period_end DESC
        LIMIT  1
    """
    async with raw_connection() as conn:
        row = await conn.fetchrow(sql, symbol.upper())
    if not row:
        raise HTTPException(status_code=404, detail="No fundamental score found")
    return dict(row)
```

### 6.4 Integration with Rating Engine

```python
# backend/pipeline/rating_engine.py — optional enhancement

async def _get_composite_fundamental_score(stock_id: int) -> float | None:
    """
    Fetches the pre-computed composite fundamental score from fundamental_scores table.
    Falls back to None if not available (rating engine will use legacy ratio-based score).
    """
    sql = """
        SELECT composite_fundamental_score
        FROM   fundamental_scores
        WHERE  stock_id    = $1
          AND  period_type = 'annual'
        ORDER  BY period_end DESC
        LIMIT  1
    """
    async with raw_connection() as conn:
        row = await conn.fetchrow(sql, stock_id)
    return float(row["composite_fundamental_score"]) if row else None
```

### 6.5 Caching Strategy

| Approach | Recommendation |
|---|---|
| **Scores table as cache** | `fundamental_scores` IS the cache — scores are pre-computed nightly and served directly. No Redis needed. |
| **API response caching** | If GET `/fundamental-score` is high-traffic: add `Cache-Control: max-age=3600` header (scores change only nightly). |
| **Re-computation trigger** | Admin `POST /statement-scores/run/{symbol}` bypasses cache and forces a fresh upsert. |
| **TTL invalidation** | Not needed — upsert on `computed_at` ensures the latest run always wins. |

---

## 7. Implementation Plan

### 7.1 Step-by-Step Execution

| Step | Action | File | Priority |
|---|---|---|---|
| 1 | Create Alembic migration for `fundamental_scores` | `alembic/versions/xxxx_add_fundamental_scores.py` | **P0** |
| 2 | Run `alembic upgrade head` | — | **P0** |
| 3 | Add `FundamentalScore` SQLAlchemy model | `app/models.py` | **P0** |
| 4 | Create `pipeline/statement_scorer.py` with all scoring functions | NEW file | **P0** |
| 5 | Add `run_statement_score_all()` orchestrator to `statement_scorer.py` | Same file | **P0** |
| 6 | Add admin trigger endpoint | `app/routers/pipeline.py` | **P1** |
| 7 | Hook `run_statement_score_all()` into `scheduler.py` | `pipeline/scheduler.py` | **P1** |
| 8 | (Optional) Update `rating_engine.py` to use `composite_fundamental_score` | `pipeline/rating_engine.py` | **P2** |
| 9 | Write unit tests | `tests/test_statement_scorer.py` | **P1** |
| 10 | Update `docs/DATABASE.md` with new table entry | `docs/DATABASE.md` | **P2** |

### 7.2 File Structure

```
backend/
├── pipeline/
│   └── statement_scorer.py           ← NEW (primary deliverable)
├── app/
│   ├── models.py                     ← MODIFY (add FundamentalScore class)
│   └── routers/
│       └── pipeline.py               ← MODIFY (add 2 new endpoints)
├── alembic/
│   └── versions/
│       └── xxxx_add_fundamental_scores.py  ← NEW migration
└── tests/
    └── test_statement_scorer.py      ← NEW unit tests
```

### 7.3 Naming Conventions

| Concept | Convention | Example |
|---|---|---|
| Scoring module | `snake_case`, `_scorer` suffix | `statement_scorer.py` |
| Score functions | `score_<statement>()` | `score_pl()`, `score_bs()`, `score_cf()` |
| Sub-score keys | `<statement>_<dimension>_score` | `pl_growth_score`, `bs_leverage_score` |
| DB table | `snake_case`, plural | `fundamental_scores` |
| Composite key | `composite_fundamental_score` | — |
| SQLAlchemy model | `PascalCase` | `FundamentalScore` |
| Alembic message | imperative verb | `"Add fundamental_scores table"` |
| Pipeline runner | `run_<action>_all()` | `run_statement_score_all()` |
| Internal helpers | `_snake_case` (private) | `_get_merged_statement()` |

### 7.4 Testing Plan

```python
# tests/test_statement_scorer.py

# Test data: mock JSONB for 5 annual periods

MOCK_PL = {
    "sales":             [50000, 60000, 72000, 85000, 92000],
    "net_profit":        [4000,  5200,  6800,  7500,  8100],
    "operating_profit":  [9000, 11000, 14000, 16000, 17500],
    "eps_in_rs":         [12.0,  15.5,  20.0,  22.5,  24.1],
}

MOCK_BS = {
    "borrowings":           [15000, 13000, 10000, 8000, 6000],   # deleveraging
    "reserves":             [25000, 30000, 36000, 43000, 51000],
    "equity_capital":       [5000,  5000,  5000,  5000,  5000],
    "total_assets":         [55000, 60000, 65000, 72000, 80000],
    "current_assets":       [20000, 22000, 25000, 28000, 31000],
    "current_liabilities":  [10000, 11000, 12000, 13000, 14000],
    "cwip":                 [2000,  2500,  3000,  2500,  2000],
}

MOCK_CF = {
    "cash_from_operating_activity": [5000, 6500, 8000, 9000, 9500],
    "cash_from_investing_activity": [-3000, -4000, -5000, -4000, -3500],
    "cash_from_financing_activity": [-1000, -1500, -1200, -800, -600],
}

# Test cases:
# 1. score_pl(MOCK_PL) → assert pl_score > 80  (strong growing company)
# 2. score_bs(MOCK_BS) → assert bs_score > 75  (deleveraging, liquid)
# 3. score_cf(MOCK_CF, pl_data=MOCK_PL) → assert cf_score > 70
# 4. Test edge: 1 period only → CAGR = None, bracket scores still run
# 5. Test edge: all negative PAT → pl_consistency_score = 0
# 6. Test edge: missing CF data → cf_score = None, composite adapts weights
# 7. Test safe_div(x, 0) → None
# 8. Test _cagr([100, None, 200], years=2) → valid CAGR ignoring None
```

### 7.5 Verification Checklist

- [ ] `alembic upgrade head` completes without errors
- [ ] `fundamental_scores` table visible in psql with correct schema
- [ ] `POST /api/v1/pipeline/statement-scores/run` returns `202 Accepted`
- [ ] `SELECT * FROM fundamental_scores LIMIT 5` shows non-null scores
- [ ] Manually cross-validate RELIANCE scores against screener.in data
- [ ] `composite_fundamental_score` is between 0 and 100 for all rows
- [ ] Stocks with no financial statements have no row (not a 0-score row)
- [ ] All unit tests in `tests/test_statement_scorer.py` pass

---

## Appendix — Composite Weights Summary

| Dimension | Sub-Component | Weight in Dimension | Dimension Weight | Effective Weight |
|---|---|---|---|---|
| **P&L** | Revenue + PAT Growth | 25% | 40% | 10.0% |
| | Margin Quality (OPM) | 25% | 40% | 10.0% |
| | EPS Consistency | 25% | 40% | 10.0% |
| | No-Loss Track Record | 25% | 40% | 10.0% |
| **Balance Sheet** | D/E Leverage | 30% | 35% | 10.5% |
| | Liquidity (CR + CWIP) | 20% | 35% | 7.0% |
| | Total Asset CAGR | 20% | 35% | 7.0% |
| | Reserves CAGR | 30% | 35% | 10.5% |
| **Cash Flow** | CFO Quality (CFO/PAT) | 40% | 25% | 10.0% |
| | FCF Margin & Trend | 35% | 25% | 8.75% |
| | Financing Quality | 25% | 25% | 6.25% |
| **TOTAL** | | | | **100%** |
