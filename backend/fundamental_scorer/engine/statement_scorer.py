import math
import statistics
from typing import Dict, Any, List, Optional

def safe_div(num, denom) -> Optional[float]:
    if denom is None or num is None or denom == 0:
        return None
    return float(num) / float(denom)

def _clean_series(vals: list, required_key: str) -> List[Optional[float]]:
    result = []
    for s in vals:
        val = s.get(required_key)
        if val is None:
            result.append(None)
            continue
        try:
            result.append(float(val))
        except (ValueError, TypeError):
            result.append(None)
    return result

def _last(series: List[Optional[float]]) -> Optional[float]:
    for val in reversed(series):
        if val is not None:
            return val
    return None

def _cagr(series: List[Optional[float]], years: int) -> Optional[float]:
    valid_vals = [v for v in series if v is not None]
    if len(valid_vals) < 2:
        return None
    start_val = valid_vals[0]
    end_val = valid_vals[-1]
    
    if start_val <= 0:
        if end_val > 0:
            return 100.0
        return 0.0
        
    try:
        ratio = end_val / start_val
        if ratio <= 0:
            return -100.0
        return (pow(ratio, 1.0 / max(1, len(valid_vals) - 1)) - 1) * 100
    except Exception:
        return 0.0

def _norm(value: Optional[float], lo: float, hi: float) -> float:
    if value is None:
        return 50.0  # neutral
    if lo < hi:
        if value <= lo: return 0.0
        if value >= hi: return 100.0
        return (value - lo) / (hi - lo) * 100.0
    else: # reversed
        if value >= lo: return 0.0
        if value <= hi: return 100.0
        return (lo - value) / (lo - hi) * 100.0

def _stddev(series: List[Optional[float]]) -> Optional[float]:
    valid_vals = [v for v in series if v is not None]
    if len(valid_vals) < 2:
        return None
    return statistics.stdev(valid_vals)

