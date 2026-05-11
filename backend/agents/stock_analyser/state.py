from typing import Any, Optional
from typing_extensions import TypedDict


class StockAnalysisState(TypedDict):
    symbol: str
    # Raw data (populated by fetch nodes)
    stock_master: dict[str, Any]
    latest_price: dict[str, Any]
    financial_ratios: dict[str, Any]      # latest annual row
    financial_statements: dict[str, Any]  # {PL: {...}, BS: {...}, CF: {...}}
    technical_indicators: dict[str, Any]  # latest 1d row
    sector_medians: dict[str, Any]        # sector median ratios
    # Sub-agent outputs (each node fills exactly ONE block)
    fundamental_score: float              # 0-100
    fundamental_signal: str              # STRONG / GOOD / WEAK / POOR
    fundamental_reasoning: str
    technical_signal: str                # BULLISH / NEUTRAL / BEARISH
    technical_reasoning: str
    valuation_signal: str                # UNDERVALUED / FAIR / OVERVALUED
    valuation_reasoning: str
    # Aggregate
    overall_health_score: float
    full_narrative: str
    stock_analysis_id: Optional[int]
    status: str
    error: Optional[str]
    logs: list[str]
