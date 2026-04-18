from ..state import ScoringState
from ..engine.statement_scorer import FinancialEngine
from typing import Dict, Any

def compute_scores_node(state: ScoringState) -> Dict[str, Any]:
    """
    Orchestrates the deterministic scoring of all financial statements.
    This node acts as a bridge to the pure math engine.
    """
    data = state.get('statements_data', {})
    
    # 1. Score P&L
    pl_results = FinancialEngine.score_pl(data.get('PL', []))
    
    # 2. Score Balance Sheet
    bs_results = FinancialEngine.score_bs(data.get('BS', []))
    
    # 3. Score Cash Flow
    cf_results = FinancialEngine.score_cf(data.get('CF', []))
    
    # Check for engine errors
    if "error" in pl_results and "error" in bs_results and "error" in cf_results:
        return {
            "status": "FAILED",
            "error": "Engine failed to score any statement type",
            "logs": state.get("logs", []) + ["Engine error: Multiple failures"]
        }

    # 4. Calculate Composite Fundamental Score
    # We apply default weights (can be made sector-specific later)
    # P&L: 40%, Balance Sheet: 40%, Cash Flow: 20%
    w_pl, w_bs, w_cf = 0.4, 0.4, 0.2
    
    # Handle missing scores by redistributing weights or using 0
    s_pl = pl_results.get('score', 0)
    s_bs = bs_results.get('score', 0)
    s_cf = cf_results.get('score', 0)
    
    composite = (s_pl * w_pl) + (s_bs * w_bs) + (s_cf * w_cf)
                 
    return {
        "pl_results": pl_results,
        "bs_results": bs_results,
        "cf_results": cf_results,
        "composite_score": round(composite, 2),
        "status": "SCORED",
        "logs": state.get("logs", []) + ["Deterministic scoring completed successfully"]
    }
