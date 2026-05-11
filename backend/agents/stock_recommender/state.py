from typing import Any, Optional
from typing_extensions import TypedDict


class StockRecommendationState(TypedDict):
    symbol: str
    # Inputs from prior agents
    stock_analysis: dict[str, Any]    # latest agent_stock_analysis row
    stock_rating: dict[str, Any]      # latest StockRating row
    latest_price: float
    # Rule-based pre-signal (computed before LLM)
    pre_signal: str                   # BUY / HOLD / SELL
    pre_confidence: str               # HIGH / MEDIUM / LOW
    # LLM outputs
    signal: str                       # BUY / HOLD / SELL
    confidence: str
    time_horizon: str                 # SHORT / MEDIUM / LONG
    entry_price_low: Optional[float]
    entry_price_high: Optional[float]
    target_price: Optional[float]
    stop_loss: Optional[float]
    key_catalysts: list[str]
    key_risks: list[str]
    recommendation_text: str
    stock_analysis_id: Optional[int]
    status: str
    error: Optional[str]
    logs: list[str]
