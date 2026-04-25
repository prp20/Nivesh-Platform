"""
Financial analytics and metric calculations.

Computes risk/return metrics for funds, benchmarks, and portfolios.
All calculations use standard financial formulas and conventions.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import TYPE_CHECKING, List, Dict, Optional
from datetime import date

from .constants import ANNUAL_RISK_FREE_RATE, TRADING_DAYS_PER_YEAR, MIN_DATA_COMPLETENESS_PCT

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def calculate_returns(nav_series: pd.Series) -> pd.Series:
    """
    Calculate daily returns from NAV series.

    Args:
        nav_series: Time series of NAV values

    Returns:
        Series of daily returns (percentage change)
    """
    return nav_series.pct_change().dropna()


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = ANNUAL_RISK_FREE_RATE) -> float:
    """
    Calculate annualized Sharpe Ratio.

    Sharpe Ratio = (mean(excess_returns) / std(excess_returns)) * sqrt(252)
    where excess_returns = daily_returns - (risk_free_rate / 252)

    Args:
        returns: Series of daily returns
        risk_free_rate: Annual risk-free rate (default: 6.5% for India 10Y GSec)

    Returns:
        Annualized Sharpe Ratio, or 0.0 if insufficient data
    """
    if returns.empty or returns.std() == 0:
        return 0.0
    excess_returns = returns - (risk_free_rate / TRADING_DAYS_PER_YEAR)
    return float(np.sqrt(TRADING_DAYS_PER_YEAR) * excess_returns.mean() / returns.std())


def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = ANNUAL_RISK_FREE_RATE) -> float:
    """
    Calculate annualized Sortino Ratio.

    Sortino Ratio = (mean(excess_returns) / downside_deviation) * sqrt(252)
    where downside_deviation = sqrt(mean(min(excess_returns, 0)^2))

    Uses downside deviation (penalizes only negative returns) instead of
    standard deviation, making it more suitable for asymmetric return distributions.

    Args:
        returns: Series of daily returns
        risk_free_rate: Annual risk-free rate (default: 6.5%)

    Returns:
        Annualized Sortino Ratio, or 0.0 if insufficient data
    """
    if returns.empty:
        return 0.0
    excess_returns = returns - (risk_free_rate / TRADING_DAYS_PER_YEAR)
    downside_returns = np.minimum(excess_returns, 0)
    downside_deviation = np.sqrt(np.mean(downside_returns ** 2))
    if downside_deviation == 0:
        return 10.0 if excess_returns.mean() > 0 else 0.0
    return float(np.sqrt(TRADING_DAYS_PER_YEAR) * excess_returns.mean() / downside_deviation)

def calculate_max_drawdown(nav_series: pd.Series) -> float:
    """
    Calculate the maximum drawdown from peak.

    Maximum drawdown is the largest percentage decline from a historical peak
    to a subsequent trough.

    Args:
        nav_series: Time series of NAV values

    Returns:
        Maximum drawdown as a decimal (e.g., -0.25 for -25%), or 0.0 if empty
    """
    if nav_series.empty:
        return 0.0
    roll_max = nav_series.cummax()
    drawdown = (nav_series - roll_max) / roll_max
    return float(drawdown.min())


def calculate_cagr(nav_series: pd.Series, years: int) -> Optional[float]:
    """
    Calculate Compound Annual Growth Rate (CAGR) over N years.

    CAGR = (end_value / start_value) ^ (1 / years) - 1

    Returns None if insufficient data (less than 90% of requested period).

    Args:
        nav_series: Time series of NAV values
        years: Number of years to calculate CAGR for

    Returns:
        CAGR as decimal (e.g., 0.12 for 12%), or None if insufficient data
    """
    if nav_series.empty:
        return None

    end_date = nav_series.index[-1]
    start_date = end_date - pd.DateOffset(years=years)

    # Find closest start date in available data
    mask = nav_series.index >= start_date
    if not mask.any():
        return None

    actual_start_date = nav_series.index[mask][0]
    start_nav = nav_series.loc[actual_start_date]
    end_nav = nav_series.iloc[-1]

    # Only calculate if we have enough data (at least 90% of requested period)
    days_diff = (end_date - actual_start_date).days
    if days_diff < (years * 365 * MIN_DATA_COMPLETENESS_PCT):
        return None

    return float((end_nav / start_nav) ** (1 / years) - 1)


def calculate_absolute_return(
    nav_series: pd.Series, years: Optional[int] = None, months: Optional[int] = None
) -> Optional[float]:
    """
    Calculate simple absolute return over N years or months.

    Returns None if insufficient data (less than 90% of requested period).

    Args:
        nav_series: Time series of NAV values
        years: Number of years (mutually exclusive with months)
        months: Number of months (mutually exclusive with years)

    Returns:
        Absolute return as decimal (e.g., 0.50 for 50%), or None if insufficient data
    """
    if nav_series.empty:
        return None

    end_date = nav_series.index[-1]
    if years:
        start_date = end_date - pd.DateOffset(years=years)
        min_days = years * 365 * MIN_DATA_COMPLETENESS_PCT
    elif months:
        start_date = end_date - pd.DateOffset(months=months)
        min_days = months * 30 * MIN_DATA_COMPLETENESS_PCT
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
        "cagr_3year": calculate_cagr(nav_series, 3),
        "cagr_5year": calculate_cagr(nav_series, 5),
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
            risk_free_rate = ANNUAL_RISK_FREE_RATE

            fund_ann_ret = (1 + fund_ret.mean())**252 - 1
            bench_ann_ret = (1 + bench_ret.mean())**252 - 1
            alpha = fund_ann_ret - (risk_free_rate + beta * (bench_ann_ret - risk_free_rate))
            
            # Tracking Error
            active_returns = fund_ret - bench_ret
            tracking_error = active_returns.std() * np.sqrt(252)

            # Information Ratio — computed from daily active returns for consistency
            # IR = mean(active_daily) / std(active_daily) * sqrt(252)
            info_ratio = (
                float(active_returns.mean() / active_returns.std() * np.sqrt(252))
                if active_returns.std() != 0
                else 0.0
            )
            
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
    Multi-fund comparison engine that fetches both master data and computed metrics.
    Parallelizes I/O to minimize total execution time.
    """
    import asyncio
    from . import crud, schemas

    # Fetch all fund masters in batch (1 query instead of N)
    results = await crud.get_fund_masters_by_codes(session, scheme_codes)
    masters_map = {m.scheme_code: m for m in results}
    masters_results = [masters_map.get(code) for code in scheme_codes]

    funds_payload = []
    for code, master_db in zip(scheme_codes, masters_results):
        if not master_db:
            # Should not happen as router already checked existence, 
            # but we preserve list length and order for the ranking engine.
            funds_payload.append({
                "scheme_code": code,
                "fund_info": None,
                "metrics": None
            })
            continue
            
        # Serialize master details
        fund_info = schemas.FundMasterRead.model_validate(master_db).model_dump(mode="json")
        
        # Serialize metrics (if any)
        metrics = None
        if master_db.metrics:
            metrics = schemas.FundMetricsRead.model_validate(master_db.metrics).model_dump(mode="json")
            
        funds_payload.append({
            "scheme_code": master_db.scheme_code,
            "fund_info": fund_info,
            "metrics": metrics
        })

    return {"funds": funds_payload}


