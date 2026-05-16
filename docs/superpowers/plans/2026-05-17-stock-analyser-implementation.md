# Stock Analyser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the plain LLM `analyze_stock` endpoint with a 3-pillar scoring pipeline (Fundamental + Technical + Valuation) and rewrite `AgentInsightsTab` to display the structured results.

**Architecture:** A new `stock_analyser.py` module holds all pure scoring functions; the existing `analyze_stock` endpoint in `agent.py` fetches stock data, calls the module, and returns a structured JSON response; `StockDetail.jsx` passes the raw response to a rewritten `AgentInsightsTab` component.

**Tech Stack:** Python (FastAPI, langchain-groq), React (JSX, Tailwind CSS), SQLAlchemy (server-side SQL edit only)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `nivesh-server/app/routers/stocks.py` | Modify (line 205) | Add `ti.adx_14, ti.stoch_k` to `GET /stocks/{symbol}` SELECT |
| `nivesh-client/app/agent/stock_analyser.py` | **Create** | All scoring logic: `score_fundamental`, `score_technical`, `score_valuation`, `aggregate`, `generate_narrative`, `run_full_analysis` |
| `nivesh-client/tests/test_stock_analyser.py` | **Create** | Unit tests for the three pure scoring functions |
| `nivesh-client/app/routers/agent.py` | Modify | Strip the inline LLM call from `analyze_stock`, delegate to `run_full_analysis` |
| `nivesh-client/frontend/src/pages/StockDetail.jsx` | Modify | Update `fetchInsights` mapping + rewrite `AgentInsightsTab` + `SignalCard` component |

---

## Task 1: Expose adx_14 and stoch_k in the server stock detail endpoint

**Files:**
- Modify: `nivesh-server/app/routers/stocks.py:205`

- [ ] **Step 1: Add the two fields to the SELECT clause**

In `nivesh-server/app/routers/stocks.py`, find line 205 (the last line of the technical indicators SELECT block) and extend it:

```python
# Before (line 205):
            ti.pct_from_52w_high, ti.pct_from_52w_low

# After:
            ti.pct_from_52w_high, ti.pct_from_52w_low,
            ti.adx_14, ti.stoch_k
```

- [ ] **Step 2: Verify the fields exist in the model**

```bash
grep -n "adx_14\|stoch_k" nivesh-server/app/models.py
```

Expected output:
```
323:    adx_14        = Column(Numeric(8, 4))
324:    stoch_k       = Column(Numeric(8, 4))
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-server/app/routers/stocks.py
git commit -m "feat(server): expose adx_14 + stoch_k in GET /stocks/{symbol}"
```

---

## Task 2: Create the stock_analyser module

**Files:**
- Create: `nivesh-client/app/agent/stock_analyser.py`

- [ ] **Step 1: Create the file with helpers and fundamental scoring**

Create `nivesh-client/app/agent/stock_analyser.py`:

