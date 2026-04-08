# Backend Implementation Plan — Mutual Fund Comparison Feature

> **Role:** Senior Backend Engineer (FastAPI)
> **Reference:** [FEATURE_MF_COMPARISON.md](./FEATURE_MF_COMPARISON.md)
> **Date:** 2026-04-05

---

## 1. Audit Summary — Current State of Backend

I have audited every file in `backend/app/` and here is the current state after the partial changes made earlier. This plan accounts for what already exists and what still needs work.

### Files Already Modified (Partial Work From Prior Session)

| File | What Was Done | Status |
|---|---|---|
| `app/crud.py` | Added `get_distinct_categories()` and `get_distinct_subcategories()` | ✅ Done, needs review |
| `app/schemas.py` | Added `FundRanking`, `RankingResult`, extended `ComparisonResponse` with `ranking` field | ✅ Done, needs review |
| `app/routers/funds.py` | Added `/categories`, `/categories/{cat}/subcategories` endpoints; integrated ranking call into `/compare` | ✅ Done, needs review |
| `app/analytics.py` | Added full `rank_funds_for_comparison()` engine (~200 lines) with metric defs, group weights, normalisation | ✅ Done, needs review |

### Files NOT Modified (No Changes Needed)

| File | Reasoning |
|---|---|
| `app/models.py` | **No DB schema changes required.** All metrics needed for comparison already exist in `FundMetrics` table. The `FundMaster.scheme_category` column is already indexed (GIN trigram). |
| `app/database.py` | No changes. Standard async engine + session factory. |
| `app/config.py` | No new config keys needed. |
| `app/security.py` | Compare endpoints are public reads — no auth changes. |
| `app/sync.py` | Sync pipeline is independent. Comparison reads pre-computed metrics. |
| `app/main.py` | The `funds` router is already mounted; new endpoints auto-register. |
| `app/routers/metrics.py` | No changes. Metrics computation is triggered separately. |
| `app/routers/benchmarks.py` | Not involved. |
| `app/routers/navs.py` | Not involved. |
| `app/routers/benchmark_navs.py` | Not involved. |
| `app/routers/sync.py` | Not involved. |
| `app/routers/auth.py` | Not involved. |

---

## 2. Database Changes

### ✅ None Required

After auditing `app/models.py`:

- **`FundMaster`** already has `scheme_category` (indexed with GIN trigram) and `scheme_subcategory` — sufficient for category-based filtering and enforcement.
- **`FundMetrics`** already has every metric the comparison engine needs: `cagr_3year`, `cagr_5year`, `absolute_return_1y/3y/5y/10y`, `short_term_return_6m`, `sharpe_ratio`, `sortino_ratio`, `alpha`, `beta`, `standard_deviation`, `maximum_drawdown`, `tracking_error`, `information_ratio`, `upside_capture`, `downside_capture`, `expense_ratio`, `aum_in_crores`, `fund_rating`, `volatility`, `data_completeness_percentage`, `final_verdict`.
- No new tables or columns are needed. No migrations to write.

---

## 3. Implementation Tasks (Ordered)

### Task 1: Review & Harden `crud.py` — Category Queries
**File:** `app/crud.py` (lines 122–142)
**Status:** Already added, needs review

**What exists:**
```python
async def get_distinct_categories(session) -> List[str]
async def get_distinct_subcategories(session, category) -> List[str]
```

**Review checklist:**
- [ ] Verify `get_distinct_categories` only returns active fund categories
- [ ] Verify `get_distinct_subcategories` filters out `None` values correctly
- [ ] Verify both sort output alphabetically
- [ ] Consider caching (categories rarely change) — defer to P2, not blocking

---

### Task 2: Review & Harden `routers/funds.py` — New Endpoints
**File:** `app/routers/funds.py` (lines 50–59, 106–116)
**Status:** Already added, needs review

**What exists:**
- `GET /funds/categories` → returns `List[str]`
- `GET /funds/categories/{category}/subcategories` → returns `List[str]`
- `/compare` endpoint now calls `analytics.rank_funds_for_comparison()` and includes ranking in response

**Review checklist:**
- [ ] Verify `/categories` is placed **above** `/{scheme_code}` to avoid FastAPI path collision
- [ ] Verify duplicate `import asyncio` at line 68 (inside function) — should use the top-level import (line 1)
- [ ] Verify compare endpoint returns `ComparisonResponse` including the new `ranking` field
- [ ] Ensure error messages are descriptive for category mismatches
- [ ] Verify URL encoding safety for category path params (e.g., "Equity Scheme" with spaces)

---

### Task 3: Review & Harden `schemas.py` — Ranking Response Models
**File:** `app/schemas.py` (lines 215–235)
**Status:** Already added, needs review

