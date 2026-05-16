# Stock Analyser — Design Spec
**Date:** 2026-05-17  
**Status:** Approved  
**Scope:** `nivesh-client` agent analysis pipeline + `AgentInsightsTab` UI

---

## Problem

The "Initialize Agent Analysis" button on the Stock Detail page calls `POST /agent/analyze/{symbol}`, which makes a single plain LLM call and returns unstructured text. The response has no scores, no pillar breakdown, and no structure that the `AgentInsightsTab` UI can render meaningfully. The three ScoreCards (P&L / Balance Sheet / Cash Flow) are populated with `null` values.

The legacy `stock_nivesh_platform/backend/agents/stock_analyser/` contains a production-grade 3-pillar scoring pipeline that should be repurposed here.

---

## Goals

- Produce a structured analysis with: fundamental score (0–95), technical signal, valuation signal, weighted composite score (0–95), and an LLM narrative
- Port the legacy scoring logic faithfully, adapting only where data is unavailable
- Never display a score of 100 — cap all scores at 95 to reflect prediction uncertainty
- No DB persistence (always recompute live on button press)
- No sector median dependency (absolute thresholds for valuation)
- No LangGraph graph — simple sequential function calls

---

## Architecture

```
Browser → POST /api/v1/agent/analyze/{symbol}   (agent.py)
               ↓
         GET /api/v1/proxy/stocks/{symbol}       (internal httpx, cached+auth)
               ↓
         stock_analyser.py (new module):
           score_fundamental(ratios)    → FundamentalResult
           score_technical(ti, price)   → TechnicalResult
           score_valuation(ratios)      → ValuationResult
           aggregate(f, t, v)           → AggregateResult
           generate_narrative(llm, ctx) → str
               ↓
         JSON response → fetchInsights() → AgentInsightsTab
```

---

## File Changes

| File | Change |
|------|--------|
| `nivesh-server/app/routers/stocks.py` | Add `ti.adx_14`, `ti.stoch_k` to `GET /stocks/{symbol}` SQL |
| `nivesh-client/app/agent/stock_analyser.py` | **New** — all scoring + narrative logic |
| `nivesh-client/app/routers/agent.py` | Update `analyze_stock` to call `stock_analyser` |
| `nivesh-client/frontend/src/pages/StockDetail.jsx` | Update `fetchInsights` mapping + `AgentInsightsTab` component |

---

## Scoring Logic

### Fundamental Score (0–95, rule-based)

Five metrics summed, then capped at 95:

| Metric | Max Pts | Thresholds |
|--------|---------|-----------|
| ROE | 25 | ≥20% → 25, 15–20% → 20, 8–15% → 12, 0–8% → 6, <0 → 0 |
| ROCE | 25 | ≥20% → 25, 12–20% → 18, 8–12% → 10, <8% → 3 |
| PAT Margin | 20 | ≥15% → 20, 8–15% → 14, 3–8% → 8, <3% → 3 |
| Debt/Equity | 15 | ≤0.3 → 15, 0.3–0.8 → 10, 0.8–1.5 → 5, >1.5 → 0 |
| Interest Coverage | 15 | ≥10x → 15, 5–10x → 10, 2–5x → 5, <2x → 0 |

**Signal mapping:**
- ≥70 → STRONG
- 50–70 → GOOD
- 30–50 → WEAK
- <30 → POOR

When a metric is `None` (not yet computed), it scores 0 for that component.

---

### Technical Signal (7-vote system)

Each indicator casts: +1 (bullish), −1 (bearish), 0 (neutral).

| Vote | Bullish (+1) | Bearish (−1) | Neutral (0) |
|------|-------------|-------------|------------|
| RSI-14 | ≥55 | ≤40 | 40–55 |
| MACD hist | >0 | ≤0 | — |
| Price vs SMA50 + SMA200 | Above both | Below both | Mixed |
| ADX-14 | ≥25 (strong trend) | — | <25 |
| Stochastic %K | ≥60 | ≤30 | 30–60 |
| 52W position (pct_from_52w_low) | >20% | pct_from_52w_high < −20% | else |
| RS vs Nifty 6M | >0 | <0 | =0 |

**Signal determination:**
- `bullish_votes ≥ bearish_votes + 2` → **BULLISH**
- `bearish_votes ≥ bullish_votes + 2` → **BEARISH**
- Otherwise → **NEUTRAL**

Missing indicators (None) cast 0 (neutral).

---

### Valuation Signal (4 absolute-threshold metrics)

| Metric | Cheap | Fair | Expensive |
|--------|-------|------|-----------|
| PE | <15 | 15–30 | >30 |
| PB | <1.5 | 1.5–4 | >4 |
| PS | <1 | 1–5 | >5 |
| EV/EBITDA | <8 | 8–20 | >20 |

Count cheap vs expensive across available metrics:
- `cheap_count ≥ 2` → **UNDERVALUED**
- `expensive_count ≥ 2` → **OVERVALUED**
- Otherwise → **FAIR**

Missing metrics are skipped (not counted as either).

---

### Aggregate Score (0–95)

**Signal-to-score conversion (all capped at 95, never 100):**