```python
"""
app/agent/stock_analyser.py — 3-pillar stock scoring pipeline.

Public entry point:
    async run_full_analysis(stock_data, groq_api_key, model) -> dict

Pillars:
    Fundamental (0-95)  — rule-based: ROE, ROCE, PAT margin, D/E, interest coverage
    Technical  (signal) — 7-vote: RSI, MACD hist, SMA50/200, ADX, Stoch %K, 52W, RS vs Nifty
    Valuation  (signal) — absolute thresholds: PE, PB, PS, EV/EBITDA

Scores are capped at 95 — never 100. Financial predictions are uncertain.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_SCORE = 95.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _f(d: dict, key: str) -> Optional[float]:
    """Extract a float from a flat dict; return None if missing or non-numeric."""
    v = d.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(v: Optional[float]) -> str:
    return f"{v * 100:.2f}%" if v is not None else "N/A"


def _r(v: Optional[float], d: int = 2) -> str:
    return f"{round(float(v), d)}" if v is not None else "N/A"


# ── Fundamental scoring (0-95) ────────────────────────────────────────────────

def score_fundamental(stock_data: dict) -> dict:
    """
    Rule-based fundamental score from flat stock_data dict.

    Metrics and max points:
        ROE               25 pts
        ROCE              25 pts
        PAT Margin        20 pts
        Debt/Equity       15 pts
        Interest Coverage 15 pts
    Total max: 95 (capped — never 100)

    Returns dict with keys: fundamental_score, fundamental_signal,
    fundamental_reasoning, fundamental_metrics.
    """
    pts = 0
    notes = []

    # ROE (max 25)
    roe = _f(stock_data, "roe")
    if roe is not None:
        roe_pct = roe * 100
        if roe_pct >= 20:
            p = 25
        elif roe_pct >= 15:
            p = 20
        elif roe_pct >= 8:
            p = 12
        elif roe_pct >= 0:
            p = 6
        else:
            p = 0
        pts += p
        notes.append(f"ROE {roe_pct:.1f}% ({p}/25pts)")
    else:
        notes.append("ROE N/A (0/25pts)")

    # ROCE (max 25)
    roce = _f(stock_data, "roce")
    if roce is not None:
        roce_pct = roce * 100
        if roce_pct >= 20:
            p = 25
        elif roce_pct >= 12:
            p = 18
        elif roce_pct >= 8:
            p = 10
        else:
            p = 3
        pts += p
        notes.append(f"ROCE {roce_pct:.1f}% ({p}/25pts)")
    else:
        notes.append("ROCE N/A (0/25pts)")

    # PAT Margin (max 20)
    pat = _f(stock_data, "pat_margin")
    if pat is not None:
        pat_pct = pat * 100
        if pat_pct >= 15:
            p = 20
        elif pat_pct >= 8:
            p = 14
        elif pat_pct >= 3:
            p = 8
        else:
            p = 3
        pts += p
        notes.append(f"PAT margin {pat_pct:.1f}% ({p}/20pts)")
    else:
        notes.append("PAT margin N/A (0/20pts)")

    # Debt/Equity (max 15)
    de = _f(stock_data, "debt_equity")
    if de is not None:
        if de <= 0.3:
            p = 15
        elif de <= 0.8:
            p = 10
        elif de <= 1.5:
            p = 5
        else:
            p = 0
        pts += p
        notes.append(f"D/E {de:.2f} ({p}/15pts)")
    else:
        notes.append("D/E N/A (0/15pts)")

    # Interest Coverage (max 15)
    icov = _f(stock_data, "interest_cov")
    if icov is not None:
        if icov >= 10:
            p = 15
        elif icov >= 5:
            p = 10
        elif icov >= 2:
            p = 5
        else:
            p = 0
        pts += p
        notes.append(f"Int. coverage {icov:.1f}x ({p}/15pts)")
    else:
        notes.append("Int. coverage N/A (0/15pts)")

    score = min(_MAX_SCORE, float(pts))

    if score >= 70:
        signal = "STRONG"
    elif score >= 50:
        signal = "GOOD"
    elif score >= 30:
        signal = "WEAK"
    else:
        signal = "POOR"

    return {
        "fundamental_score": round(score, 1),
        "fundamental_signal": signal,
        "fundamental_reasoning": ". ".join(notes),
        "fundamental_metrics": {
            "roe": _pct(roe),
            "roce": _pct(roce),
            "pat_margin": _pct(pat),
            "debt_equity": _r(de),
            "interest_cov": _r(icov),
        },
    }


# ── Technical scoring (7-vote) ────────────────────────────────────────────────

def score_technical(stock_data: dict) -> dict:
    """
    7-vote technical signal system. Each indicator: +1 bullish, -1 bearish, 0 neutral.

    Votes:
        1. RSI-14            >= 55 bullish | <= 40 bearish
        2. MACD histogram    > 0 bullish   | <= 0 bearish
        3. Price vs SMA50+200 above both bullish | below both bearish
        4. ADX-14            >= 25 bullish (strong trend)
        5. Stochastic %K     >= 60 bullish | <= 30 bearish
        6. 52W position      > 20% from low bullish | < -20% from high bearish
        7. RS vs Nifty 6M    > 0 bullish   | < 0 bearish

    Signal: bullish >= bearish + 2 -> BULLISH
            bearish >= bullish + 2 -> BEARISH
            else -> NEUTRAL

    Returns dict with keys: technical_signal, technical_reasoning,
    technical_votes, technical_metrics.
    """
    bullish = 0
    bearish = 0
    neutral = 0
    notes = []

    # 1. RSI-14
    rsi = _f(stock_data, "rsi_14")
    if rsi is not None:
        if rsi >= 55:
            bullish += 1
            notes.append(f"RSI {rsi:.1f} — bullish")
        elif rsi <= 40:
            bearish += 1
            notes.append(f"RSI {rsi:.1f} — bearish")
        else:
            neutral += 1
            notes.append(f"RSI {rsi:.1f} — neutral")
    else:
        neutral += 1
        notes.append("RSI N/A — neutral")

    # 2. MACD histogram
    macd_hist = _f(stock_data, "macd_hist")
    if macd_hist is not None:
        if macd_hist > 0:
            bullish += 1
            notes.append(f"MACD hist {macd_hist:.2f} — bullish")
        else:
            bearish += 1
            notes.append(f"MACD hist {macd_hist:.2f} — bearish")
    else:
        neutral += 1
        notes.append("MACD N/A — neutral")

    # 3. Price vs SMA50 + SMA200
    close = _f(stock_data, "latest_close")
    sma50 = _f(stock_data, "sma_50")
    sma200 = _f(stock_data, "sma_200")
    if close is not None and sma50 is not None and sma200 is not None:
        if close > sma50 and close > sma200:
            bullish += 1
            notes.append("Price above SMA50 & SMA200 — uptrend")
        elif close < sma50 and close < sma200:
            bearish += 1
            notes.append("Price below SMA50 & SMA200 — downtrend")
        else:
            neutral += 1
            notes.append("Price mixed vs SMAs — neutral")
    else:
        neutral += 1
        notes.append("SMA data N/A — neutral")

    # 4. ADX-14
    adx = _f(stock_data, "adx_14")
    if adx is not None:
        if adx >= 25:
            bullish += 1
            notes.append(f"ADX {adx:.1f} — strong trend")
        else:
            neutral += 1
            notes.append(f"ADX {adx:.1f} — weak trend, neutral")
    else:
        neutral += 1
        notes.append("ADX N/A — neutral")

    # 5. Stochastic %K
    stoch_k = _f(stock_data, "stoch_k")
    if stoch_k is not None:
        if stoch_k >= 60:
            bullish += 1
            notes.append(f"Stoch %K {stoch_k:.1f} — bullish")
        elif stoch_k <= 30:
            bearish += 1
            notes.append(f"Stoch %K {stoch_k:.1f} — oversold/bearish")
        else:
            neutral += 1
            notes.append(f"Stoch %K {stoch_k:.1f} — neutral")
    else:
        neutral += 1
        notes.append("Stoch N/A — neutral")

    # 6. 52-week position
    pct_low = _f(stock_data, "pct_from_52w_low")
    pct_high = _f(stock_data, "pct_from_52w_high")
    if pct_low is not None and pct_high is not None:
        if pct_low > 20:
            bullish += 1
            notes.append(f"{pct_low:.1f}% above 52W low — bullish")
        elif pct_high < -20:
            bearish += 1
            notes.append(f"{pct_high:.1f}% from 52W high — bearish")
        else:
            neutral += 1
            notes.append("52W position — neutral")
    else:
        neutral += 1
        notes.append("52W data N/A — neutral")

    # 7. RS vs Nifty 6M
    rs = _f(stock_data, "rs_6m_vs_nifty")
    if rs is not None:
        if rs > 0:
            bullish += 1
            notes.append(f"RS vs Nifty {rs:.2f} — outperforming")
        elif rs < 0:
            bearish += 1
            notes.append(f"RS vs Nifty {rs:.2f} — underperforming")
        else:
            neutral += 1
            notes.append("RS vs Nifty 0 — neutral")
    else:
        neutral += 1
        notes.append("RS vs Nifty N/A — neutral")

    vote_str = f"{bullish}B/{bearish}Br/{neutral}N"

    if bullish >= bearish + 2:
        signal = "BULLISH"
    elif bearish >= bullish + 2:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    sma_arrow = "N/A"
    if close is not None and sma50 is not None:
        sma_arrow = "↑" if close > sma50 else "↓"

    return {
        "technical_signal": signal,
        "technical_reasoning": ". ".join(notes) + f". Vote: {vote_str}",
        "technical_votes": {
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "summary": vote_str,
        },
        "technical_metrics": {
            "rsi_14": _r(rsi),
            "macd_hist": _r(macd_hist),
            "vs_sma": sma_arrow,
            "adx_14": _r(adx),
            "stoch_k": _r(stoch_k),
        },
    }


# ── Valuation scoring (signal) ────────────────────────────────────────────────

def score_valuation(stock_data: dict) -> dict:
    """
    Absolute-threshold valuation signal across PE, PB, PS, EV/EBITDA.
    Thresholds: PE <15 cheap / >30 expensive; PB <1.5/<4; PS <1/>5; EV/EBITDA <8/>20.
    cheap >= 2 -> UNDERVALUED; expensive >= 2 -> OVERVALUED; else FAIR.

    Returns dict with keys: valuation_signal, valuation_reasoning,
    valuation_counts, valuation_metrics.
    """
    cheap = 0
    expensive = 0
    fair = 0
    notes = []
    metrics = {}

    checks = [
        ("pe_ratio",  "PE",        15,  30),
        ("pb_ratio",  "PB",        1.5,  4),
        ("ps_ratio",  "PS",         1,   5),
        ("ev_ebitda", "EV/EBITDA",  8,  20),
    ]

    for field, label, cheap_thresh, exp_thresh in checks:
        v = _f(stock_data, field)
        if v is None:
            notes.append(f"{label} N/A — skipped")
            metrics[field] = "N/A"
            continue
        if v < cheap_thresh:
            cheap += 1
            verdict = "C"
            notes.append(f"{label} {v:.1f} — cheap (<{cheap_thresh})")
        elif v > exp_thresh:
            expensive += 1
            verdict = "E"
            notes.append(f"{label} {v:.1f} — expensive (>{exp_thresh})")
        else:
            fair += 1
            verdict = "F"
            notes.append(f"{label} {v:.1f} — fair")
        metrics[field] = f"{v:.1f} ({verdict})"

    val_str = f"{cheap}C/{expensive}E/{fair}F"

    if cheap >= 2:
        signal = "UNDERVALUED"
    elif expensive >= 2:
        signal = "OVERVALUED"
    else:
        signal = "FAIR"

    return {
        "valuation_signal": signal,
        "valuation_reasoning": ". ".join(notes) + f". {val_str} → {signal}",
        "valuation_counts": {
            "cheap": cheap,
            "expensive": expensive,
            "fair": fair,
            "summary": val_str,
        },
        "valuation_metrics": metrics,
    }


# ── Aggregate ─────────────────────────────────────────────────────────────────

_F_MAP = {"STRONG": 95, "GOOD": 65, "WEAK": 35, "POOR": 10}
_T_MAP = {"BULLISH": 95, "NEUTRAL": 60, "BEARISH": 20}
_V_MAP = {"UNDERVALUED": 95, "FAIR": 60, "OVERVALUED": 20}

_LABELS = [(80, "Strong Buy"), (65, "Buy"), (50, "Hold"), (35, "Reduce"), (0, "Sell")]


def aggregate(f_result: dict, t_result: dict, v_result: dict) -> dict:
    """
    Weighted composite: Fundamental 40% + Technical 30% + Valuation 30%.
    Result capped at 95 — never 100.

    Returns dict with keys: overall_health_score, rating_label, aggregate_log.
    """
    f_s = _F_MAP[f_result["fundamental_signal"]]
    t_s = _T_MAP[t_result["technical_signal"]]
    v_s = _V_MAP[v_result["valuation_signal"]]

    overall = min(_MAX_SCORE, round(f_s * 0.40 + t_s * 0.30 + v_s * 0.30, 1))

    label = next(lbl for thresh, lbl in _LABELS if overall >= thresh)

    return {
        "overall_health_score": overall,
        "rating_label": label,
        "aggregate_log": f"Aggregate: F={f_s}×0.4 + T={t_s}×0.3 + V={v_s}×0.3 = {overall}/95 — {label}",
    }


# ── LLM narrative ─────────────────────────────────────────────────────────────

async def generate_narrative(
    stock_data: dict,
    f_result: dict,
    t_result: dict,
    v_result: dict,
    agg_result: dict,
    groq_api_key: str,
    model: str = "llama-3.3-70b-versatile",
) -> str:
    """
    Single ChatGroq inference — no tools, no agent graph.
    Returns plain-text narrative. Falls back to a template on any LLM error.
    """
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage, SystemMessage

    company = stock_data.get("company_name", stock_data.get("symbol", ""))
    sector = stock_data.get("sector", "N/A")
    close = stock_data.get("latest_close", "N/A")

    prompt = (
        f"Synthesize this stock analysis into a concise institutional-grade equity research narrative (5-7 sentences).\n\n"
        f"COMPANY: {company} ({stock_data.get('symbol')}) — {sector}\n"
        f"CURRENT PRICE: Rs. {close}\n\n"
        f"FUNDAMENTAL (weight 40%): {f_result['fundamental_signal']} — score {f_result['fundamental_score']}/95\n"
        f"{f_result['fundamental_reasoning']}\n\n"
        f"TECHNICAL (weight 30%): {t_result['technical_signal']}\n"
        f"{t_result['technical_reasoning']}\n\n"
        f"VALUATION (weight 30%): {v_result['valuation_signal']}\n"
        f"{v_result['valuation_reasoning']}\n\n"
        f"OVERALL SCORE: {agg_result['overall_health_score']}/95 — {agg_result['rating_label']}\n\n"
        "Write a flowing paragraph covering: fundamental quality, technical posture, valuation, key risks, and investment recommendation. "
        "Be specific. No markdown formatting."
    )

    try:
        llm = ChatGroq(api_key=groq_api_key, model=model, temperature=0.3, max_tokens=512)
        response = await llm.ainvoke([
            SystemMessage(content=(
                "You are a senior equity research analyst at Nivesh, an Indian equity research platform. "
                "Write concise, data-driven narratives in plain paragraphs. No markdown."
            )),
            HumanMessage(content=prompt),
        ])
        return response.content.strip()
    except Exception as exc:
        logger.warning("LLM narrative failed for %s: %s", stock_data.get("symbol"), exc)
        return (
            f"{company} shows a composite health score of {agg_result['overall_health_score']:.1f}/95 "
            f"({agg_result['rating_label']}). "
            f"Fundamental signal: {f_result['fundamental_signal']} ({f_result['fundamental_score']}/95). "
            f"Technical momentum: {t_result['technical_signal']} ({t_result['technical_votes']['summary']}). "
            f"Valuation: {v_result['valuation_signal']}. "
            "AI narrative unavailable — metrics-based assessment applied."
        )


# ── Public entry point ────────────────────────────────────────────────────────

async def run_full_analysis(stock_data: dict, groq_api_key: str, model: str) -> dict:
    """
    Orchestrate all three pillars, aggregate, and generate LLM narrative.
    Input: flat stock_data dict from GET /proxy/stocks/{symbol}.
    Returns the full structured analysis response (matches API response schema in design spec).
    """
    logs = []

    f_result = score_fundamental(stock_data)
    logs.append(f"Fundamental: {f_result['fundamental_signal']} ({f_result['fundamental_score']}/95)")

    t_result = score_technical(stock_data)
    logs.append(f"Technical: {t_result['technical_signal']} ({t_result['technical_votes']['summary']})")

    v_result = score_valuation(stock_data)
    logs.append(f"Valuation: {v_result['valuation_signal']} ({v_result['valuation_counts']['summary']})")

    agg = aggregate(f_result, t_result, v_result)
    logs.append(agg["aggregate_log"])

    narrative = await generate_narrative(
        stock_data, f_result, t_result, v_result, agg, groq_api_key, model
    )
    logs.append("LLM narrative generated")

    return {
        "symbol": stock_data.get("symbol", ""),
        "company_name": stock_data.get("company_name", ""),
        "sector": stock_data.get("sector", ""),
        "latest_close": stock_data.get("latest_close"),
        "overall_health_score": agg["overall_health_score"],
        "rating_label": agg["rating_label"],
        "fundamental_score": f_result["fundamental_score"],
        "fundamental_signal": f_result["fundamental_signal"],
        "fundamental_reasoning": f_result["fundamental_reasoning"],
        "fundamental_metrics": f_result["fundamental_metrics"],
        "technical_signal": t_result["technical_signal"],
        "technical_reasoning": t_result["technical_reasoning"],
        "technical_votes": t_result["technical_votes"],
        "technical_metrics": t_result["technical_metrics"],
        "valuation_signal": v_result["valuation_signal"],
        "valuation_reasoning": v_result["valuation_reasoning"],
        "valuation_counts": v_result["valuation_counts"],
        "valuation_metrics": v_result["valuation_metrics"],
        "full_narrative": narrative,
        "status": "COMPLETED",
        "logs": logs,
    }
```

