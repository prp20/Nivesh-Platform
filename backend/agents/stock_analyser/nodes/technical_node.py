"""ONE JOB: Produce BULLISH / NEUTRAL / BEARISH signal from TA indicators.

Votes across 5 rule-based checks — majority wins.
No LLM call, no DB call.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _f(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


async def technical_node(state: dict) -> dict:
    ti = state.get("technical_indicators", {})
    price = state.get("latest_price", {})
    close = _f(price.get("close"))

    votes = []  # +1 = bullish, -1 = bearish, 0 = neutral

    # 1. RSI (14) — classic momentum
    rsi = _f(ti.get("rsi_14"))
    if rsi is not None:
        if rsi >= 55:
            votes.append(1)
            rsi_note = f"RSI {rsi:.1f} — bullish momentum"
        elif rsi <= 40:
            votes.append(-1)
            rsi_note = f"RSI {rsi:.1f} — oversold/bearish"
        else:
            votes.append(0)
            rsi_note = f"RSI {rsi:.1f} — neutral zone"
    else:
        rsi_note = "RSI N/A"

    # 2. MACD — trend direction
    macd_line = _f(ti.get("macd_line"))
    macd_signal = _f(ti.get("macd_signal"))
    if macd_line is not None and macd_signal is not None:
        if macd_line > macd_signal:
            votes.append(1)
            macd_note = f"MACD above signal — bullish"
        else:
            votes.append(-1)
            macd_note = f"MACD below signal — bearish"
    else:
        macd_note = "MACD N/A"

    # 3. Price vs SMA-50 and SMA-200 (trend position)
    sma50 = _f(ti.get("sma_50"))
    sma200 = _f(ti.get("sma_200"))
    if close and sma50 and sma200:
        if close > sma50 and close > sma200:
            votes.append(1)
            ma_note = "Price above SMA-50 & SMA-200 — uptrend"
        elif close < sma50 and close < sma200:
            votes.append(-1)
            ma_note = "Price below SMA-50 & SMA-200 — downtrend"
        else:
            votes.append(0)
            ma_note = "Price mixed vs moving averages"
    else:
        ma_note = "Moving averages N/A"

    # 4. ADX — trend strength (> 25 = trending, <20 = ranging)
    adx = _f(ti.get("adx_14"))
    if adx is not None:
        if adx >= 25:
            votes.append(1)  # confirmed trend — reward bullish context
            adx_note = f"ADX {adx:.1f} — strong trend"
        else:
            votes.append(0)
            adx_note = f"ADX {adx:.1f} — weak/ranging market"
    else:
        adx_note = "ADX N/A"

    # 5. Stochastic %K — overbought/oversold
    stoch_k = _f(ti.get("stoch_k"))
    if stoch_k is not None:
        if stoch_k >= 60:
            votes.append(1)
            stoch_note = f"Stoch %K {stoch_k:.1f} — bullish"
        elif stoch_k <= 30:
            votes.append(-1)
            stoch_note = f"Stoch %K {stoch_k:.1f} — oversold"
        else:
            votes.append(0)
            stoch_note = f"Stoch %K {stoch_k:.1f} — neutral"
    else:
        stoch_note = "Stochastic N/A"

    bullish = votes.count(1)
    bearish = votes.count(-1)

    if bullish > bearish and bullish >= 2:
        signal = "BULLISH"
    elif bearish > bullish and bearish >= 2:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    reason = f"{rsi_note}. {macd_note}. {ma_note}. {adx_note}. {stoch_note}. Vote: {bullish}B/{bearish}Br/{votes.count(0)}N."

    return {
        "technical_signal": signal,
        "technical_reasoning": reason,
        "logs": state["logs"] + [f"Technical agent: {signal} ({bullish}B/{bearish}Br)"],
    }
