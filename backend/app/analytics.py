import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import date

def calculate_returns(nav_series: pd.Series) -> pd.Series:
    return nav_series.pct_change().dropna()

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.05) -> float:
    """Calculate annualized Sharpe Ratio."""
    if returns.empty or returns.std() == 0: return 0.0
    excess_returns = returns - (risk_free_rate / 252)
    return np.sqrt(252) * excess_returns.mean() / returns.std()

def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.05) -> float:
    """Calculate annualized Sortino Ratio."""
    if returns.empty: return 0.0
    excess_returns = returns - (risk_free_rate / 252)
    downside_returns = excess_returns[excess_returns < 0]
    if downside_returns.empty or downside_returns.std() == 0: 
        # If no downside, return a high ratio if mean is positive
        return 10.0 if excess_returns.mean() > 0 else 0.0
    return np.sqrt(252) * excess_returns.mean() / downside_returns.std()

def calculate_max_drawdown(nav_series: pd.Series) -> float:
    """Calculate maximum drawdown."""
    if nav_series.empty: return 0.0
    roll_max = nav_series.cummax()
    drawdown = (nav_series - roll_max) / roll_max
    return float(drawdown.min())

def calculate_cagr(nav_series: pd.Series, years: int) -> Optional[float]:
    """Calculate CAGR for a given number of years."""
    if nav_series.empty: return None
    
    end_date = nav_series.index[-1]
    start_date = end_date - pd.DateOffset(years=years)
    
    # Find closest start date
    mask = nav_series.index >= start_date
    if not mask.any(): return None
    
    actual_start_date = nav_series.index[mask][0]
    start_nav = nav_series.loc[actual_start_date]
    end_nav = nav_series.iloc[-1]
    
    # Only calculate if we have enough data (at least 90% of the requested period)
    days_diff = (end_date - actual_start_date).days
    if days_diff < (years * 365 * 0.9):
        return None
        
    return float((end_nav / start_nav) ** (1 / years) - 1)

def compute_all_metrics(nav_history: List[Dict], benchmark_history: Optional[List[Dict]] = None) -> Dict:
    """Compute comprehensive metrics for a fund, including relative metrics if benchmark is provided."""
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
        "max_drawdown": calculate_max_drawdown(nav_series),
        "rolling_return_3year": calculate_cagr(nav_series, 3),
        "rolling_return_5year": calculate_cagr(nav_series, 5),
    }
    
    # Relative Metrics
    if benchmark_history:
        bench_df = pd.DataFrame(benchmark_history)
        bench_df['nav_date'] = pd.to_datetime(bench_df['nav_date'])
        bench_df = bench_df.sort_values('nav_date')
        bench_df.set_index('nav_date', inplace=True)
        
        # Align returns
        combined = pd.concat([nav_series, bench_df['index_value']], axis=1, join='inner')
        combined.columns = ['fund', 'bench']
        
        fund_ret = combined['fund'].pct_change().dropna()
        bench_ret = combined['bench'].pct_change().dropna()
        
        if not fund_ret.empty and not bench_ret.empty:
            # Beta
            covariance = np.cov(fund_ret, bench_ret)[0][1]
            variance = np.var(bench_ret)
            beta = covariance / variance if variance != 0 else 1.0
            
            # Alpha (Annualized)
            risk_free_rate = 0.05
            fund_ann_ret = (1 + fund_ret.mean())**252 - 1
            bench_ann_ret = (1 + bench_ret.mean())**252 - 1
            alpha = fund_ann_ret - (risk_free_rate + beta * (bench_ann_ret - risk_free_rate))
            
            # Tracking Error
            tracking_error = (fund_ret - bench_ret).std() * np.sqrt(252)
            
            # Information Ratio
            excess_ret = fund_ann_ret - bench_ann_ret
            info_ratio = excess_ret / tracking_error if tracking_error != 0 else 0
            
            metrics.update({
                "alpha": float(alpha),
                "beta": float(beta),
                "tracking_error": float(tracking_error),
                "information_ratio": float(info_ratio)
            })
            
    return metrics