# ============================================================================
# COMPARISON RANKING ENGINE
# ============================================================================

# Metric definitions: (key, higher_is_better, group)
_METRIC_DEFS = {
    # Returns group
    "cagr_3year":           (True,  "returns"),
    "cagr_5year":           (True,  "returns"),
    "absolute_return_1y":   (True,  "returns"),
    "absolute_return_3y":   (True,  "returns"),
    "absolute_return_5y":   (True,  "returns"),
    "absolute_return_10y":  (True,  "returns"),
    "short_term_return_6m": (True,  "returns"),
    # Risk-Adjusted group
    "sharpe_ratio":         (True,  "risk_adjusted"),
    "sortino_ratio":        (True,  "risk_adjusted"),
    "information_ratio":    (True,  "risk_adjusted"),
    "alpha":                (True,  "risk_adjusted"),
    # Risk group (lower is better for all except upside_capture)
    "standard_deviation":   (False, "risk"),
    "maximum_drawdown":     (True,  "risk"),  # Less negative = better, so higher is better
    "beta":                 (False, "risk"),
    "downside_capture":     (False, "risk"),
    "volatility":           (False, "risk"),
    "tracking_error":       (False, "risk"),
    # Cost & Size group
    "expense_ratio":        (False, "cost_and_size"),
    "aum_in_crores":        (True,  "cost_and_size"),
    "fund_rating":          (True,  "cost_and_size"),
    # Consistency group
    "upside_capture":       (True,  "consistency"),
    "data_completeness_percentage": (True, "consistency"),
}

_GROUP_WEIGHTS = {
    "returns":       0.35,
    "risk_adjusted": 0.30,
    "risk":          0.20,
    "cost_and_size": 0.10,
    "consistency":   0.05,
}

# Human-readable labels for explanation text
_METRIC_LABELS = {
    "cagr_3year": "3Y CAGR", "cagr_5year": "5Y CAGR",
    "absolute_return_1y": "1Y Return", "absolute_return_3y": "3Y Return",
    "absolute_return_5y": "5Y Return", "absolute_return_10y": "10Y Return",
    "short_term_return_6m": "6M Return",
    "sharpe_ratio": "Sharpe Ratio", "sortino_ratio": "Sortino Ratio",
    "information_ratio": "Information Ratio", "alpha": "Alpha",
    "standard_deviation": "Std Deviation", "maximum_drawdown": "Max Drawdown",
    "beta": "Beta", "downside_capture": "Downside Capture",
    "volatility": "Volatility", "tracking_error": "Tracking Error",
    "expense_ratio": "Expense Ratio", "aum_in_crores": "AUM",
    "fund_rating": "Fund Rating",
    "upside_capture": "Upside Capture",
    "data_completeness_percentage": "Data Completeness",
}

