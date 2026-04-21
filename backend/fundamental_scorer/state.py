from typing import Dict, Any, List, TypedDict, Optional

class ScoringState(TypedDict):
    """
    LangGraph state for the fundamental scoring pipeline.
    This state is passed between nodes and updated as we progress.
    """
    # Identification
    stock_id: int
    symbol: str
    period_type: str  # 'annual' or 'quarterly'
    score_version: str # e.g., 'v1.0'
    
    # Raw Data (fetched from DB)
    # Map of statement_type (PL, BS, CF) to list of statement data
    statements_data: Dict[str, List[Dict[str, Any]]]
    
    # Deterministic Analysis Results (from Engine)
    pl_results: Optional[Dict[str, Any]]
    bs_results: Optional[Dict[str, Any]]
    cf_results: Optional[Dict[str, Any]]
    
    # Aggregated Score
    composite_score: float
    
    # Qualitative Reasoning (from LLM Node)
    reasoning_label: str
    reasoning_text: str
    
    # Workflow Metadata
    status: str # 'PENDING', 'FETCHED', 'SCORED', 'REASONED', 'COMPLETED', 'FAILED'
    error: Optional[str]
    logs: List[str]
