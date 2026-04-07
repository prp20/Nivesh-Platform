import pytest
import numpy as np
from app.analytics import rank_funds_for_comparison

def test_rank_funds_basic():
    """Test ranking with two funds having clear differences."""
    scheme_codes = ["FUND_A", "FUND_B"]
    funds_metrics = [
        {
            "cagr_3year": 15.0,
            "sharpe_ratio": 1.2,
            "expense_ratio": 0.5,
            "maximum_drawdown": -0.10,
        },
        {
            "cagr_3year": 10.0,
            "sharpe_ratio": 0.8,
            "expense_ratio": 1.0,
            "maximum_drawdown": -0.20,
        }
    ]
    
    result = rank_funds_for_comparison(funds_metrics, scheme_codes)
    
    assert len(result["rankings"]) == 2
    assert result["rankings"][0]["scheme_code"] == "FUND_A"
    assert result["rankings"][0]["rank"] == 1
    assert result["rankings"][0]["is_recommended"] is True
    assert result["rankings"][1]["scheme_code"] == "FUND_B"
    assert result["rankings"][1]["rank"] == 2
    assert "FUND_A leads" in result["comparison_summary"]

def test_rank_funds_with_missing_data():
    """Test ranking where one fund has no metrics."""
    scheme_codes = ["FUND_DATA", "FUND_EMPTY"]
    funds_metrics = [
        {"cagr_3year": 12.0, "sharpe_ratio": 1.0},
        {}  # Empty dict
    ]
    
    result = rank_funds_for_comparison(funds_metrics, scheme_codes)
    
    assert result["rankings"][0]["scheme_code"] == "FUND_DATA"
    assert result["rankings"][1]["scheme_code"] == "FUND_EMPTY"
    assert result["rankings"][1]["composite_score"] == 0.0

def test_rank_funds_ties():
    """Test ranking with identical metrics."""
    scheme_codes = ["FUND_1", "FUND_2"]
    metrics = {"cagr_3year": 12.0, "sharpe_ratio": 1.0}
    funds_metrics = [metrics, metrics]
    
    result = rank_funds_for_comparison(funds_metrics, scheme_codes)
    
    assert result["rankings"][0]["composite_score"] == result["rankings"][1]["composite_score"]
    # Scores should be around 50 due to tie logic in normalisation
    assert result["rankings"][0]["composite_score"] > 0

def test_rank_funds_polarity():
    """Test that lower-is-better (expense ratio) and less-negative-is-better (drawdown) work."""
    scheme_codes = ["LOW_EXPENSE", "HIGH_EXPENSE"]
    funds_metrics = [
        {"expense_ratio": 0.3, "maximum_drawdown": -0.05},
        {"expense_ratio": 1.5, "maximum_drawdown": -0.25}
    ]
    
    result = rank_funds_for_comparison(funds_metrics, scheme_codes)
    assert result["rankings"][0]["scheme_code"] == "LOW_EXPENSE"

def test_rank_funds_single_fund():
    """Test edge case with only one fund."""
    result = rank_funds_for_comparison([{}], ["ONLY_ONE"])
    assert result["rankings"] == []
    assert "Need at least 2" in result["comparison_summary"]

def test_rank_funds_mixed_none():
    """Test normalisation handles None values in some funds."""
    scheme_codes = ["F1", "F2", "F3"]
    funds_metrics = [
        {"cagr_3year": 20.0, "alpha": 0.05},
        {"cagr_3year": 10.0, "alpha": None},
        {"cagr_3year": None, "alpha": 0.02}
    ]
    
    result = rank_funds_for_comparison(funds_metrics, scheme_codes)
    assert len(result["rankings"]) == 3
    # F1 should win as it has best values and data
    assert result["rankings"][0]["scheme_code"] == "F1"

def test_rank_funds_extreme_values():
    """Test ranking with extreme outliers."""
    scheme_codes = ["NORMAL", "OUTLIER"]
    funds_metrics = [
        {"cagr_3year": 12.0},
        {"cagr_3year": 500.0}  # Extreme outlier
    ]
    
    result = rank_funds_for_comparison(funds_metrics, scheme_codes)
    assert result["rankings"][0]["scheme_code"] == "OUTLIER"
    assert result["rankings"][0]["composite_score"] > 30 # Weight is 0.35 * 100

def test_recommendation_reason():
    """Verify recommendation reason text is generated correctly."""
    scheme_codes = ["WINNER", "LOSER"]
    funds_metrics = [
        {"cagr_3year": 25.0, "sharpe_ratio": 2.1, "expense_ratio": 0.002},
        {"cagr_3year": 5.0, "sharpe_ratio": 0.5, "expense_ratio": 0.015}
    ]
    
    result = rank_funds_for_comparison(funds_metrics, scheme_codes)
    reason = result["rankings"][0]["recommendation_reason"]
    
    assert "Highest composite score" in reason
    assert "Sharpe 2.1" in reason
    assert "Expense Ratio 0.20%" in reason