_GROUP_LABELS = {
    "returns": "Returns", "risk_adjusted": "Risk-Adjusted Performance",
    "risk": "Risk Management", "cost_and_size": "Cost & Size",
    "consistency": "Consistency",
}


def rank_funds_for_comparison(
    funds_metrics: List[Dict],
    scheme_codes: List[str],
) -> Dict:
    """
    Rank funds using weighted min-max normalisation across metric groups.

    Args:
        funds_metrics: List of metric dicts (one per fund, in same order as scheme_codes).
                       Each dict is the serialised FundMetricsRead or empty {}.
        scheme_codes:  Parallel list of scheme_code strings.

    Returns:
        Dict with 'rankings' (list) and 'comparison_summary' (str).
    """
    n = len(scheme_codes)
    if n < 2:
        return {"rankings": [], "comparison_summary": "Need at least 2 funds to compare."}

    # Initialise per-fund accumulators
    # group_scores[i][group] = list of normalised scores for that group
    group_scores: List[Dict[str, List[float]]] = [
        {g: [] for g in _GROUP_WEIGHTS} for _ in range(n)
    ]

    # Per-fund: track which metrics they "won" (best value)
    wins: List[List[str]] = [[] for _ in range(n)]

    for metric_key, (higher_is_better, group) in _METRIC_DEFS.items():
        # Extract values, treating missing metrics dicts as empty
        raw_values = []
        for m in funds_metrics:
            val = m.get(metric_key) if m else None
            # Coerce to float or None
            if val is not None:
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    val = None
            raw_values.append(val)

        # If fewer than 2 funds have data for this metric, skip it
        non_none = [v for v in raw_values if v is not None]
        if len(non_none) < 2:
            continue

        min_val = min(non_none)
        max_val = max(non_none)

        normalised = []
        for val in raw_values:
            if val is None:
                normalised.append(0.0)
            elif max_val == min_val:
                normalised.append(50.0)  # tie
            else:
                if higher_is_better:
                    normalised.append((val - min_val) / (max_val - min_val) * 100.0)
                else:
                    normalised.append((max_val - val) / (max_val - min_val) * 100.0)

        # Record win (best normalised score)
        best_idx = int(np.argmax(normalised))
        if normalised[best_idx] > 0:
            wins[best_idx].append(_METRIC_LABELS.get(metric_key, metric_key))

        for i in range(n):
            group_scores[i][group].append(normalised[i])

    # Compute group averages and composite score
    rankings = []
    for i in range(n):
        gs = {}
        composite = 0.0
        for group, weight in _GROUP_WEIGHTS.items():
            scores = group_scores[i][group]
            avg = sum(scores) / len(scores) if scores else 0.0
            gs[group] = round(avg, 2)
            composite += avg * weight
        rankings.append({
            "scheme_code": scheme_codes[i],
            "composite_score": round(composite, 2),
            "group_scores": gs,
            "wins": wins[i],
        })

    # Sort by composite score descending
    rankings.sort(key=lambda x: x["composite_score"], reverse=True)

    # Assign ranks and recommendation
    for rank_idx, r in enumerate(rankings):
        r["rank"] = rank_idx + 1
        r["is_recommended"] = rank_idx == 0

    # Build recommendation reason for the top fund
    top = rankings[0]
    best_group = max(top["group_scores"], key=top["group_scores"].get)
    top_wins = top["wins"][:4]  # Top 4 winning metrics

    metrics_part = funds_metrics[scheme_codes.index(top["scheme_code"])] or {}

    reason_parts = [f"Highest composite score ({top['composite_score']:.1f}/100)"]
    reason_parts.append(f"strongest in {_GROUP_LABELS.get(best_group, best_group)} ({top['group_scores'][best_group]:.1f})")
    if top_wins:
        reason_parts.append(f"leading in {', '.join(top_wins[:3])}")

    # Add a specific metric callout if available
    if metrics_part.get("sharpe_ratio") is not None:
        reason_parts.append(f"Sharpe {float(metrics_part['sharpe_ratio']):.2f}")
    if metrics_part.get("expense_ratio") is not None:
        reason_parts.append(f"Expense Ratio {float(metrics_part['expense_ratio'])*100:.2f}%")

    top["recommendation_reason"] = ". ".join(reason_parts[:5]) + "."

    # Build comparison summary
    if len(rankings) >= 2:
        gap = rankings[0]["composite_score"] - rankings[1]["composite_score"]
        summary = (
            f"{rankings[0]['scheme_code']} leads by {gap:.1f} points. "
            f"Primary advantage: {_GROUP_LABELS.get(best_group, best_group)}."
        )
    else:
        summary = "Insufficient data for comparison summary."

    return {
        "rankings": rankings,
        "comparison_summary": summary,
    }