**What exists:**
```python
class FundRanking(BaseModel):        # scheme_code, rank, composite_score, group_scores, wins, is_recommended, recommendation_reason
class RankingResult(BaseModel):      # rankings: List[FundRanking], comparison_summary: str
class ComparisonResponse(BaseModel): # funds, ranking (optional), warning (optional)
```

**Review checklist:**
- [ ] Verify `FundRanking.group_scores` type `Dict[str, float]` matches the 5 group keys returned by the engine
- [ ] Verify `wins: List[str]` — confirm this is the human-readable labels list, not raw metric keys
- [ ] Confirm `ComparisonResponse.ranking` is `Optional` (graceful for legacy callers)

---

### Task 4: Review & Harden `analytics.py` — Ranking Engine
**File:** `app/analytics.py` (lines 264–460)
**Status:** Already added, **most critical to review**

**What exists:**
- `_METRIC_DEFS` — 21 metrics mapped to `(higher_is_better, group)` tuples
- `_GROUP_WEIGHTS` — Returns 35%, Risk-Adjusted 30%, Risk 20%, Cost 10%, Consistency 5%
- `_METRIC_LABELS` / `_GROUP_LABELS` — Human-readable names
- `rank_funds_for_comparison(funds_metrics, scheme_codes)` → normalise → score → rank → recommend

**Review checklist:**
- [ ] **Metric polarity audit:**
  - `maximum_drawdown` is set to `higher_is_better=True` — correct because drawdown values are negative (e.g., -0.15), so a less negative value (higher) is better
  - `beta` is set to `higher_is_better=False` — acceptable (lower beta = less market risk), but debatable for aggressive investors. Document this assumption.
  - `volatility` vs `standard_deviation` — both map to "risk" group with `False`. Are both populated in DB? Could cause double-counting if both are always non-None. **Verify in DB.**
- [ ] **Edge cases:**
  - All funds have `None` for every metric → should return `composite_score: 0.0` for all, not crash
  - Only 1 fund has metrics, others are empty `{}` → should still rank (the one with data wins)
  - All funds are exactly tied on every metric → normalised = 50 for all, verify output
- [ ] **Recommendation reason generation:**
  - Line 431: `funds_metrics[scheme_codes.index(top["scheme_code"])]` — after sorting, `top["scheme_code"]` may not match original index. Verify this lookup is against the *original unsorted* lists.
  - Reason text construction — verify no crash if `wins` is empty
- [ ] **Consider adding `get_comparison_data` enhancement:** Currently fetches only `FundMetrics`. Should it also include `FundMaster` data (scheme_name, amc_name, inception_date, etc.) so the frontend doesn't need a second call?

---

### Task 5: Enhance `get_comparison_data()` — Include Fund Master Details
**File:** `app/analytics.py` (lines 236–262)
**Status:** Needs enhancement

**Current behavior:** Returns only `{ scheme_code, metrics: {...} }` per fund.

**Problem:** Frontend needs fund master info (scheme_name, AMC, inception_date, subcategory, ISIN) for the comparison table but would have to make N separate `GET /funds/{code}` calls.

**Proposed change:** Also fetch fund masters in parallel and include basic info:
```python
{
    "scheme_code": "119598",
    "fund_info": {
        "scheme_name": "...",
        "amc_name": "...",
        "scheme_category": "...",
        "scheme_subcategory": "...",
        "inception_date": "...",
        "plan_type": "...",
        "isin": "...",
        "benchmark_index_code": "..."
    },
    "metrics": { ... }
}
```

**Impact:** Eliminates N+1 API calls from frontend. One `GET /funds/compare?codes=...` returns everything needed.

---

### Task 6: Fix Redundant Import in `routers/funds.py`
**File:** `app/routers/funds.py` (line 68)
**Status:** Bug — `import asyncio` inside function body duplicates the top-level import at line 1

**Fix:** Remove `import asyncio` from line 68.

---

### Task 7: Write Unit Tests for Ranking Engine
**File:** `backend/tests/test_ranking.py` (NEW)
**Status:** Not started

**Test cases to cover:**

| # | Test Case | Expected |
|---|---|---|
| 1 | Two funds, both with complete metrics | Returns ranked list, best fund `is_recommended=True` |
| 2 | Three funds, one with empty metrics `{}` | Fund with data ranks higher, empty-metrics fund gets 0 scores |
| 3 | All funds tied on every metric | All get `composite_score` ≈ 50, ranks assigned arbitrarily |
| 4 | Only 1 fund (edge case) | Returns empty rankings with "Need at least 2" message |
| 5 | Fund with superior returns but poor risk | Verify weights balance correctly (returns fund may or may not win depending on risk penalty) |
| 6 | Metrics with `None` values mixed in | Normalisation skips None, doesn't crash |
| 7 | Extreme values (negative alpha, large drawdown) | Polarity applied correctly |
| 8 | Recommendation reason text | Non-empty, mentions the winning group and specific metrics |