class FinancialEngine:
    """
    Deterministic engine for calculating financial scores.
    Strictly NO LLM usage here.
    """

    @staticmethod
    def score_pl(statements: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(statements) < 3:
            return {"score": 0, "error": "Insufficient history (min 3 years)"}

        sales_series = _clean_series(statements, 'sales')
        if all(x is None for x in sales_series):
            sales_series = _clean_series(statements, 'revenue')
            
        op_series = _clean_series(statements, 'operating_profit')
        pat_series = _clean_series(statements, 'net_profit')
        eps_series = _clean_series(statements, 'eps_in_rs')
        if all(x is None for x in eps_series):
            eps_series = _clean_series(statements, 'eps')

        rev_cagr = _cagr(sales_series, 5)
        pat_cagr = _cagr(pat_series, 5)

        # Revenue Score
        rev_cagr_score = 50.0
        if rev_cagr is not None:
            if rev_cagr >= 20: rev_cagr_score = 100
            elif rev_cagr >= 15: rev_cagr_score = 80
            elif rev_cagr >= 10: rev_cagr_score = 60
            elif rev_cagr >= 5: rev_cagr_score = 40
            elif rev_cagr >= 0: rev_cagr_score = 20
            else: rev_cagr_score = 0

        # PAT Score
        pat_cagr_score = 50.0
        if pat_cagr is not None:
            if pat_cagr >= 25: pat_cagr_score = 100
            elif pat_cagr >= 20: pat_cagr_score = 85
            elif pat_cagr >= 15: pat_cagr_score = 70
            elif pat_cagr >= 10: pat_cagr_score = 55
            elif pat_cagr >= 5: pat_cagr_score = 35
            elif pat_cagr >= 0: pat_cagr_score = 15
            else: pat_cagr_score = 0

        # Loss Year Penalty
        loss_years = sum(1 for p in pat_series if p is not None and p < 0)
        penalty = min(loss_years * 15, 30)
        pat_cagr_score = max(0, pat_cagr_score - penalty)

        pl_growth_score = (rev_cagr_score + pat_cagr_score) / 2

        # Margin
        latest_op = _last(op_series)
        latest_sales = _last(sales_series)
        latest_opm_val = safe_div(latest_op, latest_sales)
        latest_opm = latest_opm_val * 100 if latest_opm_val is not None else None

        pl_margin_score = 50.0
        if latest_opm is not None:
            if latest_opm >= 25: pl_margin_score = 100
            elif latest_opm >= 20: pl_margin_score = 85
            elif latest_opm >= 15: pl_margin_score = 65
            elif latest_opm >= 10: pl_margin_score = 45
            elif latest_opm >= 5: pl_margin_score = 25
            else: pl_margin_score = 0

        # EPS Score
        eps_cagr = _cagr(eps_series, 5)
        eps_score = 50.0
        if eps_cagr is not None:
            if eps_cagr >= 20: eps_score = 100
            elif eps_cagr >= 15: eps_score = 80
            elif eps_cagr >= 10: eps_score = 60
            elif eps_cagr >= 5: eps_score = 40
            elif eps_cagr >= 0: eps_score = 20
            else: eps_score = 0
            
        # Consistency Score
        opms = []
        for op, sales in zip(op_series, sales_series):
            m = safe_div(op, sales)
            if m is not None:
                opms.append(m * 100)
        
        opm_sd = _stddev(opms)
        if opm_sd is not None:
            consistency_score = _norm(opm_sd, 5, 1) # 5% SD = 0, 1% SD = 100
        else:
            consistency_score = 50.0

        score = (pl_growth_score * 0.25) + (pl_margin_score * 0.25) + (eps_score * 0.25) + (consistency_score * 0.25)

        return {
            "score": round(score, 2),
            "sub_scores": {
                "growth": round(pl_growth_score, 2),
                "margin": round(pl_margin_score, 2),
                "eps": round(eps_score, 2),
                "consistency": round(consistency_score, 2)
            },
            "metrics": {
                "rev_cagr": round(rev_cagr, 2) if rev_cagr is not None else 0.0,
                "pat_cagr": round(pat_cagr, 2) if pat_cagr is not None else 0.0,
                "latest_opm": round(latest_opm, 2) if latest_opm is not None else 0.0,
                "eps_cagr": round(eps_cagr, 2) if eps_cagr is not None else 0.0
            }
        }
    
    @staticmethod
    def score_bs(statements: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not statements:
            return {"score": 0, "error": "No data"}

        total_assets = _clean_series(statements, 'total_assets')
        borrowings = _clean_series(statements, 'borrowings')
        current_liabilities = _clean_series(statements, 'current_liabilities')
        other_liabilities = _clean_series(statements, 'other_liabilities')
        current_assets = _clean_series(statements, 'current_assets')
        other_assets = _clean_series(statements, 'other_assets')
        cwip = _clean_series(statements, 'cwip')
        fixed_assets = _clean_series(statements, 'fixed_assets')
        reserves = _clean_series(statements, 'reserves')
        equity_capital = _clean_series(statements, 'equity_capital')

        # 1. Leverage (Debt to Equity)
        latest_debt = _last(borrowings)
        latest_eq = _last(equity_capital) or 0
        latest_res = _last(reserves) or 0
        net_worth = latest_eq + latest_res
        
        de_ratio = safe_div(latest_debt, net_worth)
        leverage_score = _norm(de_ratio, 2.0, 0.2) 

        # 2. Liquidity (Current Ratio - fallback to other assets/liabilities if CA/CL not present)
        # Note Screener tends to have other_assets and other_liabilities.
        latest_ca = _last(current_assets)
        if latest_ca is None: latest_ca = _last(other_assets)
        latest_cl = _last(current_liabilities)
        if latest_cl is None: latest_cl = _last(other_liabilities)
        
        current_ratio = safe_div(latest_ca, latest_cl)
        liquidity_score = _norm(current_ratio, 0.8, 2.0)

        # 3. Networth Growth
        res_cagr = _cagr(reserves, 5)
        networth_score = _norm(res_cagr, 5.0, 15.0)

        # 4. Asset Quality (CWIP / Fixed Assets)
        latest_cwip = _last(cwip)
        latest_fa = _last(fixed_assets)
        asset_ratio = safe_div(latest_cwip, latest_fa)
        asset_score = _norm(asset_ratio, 0.5, 0.05)

        # Weights: Leverage 30%, Liquidity 20%, Asset 20%, Networth 30%.
        weights = {"leverage": 0.3, "liquidity": 0.2, "asset": 0.2, "networth": 0.3}
        final_score = (leverage_score * weights["leverage"] + 
                       liquidity_score * weights["liquidity"] + 
                       asset_score * weights["asset"] +
                       networth_score * weights["networth"])

        return {
            "score": round(final_score, 2),
            "sub_scores": {
                "leverage": round(leverage_score, 2),
                "liquidity": round(liquidity_score, 2),
                "asset": round(asset_score, 2),
                "networth": round(networth_score, 2)
            },
            "metrics": {
                "debt_to_equity": round(de_ratio, 2) if de_ratio is not None else 0.0,
                "current_ratio": round(current_ratio, 2) if current_ratio is not None else 0.0,
                "reserves_cagr": round(res_cagr, 2) if res_cagr is not None else 0.0
            }
        }
    
    @staticmethod
    def score_cf(statements: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not statements:
            return {"score": 0, "error": "No data"}
            
        cfo = _clean_series(statements, 'cash_from_operating_activity')
        cff = _clean_series(statements, 'cash_from_investing_activity')
        cf_fin = _clean_series(statements, 'cash_from_financing_activity')
        pat = _clean_series(statements, 'net_profit')
        
        # CFO to PAT ratio
        cfo_sum = sum(c for c in cfo[-3:] if c is not None)
        pat_sum = sum(p for p in pat[-3:] if p is not None)
        cfo_pat_ratio = safe_div(cfo_sum, pat_sum)
        operating_score = _norm(cfo_pat_ratio, 0.5, 1.2)
        
        # Free Cash Flow / Capex coverage
        fcf_years = 0
        valid_years = 0
        for o, i in zip(cfo[-3:], cff[-3:]):
            if o is not None and i is not None:
                valid_years += 1
                if (o + i) > 0: # investing is usually negative, so o + i is FCF
                    fcf_years += 1
                    
        capex_score = 50.0
        if valid_years > 0:
            capex_score = (fcf_years / valid_years) * 100.0
            
        # Financing score
        financing_score = 50.0
        latest_cfo = _last(cfo)
        latest_cf_fin = _last(cf_fin)
        if latest_cfo is not None and latest_cfo > 0:
            if latest_cf_fin is not None and latest_cf_fin < 0:
                financing_score = 100.0
            else:
                financing_score = 40.0

        weights = {"operating": 0.4, "capex": 0.35, "financing": 0.25}
        final_score = (operating_score * weights["operating"] + 
                       capex_score * weights["capex"] + 
                       financing_score * weights["financing"])

        return {
            "score": round(final_score, 2),
            "sub_scores": {
                "operating": round(operating_score, 2),
                "capex": round(capex_score, 2),
                "financing": round(financing_score, 2)
            },
            "metrics": {
                "cfo_to_pat": round(cfo_pat_ratio, 2) if cfo_pat_ratio is not None else 0.0,
                "fcf_positive_years": fcf_years
            }
        }
