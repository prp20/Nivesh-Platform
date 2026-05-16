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
