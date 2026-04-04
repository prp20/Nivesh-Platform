import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

def calculate_returns(nav_series: pd.Series) -> pd.Series:
    return nav_series.pct_change().dropna()

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.065) -> float:
    """Calculate annualized Sharpe Ratio."""
    if returns.empty or returns.std() == 0: return 0.0
    excess_returns = returns - (risk_free_rate / 252)
    return np.sqrt(252) * excess_returns.mean() / returns.std()

def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.065) -> float:
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

def calculate_absolute_return(nav_series: pd.Series, years: Optional[int] = None, months: Optional[int] = None) -> Optional[float]:
    """Calculate simple absolute return for a given number of years or months."""
    if nav_series.empty: return None
    
    end_date = nav_series.index[-1]
    if years:
        start_date = end_date - pd.DateOffset(years=years)
        min_days = years * 365 * 0.9
    elif months:
        start_date = end_date - pd.DateOffset(months=months)
        min_days = months * 30 * 0.9
    else:
        return None
    
    # Find closest start date
    mask = nav_series.index >= start_date
    if not mask.any(): return None
    
    actual_start_date = nav_series.index[mask][0]
    start_nav = nav_series.loc[actual_start_date]
    end_nav = nav_series.iloc[-1]
    
    # Only calculate if we have enough data (at least 90% of the requested period)
    days_diff = (end_date - actual_start_date).days
    if days_diff < min_days:
        return None
        
    return float((end_nav / start_nav) - 1)

def calculate_capture_ratios(fund_returns: pd.Series, bench_returns: pd.Series) -> Dict[str, Optional[float]]:
    """Calculate upside and downside capture ratios."""
    if fund_returns.empty or bench_returns.empty:
        return {"upside_capture": None, "downside_capture": None}
    
    # Align returns
    combined = pd.concat([fund_returns, bench_returns], axis=1, join='inner')
    combined.columns = ['fund', 'bench']
    
    # Monthly returns for capture ratio (standard practice)
    # Correcting the apply logic for monthly returns
    monthly = combined.groupby(pd.Grouper(freq='ME')).apply(lambda x: (1 + x).prod() - 1, include_groups=False)
    
    up_bench = monthly[monthly['bench'] > 0]
    down_bench = monthly[monthly['bench'] < 0]
    
    upside_capture = None
    if not up_bench.empty and up_bench['bench'].mean() != 0:
        upside_capture = float(up_bench['fund'].mean() / up_bench['bench'].mean())
        
    downside_capture = None
    if not down_bench.empty and down_bench['bench'].mean() != 0:
        downside_capture = float(down_bench['fund'].mean() / down_bench['bench'].mean())
        
    return {
        "upside_capture": upside_capture,
        "downside_capture": downside_capture
    }

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
        "absolute_return_1y": calculate_absolute_return(nav_series, years=1),
        "absolute_return_3y": calculate_absolute_return(nav_series, years=3),
        "absolute_return_5y": calculate_absolute_return(nav_series, years=5),
        "absolute_return_10y": calculate_absolute_return(nav_series, years=10),
        "short_term_return_6m": calculate_absolute_return(nav_series, months=6),
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
            risk_free_rate = 0.065
            fund_ann_ret = (1 + fund_ret.mean())**252 - 1
            bench_ann_ret = (1 + bench_ret.mean())**252 - 1
            alpha = fund_ann_ret - (risk_free_rate + beta * (bench_ann_ret - risk_free_rate))
            
            # Tracking Error
            tracking_error = (fund_ret - bench_ret).std() * np.sqrt(252)
            
            # Information Ratio
            excess_ret = fund_ann_ret - bench_ann_ret
            info_ratio = excess_ret / tracking_error if tracking_error != 0 else 0
            
            # Capture Ratios
            capture = calculate_capture_ratios(fund_ret, bench_ret)
            
            metrics.update({
                "alpha": float(alpha),
                "beta": float(beta),
                "tracking_error": float(tracking_error),
                "information_ratio": float(info_ratio),
                "upside_capture": capture["upside_capture"],
                "downside_capture": capture["downside_capture"]
            })
            
    # Data completeness metadata
    start_date = nav_series.index[0].date()
    end_date = nav_series.index[-1].date()
    total_calendar_days = (nav_series.index[-1] - nav_series.index[0]).days
    expected_trading_days = total_calendar_days * 252 / 365
    actual_trading_days = len(nav_series)
    completeness = (
        min(actual_trading_days / expected_trading_days * 100, 100.0)
        if expected_trading_days > 0
        else 0.0
    )
    metrics.update({
        "calculation_period_start_date": start_date,
        "calculation_period_end_date": end_date,
        "data_completeness_percentage": round(completeness, 2),
        "has_sufficient_data": completeness >= 80.0,
    })

    # Final Verdict Logic
    sharpe_raw = metrics.get("sharpe")
    alpha_raw = metrics.get("alpha")
    
    sharpe = float(sharpe_raw) if sharpe_raw is not None else 0.0
    alpha = float(alpha_raw) if alpha_raw is not None else 0.0
    
    if sharpe > 1.2 and alpha > 0.05:
        metrics["final_verdict"] = "Elite Performance - This asset demonstrates exceptional risk-adjusted returns and significant alpha generation. Recommended for aggressive growth portfolios."
    elif sharpe > 0.8 and alpha > 0:
        metrics["final_verdict"] = "Stable Performer - The fund maintain steady risk-adjusted returns with positive alpha. Suitable as a reliable core holding for long-term investors."
    elif alpha < 0:
        metrics["final_verdict"] = "Underperforming Benchmark - Caution advised. The asset is currently failing to outpace its benchmark on a risk-adjusted basis. Monitor peer performance closely."
    else:
        metrics["final_verdict"] = "Standard Asset - Performance is largely in line with market expectations. Recommended for diversified exposure rather than localized outperformance."

    return metrics

async def get_comparison_data(session: AsyncSession, scheme_codes: List[str]) -> Dict:
    """
    Multi-fund comparison engine focusing on metrics.
    Fetches pre-calculated metrics for specified funds.
    """
    from . import crud, schemas
    
    funds_payload = []
    
    for code in scheme_codes:
        # Get metrics from DB
        metrics_db = await crud.get_fund_metrics(session, code)
        
        # If no metrics in DB, we could trigger a sync, but for comparison 
        # we'll return what we have to keep it fast.
        funds_payload.append({
            "scheme_code": code,
            "metrics": schemas.FundMetricsRead.model_validate(metrics_db).model_dump(mode="json") if metrics_db else {}
        })
        
    return {
        "funds": funds_payload,
        "metrics_comparison": {} # Placeholder for aggregate comparison metrics
    }
