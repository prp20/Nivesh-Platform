from typing import Any, Optional
from typing_extensions import TypedDict


class FundComparisonState(TypedDict):
    fund_codes: list[str]                  # 2–4 scheme codes
    funds_data: dict[str, dict[str, Any]]  # {code: {master, metrics}}
    metrics_matrix: dict[str, Any]         # {code: {metric: value}}
    rankings: dict[str, Any]               # {code: {metric: rank_1_to_4, overall_rank: int}}
    winner_code: str
    ranked_verdict: list[dict[str, Any]]   # [{rank, code, name, summary}]
    narrative: str
    comparison_id: str
    status: str
    error: Optional[str]
    logs: list[str]
