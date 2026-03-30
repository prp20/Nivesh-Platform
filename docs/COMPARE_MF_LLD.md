# Low Level Design: Mutual Fund Comparison Feature

## 1. Overview
The Mutual Fund Comparison feature allows users to perform a detailed head-to-head analysis of multiple mutual funds (up to 4) of the same category. This helps users make informed investment decisions based on performance and risk metrics.

## 2. Requirements
- **Max Funds**: 4
- **Same Type Only**: Comparison restricted to funds within the same `scheme_category`.
- **Metrics Focused**: Comparison based on rolling returns, risk ratios (Sharpe, Sortino, Alpha, Beta), and AUM.
- **Dynamic UI**: Responsive layout that adjusts from 2-way to 4-way comparison.
- **Chart Analysis**: Unified chart showing NAV trajectories for all selected funds and their benchmarks.

## 3. Backend Design

### 3.1 API Endpoint
**`GET /api/v1/funds/compare`**

**Query Parameters:**
- `codes`: Comma-separated list of scheme codes (e.g., `?codes=100033,100122,120121`)

**Validation Logic:**
1. Parse `codes` parameter.
2. If `count(codes) < 2` or `count(codes) > 4`, return `400 Bad Request`.
3. Fetch all funds. If any code is invalid, return `404 Not Found`.
4. Verify `scheme_category` of all fetched funds match. If not, return `400 Bad Request`.

**Response Structure:**
```json
[
  {
    "detail": { ...FundMasterRead... },
    "metrics": { ...FundMetricsRead... },
    "history": [ { "nav_date": "...", "nav_value": ... }, ... ],
    "benchHistory": [ { "nav_date": "...", "index_value": ... }, ... ]
  },
  ...
]
```

### 3.2 Data Flow
1. Fetch `FundMaster` with `joinedload(metrics)`.
2. Fetch `FundNavHistory` (last 500 points) for each fund.
3. Fetch `BenchmarkNavHistory` for each unique benchmark index across the funds.
4. Construct the unified response.

## 4. Frontend Design

### 4.1 UI Components
- **Comparison Table**: A grid-based layout where each column represents a fund.
    - Rows for: AMC, Category, Inception, 3Y Return, 5Y Return, Sharpe, Sortino, Alpha, Beta, Std Dev, AUM.
- **Multi-Line Chart**: Recharts `LineChart` with unique colors for each fund.
    - Primary colors: Blue, Red, Emerald, Amber.
    - Dashed lines for benchmarks.
- **Selection Bar**: (Optional enhancement) A sticky bar at the top showing selected funds and an option to add/remove.

### 4.2 State Management
- `codes`: Array of strings from URL params.
- `comparisonData`: Array of objects returned from backend.
- `loading`: Boolean status.
- `error`: Error message (for validation failures).

## 5. Security & Performance
- **Validation**: All constraints (max 4, same category) enforced on backend.
- **Efficiency**: Use `asyncio.gather` for parallel database queries.
- **Stale Data**: Metrics are served from the pre-computed `fund_metrics` table.

## 6. Future Enhancements
- Save comparison to user profile/watchlist.
- PDF export of comparison table.
- Comparison of funds across different categories (with warnings).