- [ ] **Step 2: Verify the file parses cleanly**

```bash
cd nivesh-client
python3 -c "from app.agent.stock_analyser import score_fundamental, score_technical, score_valuation, aggregate; print('Import OK')"
```

Expected output: `Import OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/agent/stock_analyser.py
git commit -m "feat(client): add stock_analyser module — 3-pillar scoring pipeline"
```

---

## Task 3: Write and run unit tests for scoring functions

**Files:**
- Create: `nivesh-client/tests/__init__.py`
- Create: `nivesh-client/tests/test_stock_analyser.py`

- [ ] **Step 1: Create the test directory and file**

```bash
mkdir -p nivesh-client/tests
touch nivesh-client/tests/__init__.py
```

Create `nivesh-client/tests/test_stock_analyser.py`:

```python
"""
Unit tests for stock_analyser scoring functions.
Run from repo root: pytest nivesh-client/tests/test_stock_analyser.py -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agent.stock_analyser import (
    score_fundamental,
    score_technical,
    score_valuation,
    aggregate,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

STRONG_STOCK = {
    "roe": 0.25,           # 25pts — >= 20%
    "roce": 0.22,          # 25pts — >= 20%
    "pat_margin": 0.18,    # 20pts — >= 15%
    "debt_equity": 0.1,    # 15pts — <= 0.3
    "interest_cov": 15.0,  # 15pts — >= 10x
    # sum = 100 → capped to 95 → STRONG
}

WEAK_STOCK = {
    "roe": 0.05,           # 6pts
    "roce": 0.06,          # 3pts
    "pat_margin": 0.02,    # 3pts
    "debt_equity": 2.0,    # 0pts
    "interest_cov": 1.5,   # 0pts
    # sum = 12 → POOR
}

BULLISH_TA = {
    "rsi_14": 60.0,             # +1 bullish
    "macd_hist": 5.0,           # +1 bullish
    "latest_close": 100.0,
    "sma_50": 90.0,             # close > sma50
    "sma_200": 80.0,            # close > sma200 → +1 bullish
    "adx_14": 30.0,             # +1 bullish (>= 25)
    "stoch_k": 65.0,            # +1 bullish
    "pct_from_52w_low": 30.0,   # +1 bullish (> 20%)
    "pct_from_52w_high": -5.0,
    "rs_6m_vs_nifty": 0.5,      # +1 bullish
    # 7B/0Br/0N → BULLISH
}

BEARISH_TA = {
    "rsi_14": 35.0,             # -1 bearish
    "macd_hist": -10.0,         # -1 bearish
    "latest_close": 70.0,
    "sma_50": 90.0,             # close < sma50
    "sma_200": 85.0,            # close < sma200 → -1 bearish
    "adx_14": 10.0,             # 0 neutral
    "stoch_k": 20.0,            # -1 bearish
    "pct_from_52w_low": 5.0,
    "pct_from_52w_high": -30.0, # -1 bearish
    "rs_6m_vs_nifty": -0.5,     # -1 bearish
    # 0B/6Br/1N → BEARISH
}

CHEAP_VALUATION = {
    "pe_ratio": 10.0,    # < 15 cheap
    "pb_ratio": 1.0,     # < 1.5 cheap
    "ps_ratio": 0.5,     # < 1 cheap
    "ev_ebitda": 6.0,    # < 8 cheap
    # 4C/0E → UNDERVALUED
}

EXPENSIVE_VALUATION = {
    "pe_ratio": 50.0,    # > 30 expensive
    "pb_ratio": 6.0,     # > 4 expensive
    "ps_ratio": 8.0,     # > 5 expensive
    "ev_ebitda": 25.0,   # > 20 expensive
    # 0C/4E → OVERVALUED
}


# ── Fundamental tests ─────────────────────────────────────────────────────────

def test_fundamental_strong_stock_capped_at_95():
    result = score_fundamental(STRONG_STOCK)
    assert result["fundamental_score"] == 95.0, "Raw 100 must be capped to 95"
    assert result["fundamental_signal"] == "STRONG"

def test_fundamental_poor_stock():
    result = score_fundamental(WEAK_STOCK)
    assert result["fundamental_score"] == 12.0
    assert result["fundamental_signal"] == "POOR"

def test_fundamental_missing_fields_score_zero():
    result = score_fundamental({})
    assert result["fundamental_score"] == 0.0
    assert result["fundamental_signal"] == "POOR"
    assert "N/A" in result["fundamental_reasoning"]

def test_fundamental_good_band():
    stock = {
        "roe": 0.12,         # 12pts
        "roce": 0.15,        # 18pts
        "pat_margin": 0.10,  # 14pts
        "debt_equity": 0.5,  # 10pts
        "interest_cov": 6.0, # 10pts
        # sum = 64 → GOOD
    }
    result = score_fundamental(stock)
    assert result["fundamental_score"] == 64.0
    assert result["fundamental_signal"] == "GOOD"

def test_fundamental_score_never_exceeds_95():
    result = score_fundamental(STRONG_STOCK)
    assert result["fundamental_score"] <= 95.0


# ── Technical tests ───────────────────────────────────────────────────────────

def test_technical_bullish_all_votes():
    result = score_technical(BULLISH_TA)
    assert result["technical_signal"] == "BULLISH"
    assert result["technical_votes"]["bullish"] == 7
    assert result["technical_votes"]["bearish"] == 0

def test_technical_bearish():
    result = score_technical(BEARISH_TA)
    assert result["technical_signal"] == "BEARISH"
    assert result["technical_votes"]["bearish"] >= 5

def test_technical_neutral_balanced():
    # 2B / 2Br / 3N → NEUTRAL (neither side has >= 2 lead)
    stock = {
        "rsi_14": 50.0,          # neutral
        "macd_hist": 1.0,        # bullish
        "latest_close": 100.0,
        "sma_50": 95.0,          # close > sma50
        "sma_200": 105.0,        # close < sma200 → mixed → neutral
        "adx_14": 20.0,          # neutral
        "stoch_k": 50.0,         # neutral
        "pct_from_52w_low": 10.0,
        "pct_from_52w_high": -10.0,  # neutral
        "rs_6m_vs_nifty": -0.1,  # bearish
    }
    result = score_technical(stock)
    assert result["technical_signal"] == "NEUTRAL"

def test_technical_missing_all_fields():
    result = score_technical({})
    assert result["technical_signal"] == "NEUTRAL"  # all neutral → no side wins
    assert result["technical_votes"]["bullish"] == 0
    assert result["technical_votes"]["bearish"] == 0


# ── Valuation tests ───────────────────────────────────────────────────────────

def test_valuation_undervalued():
    result = score_valuation(CHEAP_VALUATION)
    assert result["valuation_signal"] == "UNDERVALUED"
    assert result["valuation_counts"]["cheap"] == 4

def test_valuation_overvalued():
    result = score_valuation(EXPENSIVE_VALUATION)
    assert result["valuation_signal"] == "OVERVALUED"
    assert result["valuation_counts"]["expensive"] == 4

def test_valuation_fair_mixed():
    stock = {"pe_ratio": 20.0, "pb_ratio": 2.5, "ps_ratio": 3.0, "ev_ebitda": 12.0}
    result = score_valuation(stock)
    assert result["valuation_signal"] == "FAIR"

def test_valuation_missing_fields_skipped():
    # Only PE available and it's expensive — not enough for OVERVALUED (needs >=2)
    result = score_valuation({"pe_ratio": 50.0})
    assert result["valuation_signal"] == "FAIR"
    assert result["valuation_counts"]["expensive"] == 1

def test_valuation_empty_is_fair():
    result = score_valuation({})
    assert result["valuation_signal"] == "FAIR"


# ── Aggregate tests ───────────────────────────────────────────────────────────

def test_aggregate_strong_buy():
    f = {"fundamental_signal": "STRONG"}
    t = {"technical_signal": "BULLISH"}
    v = {"valuation_signal": "UNDERVALUED"}
    result = aggregate(f, t, v)
    # 95*0.4 + 95*0.3 + 95*0.3 = 95 → capped 95
    assert result["overall_health_score"] == 95.0
    assert result["rating_label"] == "Strong Buy"

def test_aggregate_sell():
    f = {"fundamental_signal": "POOR"}
    t = {"technical_signal": "BEARISH"}
    v = {"valuation_signal": "OVERVALUED"}
    result = aggregate(f, t, v)
    # 10*0.4 + 20*0.3 + 20*0.3 = 4+6+6 = 16
    assert result["overall_health_score"] == 16.0
    assert result["rating_label"] == "Sell"

def test_aggregate_score_never_exceeds_95():
    f = {"fundamental_signal": "STRONG"}
    t = {"technical_signal": "BULLISH"}
    v = {"valuation_signal": "UNDERVALUED"}
    result = aggregate(f, t, v)
    assert result["overall_health_score"] <= 95.0

def test_aggregate_hold_band():
    f = {"fundamental_signal": "GOOD"}   # 65
    t = {"technical_signal": "NEUTRAL"}  # 60
    v = {"valuation_signal": "FAIR"}     # 60
    result = aggregate(f, t, v)
    # 65*0.4 + 60*0.3 + 60*0.3 = 26 + 18 + 18 = 62
    assert result["overall_health_score"] == 62.0
    assert result["rating_label"] == "Hold"
```

