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
