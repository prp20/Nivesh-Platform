from typing import Any, Optional
from typing_extensions import TypedDict


class FundAnalysisState(TypedDict):
    scheme_code: str
    # Fetched data
    fund_master: dict[str, Any]
    fund_metrics: dict[str, Any]
    peer_metrics: list[dict[str, Any]]
    # Computed
    composite_score: float
    peer_percentile: float
    category_rank: int
    category_size: int
    # LLM outputs
    verdict_label: str
    verdict_text: str
    key_strengths: list[str]
    key_risks: list[str]
    # Meta
    status: str          # PENDING|FETCHED|RANKED|ANALYSED|PERSISTED|FAILED
    error: Optional[str]
    logs: list[str]
