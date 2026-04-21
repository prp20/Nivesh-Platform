import pytest
from fundamental_scorer.engine.statement_scorer import FinancialEngine

def test_score_pl_basic():
    # Mock P&L data for 4 years (to test 3Y CAGR)
    statements = [
        {"sales": 100, "operating_profit": 10, "net_profit": 5, "eps_in_rs": 1},
        {"sales": 120, "operating_profit": 15, "net_profit": 8, "eps_in_rs": 2},
        {"sales": 150, "operating_profit": 25, "net_profit": 12, "eps_in_rs": 3},
        {"sales": 200, "operating_profit": 40, "net_profit": 20, "eps_in_rs": 4},
    ]
    
    result = FinancialEngine.score_pl(statements)
    
    assert "score" in result
    assert result["score"] > 0
    assert "sub_scores" in result
    assert "metrics" in result
    
    # Revenue CAGR: (200/100)^(1/3) - 1 = 25.99% -> 100.0 score (>= 20%)
    # Pat CAGR: (20/5)^(1/3) - 1 = 58.74% -> 100.0 score (>= 25%)
    # Growth = (100 + 100) / 2 = 100.0
    assert result["sub_scores"]["growth"] == 100.0

def test_score_pl_insufficient_data():
    statements = [
        {"sales": 100, "operating_profit": 10, "net_profit": 5},
    ]
    result = FinancialEngine.score_pl(statements)
    assert result["score"] == 0
    assert "error" in result

def test_score_bs_basic():
    statements = [
        {"borrowings": 50, "equity_capital": 100, "reserves": 100, "cwip": 5, "fixed_assets": 100, "current_assets": 100, "current_liabilities": 50},
        {"borrowings": 40, "equity_capital": 100, "reserves": 150, "cwip": 2, "fixed_assets": 120, "current_assets": 150, "current_liabilities": 60},
    ]
    
    result = FinancialEngine.score_bs(statements)
    
    assert "score" in result
    assert result["score"] > 0
    # Debt/Equity = 40 / 250 = 0.16 (excellent < 0.2)
    assert result["sub_scores"]["leverage"] == 100.0

def test_score_cf_basic():
    statements = [
        {"cash_from_operating_activity": 10, "cash_from_investing_activity": -5, "net_profit": 8},
        {"cash_from_operating_activity": 20, "cash_from_investing_activity": -10, "net_profit": 18},
        {"cash_from_operating_activity": 30, "cash_from_investing_activity": -15, "net_profit": 28},
    ]
    
    result = FinancialEngine.score_cf(statements)
    
    assert "score" in result
    assert result["score"] > 0
    assert result["metrics"]["fcf_positive_years"] == 3
