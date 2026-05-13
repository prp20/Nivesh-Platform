# Code Review — Stock Nivesh Platform

**Date:** 2026-04-25  
**Reviewer:** Claude Code (automated, 5-agent parallel review)  
**Scope:** Full codebase — `backend/` and `frontend/src/`  
**Agents:** Backend Security, Backend Pipeline/Analytics, Backend API Design, Frontend Security/State, Frontend Components/UX

---

## Table of Contents

1. [Critical Issues](#1-critical-issues)
2. [High Severity Issues](#2-high-severity-issues)
3. [Medium Severity Issues](#3-medium-severity-issues)
4. [Low Severity Issues](#4-low-severity-issues)
5. [Summary Table](#5-summary-table)

---

## 1. Critical Issues

### BE-C1 · Secrets committed to version control

**File:** `backend/.env`  
**Lines:** 2, 10, 15, 18, 22

The `.env` file contains live production credentials: Supabase database connection string (with password), JWT `SECRET_KEY`, GROQ API key, LangSmith API key, and admin password hash. Anyone with repository access can access the production database and impersonate users.

**Fix:**
1. Rotate all exposed credentials immediately (DB password, JWT secret, all API keys).
2. Remove `.env` from git history: `git filter-branch --tree-filter 'rm -f backend/.env' -- --all`
3. Ensure `backend/.env` is in `.gitignore`.
4. Use environment-specific secret management (GitHub Secrets, AWS Secrets Manager) for CI/CD.

---

### BE-C2 · Sharpe ratio uses wrong standard deviation

**File:** `backend/app/analytics.py`  
**Line:** 51

```python
# BUG — denominator should be excess_returns.std(), not returns.std()
return float(np.sqrt(TRADING_DAYS_PER_YEAR) * excess_returns.mean() / returns.std())
```

The Sharpe ratio is `mean(excess_returns) / std(excess_returns)`. Using `returns.std()` produces systematically incorrect values and can lead to wrong investment decisions displayed to users.

**Fix:** Change `returns.std()` → `excess_returns.std()` on line 51.

---

### BE-C3 · ROIC calculated twice with hardcoded 25% tax rate

**File:** `backend/pipeline/ratio_engine.py`  
**Lines:** 172, 207

The `roic` key is defined twice in the same dict (copy-paste error). Both use `ebit * 0.75` — a hardcoded 25% tax assumption. India's effective tax rates vary from 15–42%, making this systematically wrong for most companies.

**Fix:** Remove the duplicate on line 207. Replace `0.75` with `(1 - tax_rate)` where `tax_rate` is derived from actual financial data (`tax_expense / profit_before_tax`), falling back to an industry estimate only if unavailable.

---

### BE-C4 · Timing attack on admin credential verification

**File:** `backend/app/routers/auth.py`  
**Lines:** 17–20

```python
credentials_match = (
    form_data.username == settings.ADMIN_USERNAME           # short-circuits here
    and security.verify_password(form_data.password, ...)
)
```

Short-circuit evaluation means `verify_password` is never called when the username is wrong. Response-time differences allow an attacker to enumerate valid usernames.

**Fix:** Always call `verify_password`, regardless of username match:
```python
username_match = form_data.username == settings.ADMIN_USERNAME
password_match = security.verify_password(form_data.password, settings.ADMIN_PASSWORD_HASH)
credentials_match = username_match and password_match
```

---

### BE-C5 · Inconsistent JWT SECRET_KEY handling between modules

**File:** `backend/app/main.py`  
**Line:** 114

`main.py` calls `.get_secret_value()` (for `SecretStr`) while `security.py` uses `SECRET_KEY` directly as a string. Depending on the Pydantic model type, one of these will fail at runtime with a type error.

**Fix:** Standardize to one pattern in both files:
```python
secret_key = settings.SECRET_KEY if isinstance(settings.SECRET_KEY, str) else settings.SECRET_KEY.get_secret_value()
```

---

### BE-C6 · Operating margin not converted to percentage — unit inconsistency

**File:** `backend/pipeline/ratio_engine.py`  
**Line:** 175

`pat_margin` and `ebitda_margin` are stored as percentages (multiplied by 100), but `operating_margin` is stored as a decimal (e.g., `0.15` instead of `15.0`). Downstream consumers that treat all margins as percentages will display wrong data.

**Fix:**
```python
"operating_margin": round(safe_div(ebit, revenue) * 100, 3) if ebit and revenue else None,
```

---

### FE-C1 · JWT token stored in localStorage (XSS risk)

**File:** `frontend/src/context/AuthContext.jsx`  
**Lines:** 13, 38, 46, 54; also `frontend/src/api/apiClient.js` lines 14, 32

`localStorage` is accessible to any JavaScript on the page. Any XSS vulnerability — present or future — immediately leaks the token.

**Fix:** Use an `httpOnly`, `Secure`, `SameSite=Strict` cookie set by the backend on login. The frontend removes all `localStorage.getItem/setItem` calls for the token and relies on the browser sending the cookie automatically on API requests.

---

### FE-C2 · No JWT expiry validation on the client

**File:** `frontend/src/context/AuthContext.jsx`

Tokens are loaded from localStorage and used without checking the `exp` claim. Expired or revoked tokens remain active in the UI until a 401 forces logout, creating a window where stale sessions appear valid.

**Fix:** Decode the JWT on `initAuth()` (using `jwt-decode` — no private key needed for decode), check `payload.exp * 1000 > Date.now()`, and log out immediately if expired. Set a timer to auto-logout when the token will expire.

---

### FE-C3 · Stale closure in StockDetail polling interval

**File:** `frontend/src/pages/StockDetail.jsx`  
**Lines:** 42–146

`triggerTime` and `symbol` are captured at callback-creation time but the `setInterval` callback continues running after the component re-renders (e.g., user navigates to a different stock). The polling loop uses stale values and may update state for the wrong stock.

**Fix:** Use a `useRef` to hold the latest symbol and trigger time, and always clear the interval in the effect cleanup:
```javascript
const symbolRef = useRef(symbol);
useEffect(() => { symbolRef.current = symbol; }, [symbol]);
// In handleSyncDaily:
return () => clearInterval(fundamentalsPollRef.current);
```

---

## 2. High Severity Issues

### BE-H1 · Debug exception messages returned to clients

**File:** `backend/app/routers/pipeline.py`  
**Lines:** 346, 402, 436

```python
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

Full exception messages (including stack traces from `str(e)`) expose internal paths, table names, and query structure to API consumers.

**Fix:** Return a generic message to the client; log the full error server-side:
```python
logger.error(f"Pipeline failed for {sym}: {e}", exc_info=True)
raise HTTPException(status_code=500, detail="Internal error — check server logs.")
```

---

### BE-H2 · Race condition in in-memory rate limiter

**File:** `backend/app/rate_limiting.py`  
**Lines:** 41–87

The rate limiter modifies `self.requests[key]` (a shared dict) from async handlers without locking. Under concurrent load, request counts can be lost (reads and writes interleave), allowing rate limit bypass.

**Fix:** Protect all reads and writes with `asyncio.Lock`:
```python
def __init__(self):
    self._lock = asyncio.Lock()

async def is_allowed(self, user_id, endpoint):
    async with self._lock:
        # existing logic
```

---

### BE-H3 · Database name exposed in public health endpoint

**File:** `backend/app/main.py`  
**Lines:** 170, 184–186

`GET /api/health` returns `{"database": {"name": "<actual-db-name>"}}` with no authentication. This aids reconnaissance.

**Fix:** Mask the value in production:
```python
"name": db_name if not settings.ENABLE_AUTH else "***"
```

---

### BE-H4 · Inventory turnover uses revenue instead of COGS

**File:** `backend/pipeline/ratio_engine.py`  
**Line:** 187

```python
"inventory_turnover": safe_div(revenue, inventory),
```

Standard formula is `COGS / Inventory`. Using revenue overstates turnover for companies with high gross margins.

**Fix:** Fetch `cogs` from financial statements:
```python
"inventory_turnover": safe_div(cogs, inventory) if cogs else None,
```

---

### BE-H5 · Payable days uses hardcoded 70% COGS estimate

**File:** `backend/pipeline/ratio_engine.py`  
**Line:** 189

```python
"payable_days": safe_div(payables, revenue * 0.7) * 365
```

The correct formula is `(Payables / COGS) × 365`. Hardcoding 70% as a COGS proxy introduces large systematic errors for asset-light businesses (e.g., IT services with 30–40% cost ratios).

**Fix:** Use actual COGS from financial statements; only fall back to the estimate if COGS is unavailable, with a comment documenting the approximation.

---

### BE-H6 · Audit job `_close_audit()` can raise silently in `finally`

**File:** `backend/pipeline/audit.py`  
**Lines:** 61–62, 79–87

`_close_audit()` is called in a `finally` block without try/except. If the database is unreachable, the exception from `_close_audit()` replaces the original exception, masking the real failure cause.

**Fix:**
```python
finally:
    if audit_id != -1:
        try:
            await _close_audit(audit_id, record)
        except Exception as exc:
            logger.error(f"Failed to close audit {audit_id}: {exc}")
```

---

### BE-H7 · Fundamental scraper stores statements without per-statement rollback

**File:** `backend/pipeline/fundamental_scraper.py`  
**Lines:** 118–123

Four sequential storage calls (`_store_pl`, `_store_bs`, `_store_cf`, `_store_shareholding`) share one connection. If `_store_cf` raises, P&L and Balance Sheet data are already written — the stock ends up with partial data and no way to detect the inconsistency.

**Fix:** Wrap the four calls in an explicit transaction block so partial writes are rolled back as a unit.

---

### BE-H8 · Missing database indexes for common query patterns

**File:** `backend/app/models.py`  
**Lines:** 85–109 (`FundNavHistory`, `BenchmarkNavHistory`)

Queries filtering by `scheme_code` alone (used in reports and sync checks) perform full table scans because the composite primary key is `(scheme_code, nav_date)` and there is no single-column index on `scheme_code`.

**Fix:** Add explicit indexes:
```python
Index('ix_fund_nav_scheme_code', 'scheme_code'),
Index('ix_bench_nav_benchmark_code', 'benchmark_code'),
```

---

### BE-H9 · EPS and shares_outstanding circular dependency

**File:** `backend/pipeline/ratio_engine.py`  
**Lines:** 106–107, 120

```python
eps    = latest("eps") or ...
shares = latest("shares_outstanding") or safe_div(pat, eps)  # uses eps
...
eps    = latest("eps") or safe_div(pat, shares)  # recalculates from shares
```

If `eps` is missing, `shares` falls back to `pat / eps` (which is None), so `shares` is also None. Then the second EPS calculation also fails. Neither value is ever populated even when `pat` is available.

**Fix:** Calculate `shares` first using only direct data, then derive `eps` from `shares` if missing:
```python
shares = latest("shares_outstanding")
eps    = latest("eps_in_rs") or latest("eps") or safe_div(pat, shares)
```

---

### BE-H10 · `FundMaster.metrics` relationship contract not enforced in schema

**File:** `backend/app/models.py`  
**Lines:** 65, 82

The ORM relationship uses `uselist=False` (one-to-one semantics), but `FundMetrics` has no `UNIQUE(scheme_code)` constraint. The database can hold multiple metric rows per fund; the ORM will silently return whichever SQLAlchemy picks first.

**Fix:** Add a unique constraint to `FundMetrics`:
```python
__table_args__ = (
    UniqueConstraint('scheme_code', name='uq_fund_metrics_scheme_code'),
)
```

---

### FE-H1 · `window.location.href` redirect in Axios interceptor

**File:** `frontend/src/api/apiClient.js`  
**Line:** 38

Using `window.location.href` bypasses React Router, discards unsaved form state, and prevents animated transitions. It also makes the auth flow untestable.

**Fix:** Emit a custom event or call a callback injected into the Axios instance so `AuthContext` can call `navigate('/login')` through the router.

---

### FE-H2 · No CSRF protection on state-changing requests

**File:** `frontend/src/api/apiClient.js`

POST/PUT/DELETE requests carry no CSRF token. If session cookies are adopted (from FE-C1 fix), CSRF becomes an active attack surface.

**Fix:** Add a request interceptor that attaches the CSRF token from a `<meta>` tag (set by the backend) on all mutating requests:
```javascript
if (['post','put','delete','patch'].includes(config.method)) {
    config.headers['X-CSRF-Token'] = document.querySelector('meta[name="csrf-token"]')?.content;
}
```

---

### FE-H3 · `Promise.all()` in Redux thunks aborts on first error

**File:** `frontend/src/store/slices/dashboardSlice.js` (lines 12–29); `frontend/src/store/slices/fundDetailSlice.js` (lines 8–26)

If any one of the parallel API calls rejects (e.g., benchmark data is temporarily unavailable), the entire thunk fails and the page shows nothing instead of partial data.

**Fix:** Use `Promise.allSettled()` and handle each result independently so non-critical failures degrade gracefully.

---

### FE-H4 · `Math.random()` inside `useMemo` produces non-deterministic portfolio values

**File:** `frontend/src/pages/Portfolio.jsx`  
**Lines:** 18–38

```javascript
const { portfolioHoldings } = React.useMemo(() => {
    return items.map(fund => ({
        valueNum: Math.random() * 500000 + 100000,  // random on every re-render trigger
        ...
    }));
}, [items]);
```

Every time `items` changes (e.g., background sync), portfolio values jump to new random numbers. This is a placeholder that has leaked into production-visible code.

**Fix:** Remove randomization entirely. Derive values from real fund data (NAV × units), or remove the field until real data is available.

---

### FE-H5 · Array index used as React `key` in list renders

**Files:** `Dashboard.jsx:146`, `Portfolio.jsx:81,107`, `StockListing.jsx:219`, `MFListing.jsx:195`, `Admin.jsx:221,495,568`, and comparison components

Using `key={i}` (array index) causes React to reuse component instances when items are reordered or filtered, leading to stale state, incorrect animation targets, and potential input focus bugs.

**Fix:** Use stable unique identifiers:
- Fund lists → `key={fund.scheme_code}`
- Stock lists → `key={stock.symbol}`
- Index lists → `key={idx.benchmark_code}`

---

### FE-H6 · Missing cleanup for async effects causes state updates on unmounted components

**File:** `frontend/src/pages/StockDetail.jsx`  
**Lines:** 51–61, 179–183, 190–194

`.then(res => setPriceHistory(...))` calls continue after the component unmounts (navigation away). React logs warnings and the resulting state update may corrupt the state of the newly mounted component.

**Fix:** Use an `isMounted` flag or `AbortController`, and return a cleanup function from the effect:
```javascript
useEffect(() => {
    let alive = true;
    stockService.getPriceHistory(symbol, ...).then(res => {
        if (alive) setPriceHistory(res.data);
    });
    return () => { alive = false; };
}, [...]);
```

---

### FE-H7 · `shareholding` in `useEffect` dependency array causes infinite re-fetch loop

**File:** `frontend/src/pages/StockDetail.jsx`  
**Lines:** 187–196

```javascript
}, [symbol, activeTab, stmtType, shareholding]); // shareholding triggers re-run after it's set
```

The effect sets `shareholding` → which changes the dependency → which re-runs the effect → which calls the API again. This creates an infinite loop of API requests.

**Fix:** Remove `shareholding` from the dependency array. The `!shareholding` guard inside the effect is sufficient to prevent duplicate fetches.

---

### FE-H8 · Unguarded property access causes runtime crashes on missing API fields

**File:** `frontend/src/pages/StockDetail.jsx`  
**Lines:** 286, 316, 543

```javascript
detail.market_cap_cat.toUpperCase()  // crashes if market_cap_cat is null
detail.industry.toUpperCase()        // crashes if industry is null
```

**Fix:** Use optional chaining:
```javascript
(detail?.market_cap_cat ?? '—').toUpperCase()
(detail?.industry ?? '—').toUpperCase()
```

---

## 3. Medium Severity Issues

### BE-M1 · N+1 query pattern in screener endpoint

**File:** `backend/app/routers/screener.py`  
**Lines:** 200–220

`LEFT JOIN LATERAL` subqueries for `financial_ratios`, `technical_indicators`, and `stock_ratings` execute a subquery per stock row to find the latest record. For large result sets (100+ stocks), this degrades significantly.

**Fix:** Replace LATERAL joins with a single CTE using `ROW_NUMBER() OVER (PARTITION BY stock_id ORDER BY period_end DESC)` to pre-filter the latest row per stock, then do a single join.

---

### BE-M2 · `"n/a"` strings stored in JSONB instead of NULL

**File:** `backend/pipeline/fundamental_scraper.py`  
**Lines:** 153–156

Missing values are stored as the string `"n/a"` in JSONB. Downstream code in `ratio_engine.py` defensively filters these out (`str(v).lower() != "n/a"`), but any new consumer of the raw JSONB that doesn't know this convention will silently compute wrong ratios.

**Fix:** Store `None` (JSON `null`) instead of `"n/a"`. Remove the `"n/a"` string filter in `ratio_engine.py` once data is clean.

---

### BE-M3 · Duplicate stock detail SQL in stocks router and screener router

**Files:** `backend/app/routers/stocks.py` (lines 173–232) and `backend/app/routers/screener.py` (lines 177–224)

The complex multi-join SQL to fetch a stock with its latest ratios and technicals is copy-pasted between two routers. A schema change or bug fix in one must be manually mirrored to the other.

**Fix:** Extract into a shared helper function in `crud.py` or a dedicated `stock_queries.py` module.

---

### BE-M4 · Piotroski F-Score uses `or 1` fallback for zero denominators

**File:** `backend/pipeline/ratio_engine.py`  
**Lines:** 468, 472, 478, 482

```python
de = borrowings / (shareholders_equity or 1)
```

When `shareholders_equity` is actually zero (a meaningful financial signal), dividing by 1 instead of returning `None` produces a meaningless ratio that silently passes into the F-Score calculation.

**Fix:** Use a `safe_div` that returns `None` when the denominator is zero, and propagate `None` through the F-Score rather than substituting 1.

---

### BE-M5 · Public read endpoints inconsistently bypass auth dependency

**Files:** `backend/app/routers/funds.py` (lines 22–50), `backend/app/routers/benchmarks.py` (lines 24–44)

Comments say "public access", but the auth dependency is sometimes present and sometimes absent across routers. With `ENABLE_AUTH=True` in production, any endpoint that accidentally includes the auth dependency will break for unauthenticated users.

**Fix:** Establish a clear convention: public reads have no auth dependency. Add integration tests that verify these endpoints return 200 without a token when `ENABLE_AUTH=True`.

---

### BE-M6 · Background pipeline tasks log "started" but never log failure

**File:** `backend/app/routers/pipeline.py`  
**Lines:** 43–68

Trigger endpoints log `"started in background"` but register no callback for completion or failure. The audit table shows every trigger as started; there is no way to determine from logs alone whether it succeeded.

**Fix:** Wrap background tasks in a helper that writes a `COMPLETED` or `FAILED` audit entry when the task resolves.

---

### BE-M7 · Unhandled naive datetime comparison in metrics router

**File:** `backend/app/routers/metrics.py`  
**Lines:** 49–51, 64–66

Timezone-naive datetimes from the DB are manually patched with `.replace(tzinfo=UTC)`. If the DB driver or ORM configuration ever returns aware datetimes, comparing aware and naive datetimes raises a `TypeError` at runtime.

**Fix:** Configure the async engine to always return timezone-aware datetimes:
```python
create_async_engine(..., connect_args={"server_settings": {"timezone": "UTC"}})
```
And use `TIMESTAMP(timezone=True)` on all columns.

---

### BE-M8 · `ComparisonResponse.ranking.recommendation_reason` is never populated

**Files:** `backend/app/schemas.py` (lines 205–220), `backend/app/routers/funds.py` (lines 123–133)

`FundRanking.recommendation_reason` is always `None` — the `rank_funds_for_comparison()` function in `analytics.py` does not set it. The field exists in the schema but is dead code that misleads API consumers.

**Fix:** Either populate the field with a human-readable reason (e.g., `"Best 3Y risk-adjusted return"`) or remove it from the schema.

---

### FE-M1 · No input validation on service layer URL parameters

**Files:** `frontend/src/api/services/fundService.js`, `stockService.js`

`schemeCode`, `symbol`, and category parameters are URL-encoded but not validated. Passing structurally invalid values (empty strings, path-traversal segments) generates confusing 404/422 errors with no client-side guidance.

**Fix:** Add lightweight validation before the API call:
```javascript
if (!symbol || !/^[A-Z0-9.\-]+$/.test(symbol)) throw new Error('Invalid symbol');
```

---

### FE-M2 · No AbortController support in Redux async thunks

**Files:** All Redux slices

In-flight API requests are never cancelled when a component unmounts or the user navigates away. React may log "state update on unmounted component" warnings, and stale responses can overwrite newer data.

**Fix:** Pass `signal` from `createAsyncThunk`'s second argument to Axios:
```javascript
export const fetchFunds = createAsyncThunk('funds/fetchFunds', async (params, { signal }) => {
    return fundService.getFunds(params, { signal });
});
```

---

### FE-M3 · No Content Security Policy configured

**File:** `frontend/index.html`

There are no CSP headers or meta tags. Inline script injection from a XSS attack is entirely unrestricted.

**Fix:** Add a CSP meta tag in `index.html` (and ideally as an HTTP header from the backend for the SPA shell):
```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self'; connect-src 'self' http://localhost:8000; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:;">
```

---

### FE-M4 · Login form has no client-side validation

**File:** `frontend/src/pages/Login.jsx`  
**Lines:** 50–95

Empty username or password are submitted directly to the API. The error message for a failed login is a raw backend string that may be undefined (`err.response?.data?.detail` can be `undefined` if the network is down).

**Fix:**
```javascript
if (!username.trim() || !password.trim()) {
    setError('Username and password are required');
    return;
}
const errorMsg = err?.response?.data?.detail || err?.message || 'Login failed. Please try again.';
```

---

### FE-M5 · Missing global unhandled promise rejection handler

**File:** `frontend/src/App.jsx` (or main entry)

Async errors outside of try/catch (e.g., in event handlers and thunks not caught by Redux) surface as silent failures. Users see a frozen UI with no feedback.

**Fix:** Add a global handler in `main.jsx`:
```javascript
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled rejection:', event.reason);
    toast.error('An unexpected error occurred');
});
```

---

## 4. Low Severity Issues

### BE-L1 · Rate limit `Retry-After` header value should be an integer string

**File:** `backend/app/main.py`  
**Lines:** 126–133

RFC 7231 requires `Retry-After` to be a decimal integer (seconds) or HTTP-date. Clients that strictly parse this header may reject a stringified float.

**Fix:** Ensure the value passed is `"60"` (string of integer), not a float representation.

---

### BE-L2 · Very high default rate limit on public endpoints

**File:** `backend/app/rate_limiting.py`  
**Line:** 24

`DEFAULT_LIMIT = (1000, 60)` allows 1000 requests/minute per user on all unlisted endpoints. This permits trivial database scraping.

**Fix:** Lower to 100–200 req/min for public read endpoints.

---

### BE-L3 · Missing HTTPS / security headers

**File:** `backend/app/main.py`

No `Strict-Transport-Security`, `X-Content-Type-Options`, or `X-Frame-Options` headers. These should be set either by the application or documented as a reverse-proxy responsibility.

---

### BE-L4 · Magic cache TTL numbers not extracted to constants

**File:** `backend/app/routers/metrics.py`  
**Lines:** 54, 68

`24` (hours) and `10` (minutes) are hardcoded inline. If the cache TTL needs changing, there are multiple places to update.

**Fix:** Define `METRICS_CACHE_TTL_HOURS = 24` and `SYNC_JOB_TIMEOUT_MINUTES = 10` in `app/constants.py`.

---

### BE-L5 · Beta calculation threshold too low for numerical stability

**File:** `backend/app/analytics.py`  
**Lines:** 254–257

```python
beta = covariance / variance if variance != 0 else 1.0
```

Comparing a float to exactly `0` is unreliable for near-zero variances (flat benchmark periods). Use a minimum threshold:
```python
beta = covariance / variance if variance > 1e-10 else 1.0
```

---

### BE-L6 · File upload content-type check too permissive

**File:** `backend/app/routers/benchmark_navs.py`  
**Line:** 32

`text/plain` is accepted for CSV uploads. Restrict to `text/csv` or `application/csv` only.

---

### FE-L1 · Console errors in production expose internal details

Console calls (`console.error`, `console.log`) are present throughout components and services. In production builds, these expose API error messages and stack traces in the browser developer console.

**Fix:** Gate console output behind `import.meta.env.DEV`:
```javascript
if (import.meta.env.DEV) console.error(...);
```

Or integrate a structured logging service.

---

### FE-L2 · Redux DevTools enabled in production

Redux DevTools exposes the entire application state (fund data, user session) in any browser with the extension installed.

**Fix:** Disable DevTools in the production Redux store configuration:
```javascript
devTools: import.meta.env.DEV,
```

---

## 5. Summary Table

| ID | Area | Severity | Description |
|----|------|----------|-------------|
| BE-C1 | Security | **CRITICAL** | Secrets committed to `.env` |
| BE-C2 | Analytics | **CRITICAL** | Sharpe ratio uses wrong std dev |
| BE-C3 | Pipeline | **CRITICAL** | ROIC duplicated with hardcoded 25% tax |
| BE-C4 | Security | **CRITICAL** | Timing attack on admin login |
| BE-C5 | Security | **CRITICAL** | JWT SECRET_KEY type inconsistency |
| BE-C6 | Pipeline | **CRITICAL** | Operating margin not converted to % |
| FE-C1 | Security | **CRITICAL** | JWT in localStorage (XSS) |
| FE-C2 | Security | **CRITICAL** | No JWT expiry validation |
| FE-C3 | React | **CRITICAL** | Stale closure in StockDetail poll |
| BE-H1 | Security | **HIGH** | Exception messages returned to clients |
| BE-H2 | Security | **HIGH** | Race condition in rate limiter |
| BE-H3 | Security | **HIGH** | DB name in public health endpoint |
| BE-H4 | Pipeline | **HIGH** | Inventory turnover uses revenue not COGS |
| BE-H5 | Pipeline | **HIGH** | Payable days uses hardcoded 70% COGS |
| BE-H6 | Pipeline | **HIGH** | `_close_audit()` swallows original error |
| BE-H7 | Pipeline | **HIGH** | Scraper: partial writes without transaction |
| BE-H8 | DB | **HIGH** | Missing indexes on nav history tables |
| BE-H9 | Pipeline | **HIGH** | EPS/shares circular dependency |
| BE-H10 | DB | **HIGH** | FundMetrics lacks UNIQUE constraint |
| FE-H1 | Security | **HIGH** | `window.location.href` in Axios interceptor |
| FE-H2 | Security | **HIGH** | No CSRF protection on mutations |
| FE-H3 | State | **HIGH** | `Promise.all()` aborts on first failure |
| FE-H4 | State | **HIGH** | `Math.random()` in `useMemo` (Portfolio) |
| FE-H5 | React | **HIGH** | Array index used as React key (12 files) |
| FE-H6 | React | **HIGH** | No async effect cleanup → state on unmounted |
| FE-H7 | React | **HIGH** | `shareholding` in deps → infinite loop |
| FE-H8 | React | **HIGH** | Unguarded property access → runtime crash |
| BE-M1 | Performance | **MEDIUM** | N+1 LATERAL JOINs in screener |
| BE-M2 | Data | **MEDIUM** | `"n/a"` strings stored instead of NULL |
| BE-M3 | Maintainability | **MEDIUM** | Duplicate stock detail SQL in two routers |
| BE-M4 | Analytics | **MEDIUM** | Piotroski uses `or 1` for zero denominators |
| BE-M5 | Auth | **MEDIUM** | Inconsistent public endpoint auth dependency |
| BE-M6 | Ops | **MEDIUM** | Background tasks log start but not failure |
| BE-M7 | DB | **MEDIUM** | Naive/aware datetime inconsistency |
| BE-M8 | API | **MEDIUM** | `recommendation_reason` never populated |
| FE-M1 | Validation | **MEDIUM** | No URL param validation in service layer |
| FE-M2 | State | **MEDIUM** | No AbortController in Redux thunks |
| FE-M3 | Security | **MEDIUM** | No Content Security Policy |
| FE-M4 | UX | **MEDIUM** | Login form has no client-side validation |
| FE-M5 | Errors | **MEDIUM** | No global unhandled rejection handler |
| BE-L1 | API | **LOW** | `Retry-After` header format |
| BE-L2 | Security | **LOW** | Default rate limit too high for public routes |
| BE-L3 | Security | **LOW** | No HTTPS / security headers |
| BE-L4 | Maintainability | **LOW** | Magic TTL numbers not in constants |
| BE-L5 | Analytics | **LOW** | Beta calculation float comparison to `0` |
| BE-L6 | Security | **LOW** | File upload accepts `text/plain` |
| FE-L1 | Ops | **LOW** | `console.error` in production |
| FE-L2 | Security | **LOW** | Redux DevTools enabled in production |

### Count by severity

| Severity | Backend | Frontend | Total |
|----------|---------|----------|-------|
| Critical | 6 | 3 | **9** |
| High | 10 | 8 | **18** |
| Medium | 8 | 5 | **13** |
| Low | 6 | 2 | **8** |
| **Total** | **30** | **18** | **48** |

### Recommended fix order

1. **Immediately:** BE-C1 (rotate leaked credentials) — do this before any other work.
2. **Before next deploy:** BE-C2, BE-C3, BE-C6 (financial calculation correctness), FE-C1 (JWT storage), FE-C3 (polling closure), BE-C4/C5 (auth security).
3. **This sprint:** All HIGH issues — especially BE-H4/H5 (ratio formula correctness), BE-H7 (partial write risk), FE-H3/H4/H5/H7/H8.
4. **Next sprint:** MEDIUM issues — particularly BE-M1 (screener performance), BE-M2 (data quality), FE-M2 (request cancellation).
5. **Tech debt:** LOW issues as bandwidth allows.
