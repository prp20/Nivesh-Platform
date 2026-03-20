import pandas as pd
import numpy as np
from typing import List, Dict

def calculate_returns(nav_series: pd.Series) -> pd.Series:
    return nav_series.pct_change().dropna()

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.05) -> float:
    """Calculate annualized Sharpe Ratio."""
    if returns.empty: return 0.0
    excess_returns = returns - (risk_free_rate / 252)
    return np.sqrt(252) * excess_returns.mean() / returns.std()

def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.05) -> float:
    """Calculate annualized Sortino Ratio."""
    if returns.empty: return 0.0
    excess_returns = returns - (risk_free_rate / 252)
    downside_returns = excess_returns[excess_returns < 0]
    if downside_returns.empty: return 0.0
    return np.sqrt(252) * excess_returns.mean() / downside_returns.std()

def calculate_max_drawdown(nav_series: pd.Series) -> float:
    """Calculate maximum drawdown."""
    if nav_series.empty: return 0.0
    roll_max = nav_series.cummax()
    drawdown = (nav_series - roll_max) / roll_max
    return float(drawdown.min())

def compute_all_metrics(nav_history: List[Dict]) -> Dict:
    """Compute comprehensive metrics for a fund."""
    if not nav_history: return {}
    
    df = pd.DataFrame(nav_history)
    df['nav_date'] = pd.to_datetime(df['nav_date'])
    df = df.sort_values('nav_date')
    df.set_index('nav_date', inplace=True)
    
    nav_series = df['nav_value']
    returns = calculate_returns(nav_series)
    
    metrics = {
        "current_nav": float(nav_series.iloc[-1]),
        "nav_date": nav_series.index[-1].date(),
        "std_dev": float(returns.std() * np.sqrt(252)),
        "sharpe": calculate_sharpe_ratio(returns),
        "sortino": calculate_sortino_ratio(returns),
        "max_drawdown": calculate_max_drawdown(nav_series)
    }
    return metrics