**Testing approach:** Pure unit tests — `rank_funds_for_comparison` is a pure function (no DB, no async), so no mocking needed. Feed it synthetic dicts.

---

### Task 8: Add Compare Endpoint Tests to `test_api_simple.py`
**File:** `backend/test_api_simple.py`
**Status:** Current test at line 109 only checks `compare?codes=1,2` with `[200, 400]`

**Add these tests:**
```python
# Categories endpoint
test_endpoint("GET", "/funds/categories", 200)
test_endpoint("GET", "/funds/categories/Equity/subcategories", [200, 404])

# Compare — same category (should succeed with ranking)
test_endpoint("GET", "/funds/compare?codes=VALID1,VALID2", 200)

# Compare — different categories (should fail 400)
test_endpoint("GET", "/funds/compare?codes=EQUITY_FUND,DEBT_FUND", 400)

# Compare — more than 4 funds
test_endpoint("GET", "/funds/compare?codes=1,2,3,4,5", 400)

# Compare — single fund
test_endpoint("GET", "/funds/compare?codes=1", 400)
```

---

## 4. File Change Matrix

| File | Action | Lines Changed | Priority |
|---|---|---|---|
| `app/crud.py` | Review existing code | ~20 lines (122–142) | P0 |
| `app/schemas.py` | Review existing code | ~20 lines (215–235) | P0 |
| `app/routers/funds.py` | Review + fix redundant import + include fund_info | ~60 lines (50–116) | P0 |
| `app/analytics.py` | Review + enhance `get_comparison_data()` | ~200 lines (236–460) | P0 |
| `tests/test_ranking.py` | New file — unit tests | ~150 lines | P1 |
| `test_api_simple.py` | Add compare/category test cases | ~15 lines | P1 |
| `app/models.py` | **No changes** | 0 | — |
| `app/database.py` | **No changes** | 0 | — |
| `app/main.py` | **No changes** | 0 | — |
| `app/sync.py` | **No changes** | 0 | — |

---

## 5. TODO Checklist (Implementation Order)

```
Phase 1 — Review & Fix Existing Code
  [ ] 1.1  Review crud.py category queries (Task 1)
  [ ] 1.2  Review schemas.py ranking models (Task 3)
  [ ] 1.3  Review analytics.py ranking engine — polarity, edge cases, reason text (Task 4)
  [ ] 1.4  Review funds.py endpoints — path ordering, import cleanup (Task 2 + Task 6)

Phase 2 — Enhancements
  [ ] 2.1  Enhance get_comparison_data() to include fund_info (Task 5)
  [ ] 2.2  Update ComparisonResponse schema if fund_info shape changes

Phase 3 — Testing
  [ ] 3.1  Create tests/test_ranking.py with 8 test cases (Task 7)
  [ ] 3.2  Add compare & category tests to test_api_simple.py (Task 8)

Phase 4 — Validation
  [ ] 4.1  Start backend server and hit /docs — verify all new endpoints appear
  [ ] 4.2  curl /funds/categories — confirm category list returns
  [ ] 4.3  curl /funds/compare?codes=X,Y with same-category funds — verify full response with ranking
  [ ] 4.4  curl /funds/compare?codes=X,Y with different-category funds — verify 400 error
  [ ] 4.5  Run test_api_simple.py — verify all tests pass
  [ ] 4.6  Run pytest tests/test_ranking.py — verify all unit tests pass
```

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `volatility` and `standard_deviation` double-counting in risk group | Medium | Low (both are volatility proxies but sourced differently) | Verify DB — if both always populated, consider dropping one from `_METRIC_DEFS` |
| `maximum_drawdown` polarity confusion (negative values, higher_is_better=True) | Low | High (inverts ranking) | Unit test with known drawdown values (-0.05 vs -0.30) |
| Funds with no pre-computed metrics (never synced) | Medium | Medium (empty {} in response) | Ranking engine already handles `{}` → 0 scores. Frontend should show "Sync required" |
| Path collision `/categories` vs `/{scheme_code}` | Low | High (route never matched) | Already placed above `/{scheme_code}` — verified in audit |
| Large number of duplicate `asyncio.gather` calls in compare endpoint | Low | Low | Current parallel fetch is efficient; N ≤ 4 |

---

## 7. Notes for Future Consideration (Not in Scope)

- **Caching:** The `/categories` endpoint could be cached (categories rarely change). Consider `cachetools.TTLCache` or Redis.
- **Weighted slider:** The `_GROUP_WEIGHTS` are hardcoded in `analytics.py`. A future API enhancement could accept user-defined weights as query params.
- **Batch comparison history:** Storing comparison results for analytics (which funds are commonly compared, recommendation acceptance rate).