- [ ] **Step 2: Run the tests**

```bash
cd /home/prasad/dev_home/projects/stock_platform
pytest nivesh-client/tests/test_stock_analyser.py -v
```

Expected output: all tests PASSED. If any fail, fix `stock_analyser.py` before proceeding.

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/tests/
git commit -m "test(client): unit tests for stock_analyser scoring functions"
```

---

## Task 4: Update the analyze_stock endpoint

**Files:**
- Modify: `nivesh-client/app/routers/agent.py` — replace the `analyze_stock` function body

- [ ] **Step 1: Replace the analyze_stock function body**

In `nivesh-client/app/routers/agent.py`, find `@router.post("/analyze/{symbol}")` and replace the entire function body. Keep the function signature and docstring, replace everything from the httpx fetch onward:

```python
@router.post("/analyze/{symbol}")
async def analyze_stock(symbol: str):
    """
    Run the 3-pillar stock scoring pipeline and return a structured analysis.

    Fetches stock data from the local proxy (cached, auth-injected), then runs
    fundamental + technical + valuation scoring and generates an LLM narrative.
    No tool calling — single deterministic pipeline.
    """
    if not settings.GROQ_API_KEY:
        raise HTTPException(503, "GROQ_API_KEY not configured — add it to ~/.nivesh/.env")

    sym = symbol.upper().strip()

    # Fetch stock data from local proxy (handles JWT + caching)
    async with httpx.AsyncClient(base_url="http://localhost:8001", timeout=30.0) as client:
        resp = await client.get(f"/api/v1/proxy/stocks/{sym}")

    if resp.status_code == 404:
        raise HTTPException(404, f"Stock '{sym}' not found")
    if resp.status_code != 200:
        raise HTTPException(502, f"Proxy returned HTTP {resp.status_code}")

    stock_data = resp.json()

    from ..agent.stock_analyser import run_full_analysis
    return await run_full_analysis(stock_data, settings.GROQ_API_KEY, settings.AGENT_MODEL)