| Pillar | Signal → Score |
|--------|---------------|
| Fundamental | STRONG → 95, GOOD → 65, WEAK → 35, POOR → 10 |
| Technical | BULLISH → 95, NEUTRAL → 60, BEARISH → 20 |
| Valuation | UNDERVALUED → 95, FAIR → 60, OVERVALUED → 20 |

```
overall_health_score = min(95, F_score×0.40 + T_score×0.30 + V_score×0.30)
```

**Rating label from overall_health_score:**

| Score | Label |
|-------|-------|
| ≥80 | Strong Buy |
| ≥65 | Buy |
| ≥50 | Hold |
| ≥35 | Reduce |
| <35 | Sell |

---

### LLM Narrative

- Single `ChatGroq.ainvoke()` call — no tools, no agent graph
- System prompt: senior equity research analyst persona
- User prompt: all scores, signals, key metrics pre-loaded as context
- Temperature: 0.3
- Fallback: template string if LLM fails or times out

---

## API Response Schema

```json
{
  "symbol": "ABB",
  "company_name": "ABB India Limited",
  "sector": "Capital Goods",
  "latest_close": 6381.0,
  "overall_health_score": 58.5,
  "rating_label": "Hold",
  "fundamental_score": 82.0,
  "fundamental_signal": "STRONG",
  "fundamental_reasoning": "ROE 21.3% (25pts), ROCE 24.0% (25pts), PAT margin 12.6% (14pts), D/E 0.01 (15pts), Interest coverage 94.9x (15pts). Raw: 94 → capped 95 → signal STRONG.",
  "technical_signal": "BEARISH",
  "technical_reasoning": "RSI 37.1 — bearish. MACD hist −144 — bearish. Price below SMA50 (6587) — bearish. ADX N/A — neutral. Stoch N/A — neutral. 52W pos — neutral. RS vs Nifty — neutral. Vote: 1B/3Br/3N.",
  "valuation_signal": "FAIR",
  "valuation_reasoning": "PE 81.0 — expensive. PB 3.4 — fair. PS 2.0 — fair. EV/EBITDA N/A — skipped. 0 cheap / 1 expensive → FAIR.",
  "full_narrative": "ABB India demonstrates exceptional fundamental quality...",
  "status": "COMPLETED",
  "logs": [
    "Fundamental: STRONG (82.0/95)",
    "Technical: BEARISH (1B/3Br/3N)",
    "Valuation: FAIR (0C/1E)",
    "Aggregate: F=95×0.4 + T=20×0.3 + V=60×0.3 = 62.0/95",
    "LLM narrative generated"
  ]
}
```

---

## UI: Updated `AgentInsightsTab`

Replaces the P&L / Balance Sheet / Cash Flow ScoreCards with three **Signal Cards**:

```
┌──────────────────────────────────────────────────────────┐
│  [Score Ring: overall_health_score]  [Rating Label]      │
│                                      [full_narrative]    │
│                                      [Re-run button]     │
└──────────────────────────────────────────────────────────┘

┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  FUNDAMENTAL  │  │   TECHNICAL   │  │   VALUATION   │
│  82.0 / 95    │  │   BEARISH     │  │     FAIR      │
│  [signal badge]│  │  1B/3Br/3N   │  │  0C/1E/3F    │
│  ROE: 21.3%  │  │  RSI: 37.1   │  │  PE: 81 (E)  │
│  ROCE: 24.0% │  │  MACD: neg   │  │  PB: 3.4 (F) │
│  PAT: 12.6%  │  │  vs SMA: ↓   │  │  PS: 2.0 (F) │
└───────────────┘  └───────────────┘  └───────────────┘

┌──────────────────────────────────────────────────────────┐
│ PIPELINE TRACE                                           │
│ [1] Fundamental: STRONG (82.0/95)                        │
│ [2] Technical: BEARISH (1B/3Br/3N)                       │
│ [3] Valuation: FAIR (0C/1E/3F)                          │
│ [4] Aggregate: 62.0/95 — Hold                            │
│ [5] LLM narrative generated                              │
└──────────────────────────────────────────────────────────┘
```

**Signal badge colours:**
- STRONG / BULLISH / UNDERVALUED → green
- GOOD / NEUTRAL / FAIR → amber
- WEAK / POOR / BEARISH / OVERVALUED → red

**`fetchInsights` mapping in StockDetail.jsx:**
`fetchInsights` passes the raw API response object directly as the `data` prop to `AgentInsightsTab`. The component will be rewritten (replacing the current P&L/BS/CF ScoreCard structure) to read directly from the API response shape defined above.

---

## Error Handling

| Failure | Behaviour |
|---------|-----------|
| Stock not found (proxy 404) | `HTTP 404` — UI shows toast error |
| GROQ_API_KEY missing | `HTTP 503` — UI shows config error |
| LLM timeout / error | Use fallback template narrative; rest of response intact |
| Missing ratio fields (None) | Scored as 0 for fundamental; neutral vote for technical; skipped for valuation |
| Server offline (proxy OfflineError) | `HTTP 503` — UI shows toast error |
