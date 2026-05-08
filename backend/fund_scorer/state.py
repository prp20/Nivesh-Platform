from typing import Dict, Any, List, TypedDict, Optional

class FundScoringState(TypedDict):
    """
    LangGraph state for the mutual fund agentic analysis pipeline.
    """
    # Identification
    scheme_code: str
    scheme_name: str
    category: str
    
    # Metrics Data (fetched from DB)
    metrics: Dict[str, Any]
    
    # Aggregated Score (could be a subset of metrics or computed)
    composite_score: float
    
    # Qualitative Reasoning (from LLM Node)
    reasoning_label: str
    reasoning_text: str
    
    # Workflow Metadata
    status: str # 'PENDING', 'FETCHED', 'REASONED', 'COMPLETED', 'FAILED'
    error: Optional[str]
    logs: List[str]