```

- [ ] **Step 2: Verify syntax**

```bash
cd nivesh-client
python3 -c "from app.routers.agent import router; print('Import OK')"
```

Expected: `Import OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/routers/agent.py
git commit -m "feat(client): wire analyze_stock endpoint to stock_analyser pipeline"
```

---

## Task 5: Update fetchInsights and rewrite AgentInsightsTab in StockDetail.jsx

**Files:**
- Modify: `nivesh-client/frontend/src/pages/StockDetail.jsx`

### 5a — Update fetchInsights

- [ ] **Step 1: Replace fetchInsights in StockDetail.jsx**

Find the `fetchInsights` function (starts at `const fetchInsights = async () => {`) and replace it entirely:

```javascript
const fetchInsights = async () => {
  if (!symbol) return;
  setLoadingInsights(true);
  try {
    const response = await apiClient.post(`/agent/analyze/${symbol.toUpperCase()}`);
    setAgentInsights(response.data);  // pass raw API response directly
  } catch (err) {
    console.error("Failed to fetch agent insights:", err);
    toast.error("Analysis failed. Check server logs or GROQ_API_KEY.");
  } finally {
    setLoadingInsights(false);
  }
};
```

Also remove the `import stockService` usage inside `fetchInsights` — `getAgentInsights` in `stockService.js` is no longer called from here; the component calls `apiClient` directly for this one endpoint.

> **Note:** `stockService.getAgentInsights` in `stockService.js` becomes dead code after this change. Leave it in place — it still calls `POST /agent/analyze/{symbol}` which is correct. The direct `apiClient` call above is equivalent.

### 5b — Rewrite AgentInsightsTab and add SignalCard

- [ ] **Step 2: Replace AgentInsightsTab and ScoreCard with the new components**

Find `function AgentInsightsTab(` and everything from there to the end of `function ScoreCard(` (inclusive) and replace with:

```javascript
function AgentInsightsTab({ data, loading, onRefresh }) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-20 space-y-8 animate-pulse">
        <div className="w-20 h-20 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
        <p className="font-label text-xs uppercase tracking-[0.4em] text-primary">Synthesizing Neural Lattice...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="glass-panel p-20 text-center rounded-[3rem] border border-white/5">
        <span className="material-symbols-outlined text-4xl text-slate-800 mb-4 block">smart_toy</span>
        <p className="text-[10px] uppercase font-black tracking-widest text-slate-600 mb-8">No Intelligence Recovered</p>
        <button
          onClick={onRefresh}
          className="px-8 py-3 bg-primary text-black rounded-xl font-black text-[10px] tracking-[0.2em] uppercase hover:shadow-lg hover:shadow-primary/20 transition-all font-headline"
        >
          Initialize Agent Analysis
        </button>
      </div>
    );
  }

  const score = data.overall_health_score ?? 0;
  const maxScore = 95;
  const circumference = 552.92;
  const offset = circumference - (circumference * score) / maxScore;

  return (
    <div className="space-y-12 animate-fadeIn pb-20">
      {/* Header: Score Ring + Narrative */}
      <div className="flex flex-col lg:flex-row gap-8">
        {/* Score ring */}
        <div className="lg:w-1/3 glass-panel p-10 rounded-[3rem] border border-white/5 flex flex-col items-center justify-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent pointer-events-none"></div>
          <p className="text-[10px] text-slate-500 font-black uppercase tracking-[0.4em] mb-6 relative z-10">Composite Health Score</p>
          <div className="relative w-48 h-48 flex items-center justify-center z-10">
            <svg className="w-full h-full transform -rotate-90">
              <circle cx="96" cy="96" r="88" stroke="currentColor" strokeWidth="2" fill="transparent" className="text-white/5" />
              <circle
                cx="96" cy="96" r="88" stroke="currentColor" strokeWidth="10" fill="transparent"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                className="text-primary drop-shadow-[0_0_10px_rgba(233,195,73,0.5)]"
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-5xl font-headline font-black text-white">{score.toFixed(1)}</span>
              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">out of {maxScore}</span>
            </div>
          </div>
          <div className="mt-8 px-6 py-2 bg-primary/10 border border-primary/20 rounded-full z-10">
            <span className="text-[10px] font-black text-primary uppercase tracking-widest">{data.rating_label ?? '—'}</span>
          </div>
        </div>

        {/* Narrative */}
        <div className="lg:flex-1 glass-panel p-10 rounded-[3rem] border border-white/5 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-10">
            <span className="material-symbols-outlined text-8xl text-primary">format_quote</span>
          </div>
          <h4 className="text-[10px] font-black uppercase tracking-[0.4em] text-slate-500 mb-6">Neural Synthesis</h4>
          <p className="text-base md:text-lg font-headline font-light leading-relaxed text-white/90 relative z-10">
            {data.full_narrative}
          </p>
          <div className="mt-10 flex justify-between items-center relative z-10">
            <span className="text-[9px] font-black text-slate-600 uppercase tracking-widest">Score v2.0 — Capped at 95</span>
            <button
              onClick={onRefresh}
              className="flex items-center gap-2 px-6 py-2 rounded-xl border border-white/5 hover:bg-white/5 transition-all group"
            >
              <span className="material-symbols-outlined text-sm group-hover:rotate-180 transition-transform duration-500 text-primary">sync</span>
              <span className="text-[9px] font-black text-slate-400 group-hover:text-white uppercase tracking-widest">Re-run Analysis</span>
            </button>
          </div>
        </div>
      </div>

      {/* Three Signal Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <SignalCard
          title="Fundamental"
          signal={data.fundamental_signal}
          score={data.fundamental_score}
          badge={`${data.fundamental_score ?? '—'}/95`}
          metrics={[
            { label: 'ROE',   value: data.fundamental_metrics?.roe ?? '—' },
            { label: 'ROCE',  value: data.fundamental_metrics?.roce ?? '—' },
            { label: 'PAT Margin', value: data.fundamental_metrics?.pat_margin ?? '—' },
          ]}
        />
        <SignalCard
          title="Technical"
          signal={data.technical_signal}
          badge={data.technical_votes?.summary ?? '—'}
          metrics={[
            { label: 'RSI-14',   value: data.technical_metrics?.rsi_14 ?? '—' },
            { label: 'MACD Hist', value: data.technical_metrics?.macd_hist ?? '—' },
            { label: 'vs SMA50',  value: data.technical_metrics?.vs_sma ?? '—' },
          ]}
        />
        <SignalCard
          title="Valuation"
          signal={data.valuation_signal}
          badge={data.valuation_counts?.summary ?? '—'}
          metrics={[
            { label: 'PE',        value: data.valuation_metrics?.pe_ratio ?? '—' },
            { label: 'PB',        value: data.valuation_metrics?.pb_ratio ?? '—' },
            { label: 'EV/EBITDA', value: data.valuation_metrics?.ev_ebitda ?? '—' },
          ]}
        />
      </div>

      {/* Pipeline Trace */}
      <div className="glass-panel rounded-[2rem] border border-white/5 overflow-hidden">
        <div className="px-8 py-4 bg-white/5 flex items-center justify-between">
          <h5 className="text-[9px] font-black uppercase tracking-[0.4em] text-slate-500">Pipeline Execution Trace</h5>
          <span className="text-[10px] font-bold text-secondary font-headline uppercase tracking-widest">{data.status}</span>
        </div>
        <div className="p-8 space-y-2 bg-black/20">
          {(data.logs ?? []).map((log, i) => (
            <div key={i} className="flex gap-4 font-mono text-[10px]">
              <span className="text-slate-700">[{i + 1}]</span>
              <span className="text-slate-400">{log}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Signal colours ─────────────────────────────────────────────────────────────
const SIGNAL_COLOURS = {
  STRONG:      { text: 'text-emerald-400', border: 'border-emerald-400/20', bg: 'bg-emerald-400/10' },
  BULLISH:     { text: 'text-emerald-400', border: 'border-emerald-400/20', bg: 'bg-emerald-400/10' },
  UNDERVALUED: { text: 'text-emerald-400', border: 'border-emerald-400/20', bg: 'bg-emerald-400/10' },
  GOOD:        { text: 'text-amber-400',   border: 'border-amber-400/20',   bg: 'bg-amber-400/10'   },
  NEUTRAL:     { text: 'text-amber-400',   border: 'border-amber-400/20',   bg: 'bg-amber-400/10'   },
  FAIR:        { text: 'text-amber-400',   border: 'border-amber-400/20',   bg: 'bg-amber-400/10'   },
  WEAK:        { text: 'text-red-400',     border: 'border-red-400/20',     bg: 'bg-red-400/10'     },
  POOR:        { text: 'text-red-400',     border: 'border-red-400/20',     bg: 'bg-red-400/10'     },
  BEARISH:     { text: 'text-red-400',     border: 'border-red-400/20',     bg: 'bg-red-400/10'     },
  OVERVALUED:  { text: 'text-red-400',     border: 'border-red-400/20',     bg: 'bg-red-400/10'     },
};

function SignalCard({ title, signal, badge, score, metrics }) {
  const colours = SIGNAL_COLOURS[signal] ?? { text: 'text-slate-400', border: 'border-white/5', bg: 'bg-white/5' };

  return (
    <div className={`glass-panel p-8 rounded-[2.5rem] border border-white/5 hover:${colours.border} transition-colors`}>
      <h5 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-4">{title}</h5>

      {/* Signal badge */}
      <div className={`inline-flex px-4 py-1.5 rounded-full ${colours.bg} border ${colours.border} mb-4`}>
        <span className={`text-[10px] font-black uppercase tracking-widest ${colours.text}`}>{signal ?? '—'}</span>
      </div>

      {/* Score (fundamental only) or vote summary */}
      <p className={`text-3xl font-headline font-black mb-6 ${colours.text}`}>
        {score != null ? `${score}` : badge}
      </p>

      {/* Key metrics */}
      <div className="space-y-3">
        {metrics.map((m, i) => (
          <div key={i} className="flex justify-between items-center py-1.5 border-b border-white/[0.03]">
            <span className="text-[10px] text-slate-600 font-bold uppercase tracking-widest">{m.label}</span>
            <span className="text-xs font-headline font-bold text-white/80">{m.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Remove the now-unused ScoreCard component call sites**

The old `<ScoreCard ... />` JSX blocks were already replaced in Step 2. Verify no remaining `ScoreCard` references exist:

```bash
grep -n "ScoreCard" nivesh-client/frontend/src/pages/StockDetail.jsx
```

Expected output: empty (no matches).

- [ ] **Step 4: Commit**

```bash
git add nivesh-client/frontend/src/pages/StockDetail.jsx
git commit -m "feat(client): rewrite AgentInsightsTab — 3-pillar signal cards + score ring"
```

---

## Task 6: End-to-end smoke test

- [ ] **Step 1: Restart the client server**

```bash
cd nivesh-client
uvicorn app.main:app --port 8001 --reload
```

- [ ] **Step 2: Test the endpoint directly**

```bash
curl -s -X POST http://localhost:8001/api/v1/agent/analyze/ABB | python3 -m json.tool | head -40
```

Expected: JSON with `overall_health_score`, `fundamental_score`, `technical_signal`, `valuation_signal`, `full_narrative`, `logs`.

- [ ] **Step 3: Open the browser and navigate to a stock detail page**

Go to `http://localhost:8001` → navigate to a stock (e.g. ABB) → click the "Agent Insights" tab → click "Initialize Agent Analysis".

Verify:
- Loading spinner appears
- After ~3-5 seconds: score ring shows numeric score (not 0.0)
- Rating label shows (Strong Buy / Buy / Hold / Reduce / Sell)
- Three signal cards render with coloured badges (green/amber/red)
- Narrative text populates
- Pipeline trace logs appear at the bottom

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: stock analyser pipeline — 3-pillar scoring, signal cards, LLM narrative"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Fundamental 0-95 rule-based scoring — Task 2 `score_fundamental`
- ✅ Technical 7-vote signal — Task 2 `score_technical`
- ✅ Valuation absolute thresholds — Task 2 `score_valuation`
- ✅ Weighted aggregate, cap at 95, rating label — Task 2 `aggregate`
- ✅ LLM narrative, fallback on error — Task 2 `generate_narrative`
- ✅ No DB persistence — no migration tasks
- ✅ `adx_14` + `stoch_k` added to server SQL — Task 1
- ✅ `fetchInsights` passes raw response — Task 5a
- ✅ `AgentInsightsTab` rewritten with 3 signal cards — Task 5b
- ✅ Signal colour coding green/amber/red — Task 5b `SIGNAL_COLOURS`
- ✅ Score ring uses `overall_health_score / 95` — Task 5b
- ✅ Unit tests cover all scoring functions — Task 3

**Type consistency check:**
- `score_fundamental` returns `fundamental_score`, `fundamental_signal`, `fundamental_reasoning`, `fundamental_metrics` — used identically in `run_full_analysis` (Task 2) and `AgentInsightsTab` (Task 5b) ✅
- `score_technical` returns `technical_signal`, `technical_votes.summary`, `technical_metrics.rsi_14/macd_hist/vs_sma` — all referenced by exact key in SignalCard ✅
- `score_valuation` returns `valuation_signal`, `valuation_counts.summary`, `valuation_metrics.pe_ratio/pb_ratio/ev_ebitda` — all referenced by exact key in SignalCard ✅
- `aggregate` returns `overall_health_score`, `rating_label`, `aggregate_log` — used in `run_full_analysis` logs and `AgentInsightsTab` score ring ✅
