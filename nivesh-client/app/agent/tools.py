"""
Agent tools — LangChain @tool async functions for the Groq multi-agent system.

Tools are grouped into three lists matching the three specialist agents:
  STOCK_TOOLS     → stock_agent   (get_stock_detail, search_stocks, screen_stocks)
  FUND_TOOLS      → fund_agent    (get_fund_detail, compare_funds)
  PORTFOLIO_TOOLS → portfolio_agent (get_portfolio, get_market_overview)

All tools return JSON strings. They never raise — errors are returned as
{"error": "..."} so the LLM handles them gracefully.

All HTTP calls go to localhost:8001 (the client itself) so the proxy layer
handles JWT injection and caching transparently.
"""

import json
import logging
from typing import Optional

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_BASE_URL = "http://localhost:8001"
_API_PREFIX = "/api/v1"


# ── Stock tools ────────────────────────────────────────────────────────────────

@tool
async def get_stock_detail(symbol: str) -> str:
    """
    Get current price, technical indicators (RSI, MACD, EMAs),
    fundamentals (PE, PB, ROE, ROCE, D/E), and composite rating
    for an NSE/BSE stock. Always call this before making any numerical
    claim about a stock's current state.

    Args:
        symbol: NSE stock symbol in uppercase, e.g. RELIANCE, TCS, INFY, HDFCBANK
    """
    sym = symbol.upper().strip()
    try:
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0) as client:
            resp = await client.get(f"{_API_PREFIX}/proxy/stocks/{sym}")
        if resp.status_code == 200:
            return json.dumps(resp.json())
        return json.dumps({"error": f"Stock {sym} not found (HTTP {resp.status_code})"})
    except httpx.TimeoutException:
        return json.dumps({"error": f"Request timed out for stock {sym}"})
    except Exception as exc:
        logger.error("get_stock_detail failed for %s: %s", sym, exc)
        return json.dumps({"error": str(exc)})


@tool
async def search_stocks(query: str) -> str:
    """
    Search for NSE stocks by company name or partial symbol.
    Use this when the user mentions a company name but you are unsure
    of the exact NSE symbol before calling get_stock_detail.

    Args:
        query: Company name or partial symbol, e.g. 'Reliance', 'Tata Consultancy', 'HDFC'
    """
    try:
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0) as client:
            resp = await client.get(f"{_API_PREFIX}/proxy/stocks/search", params={"q": query.strip()})
        if resp.status_code == 200:
            return json.dumps(resp.json())
        return json.dumps({"results": [], "error": f"Search failed (HTTP {resp.status_code})"})
    except Exception as exc:
        logger.error("search_stocks failed for %s: %s", query, exc)
        return json.dumps({"results": [], "error": str(exc)})


@tool
async def screen_stocks(
    min_pe: Optional[float] = None,
    max_pe: Optional[float] = None,
    min_pb: Optional[float] = None,
    max_pb: Optional[float] = None,
    min_roe: Optional[float] = None,
    min_roce: Optional[float] = None,
    max_debt_equity: Optional[float] = None,
    sector: Optional[str] = None,
    market_cap_cat: Optional[str] = None,
    sort_by: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Screen NSE stocks using fundamental and technical filter criteria.
    Returns stocks matching ALL specified conditions sorted by composite score.
    Pass only the filters you need — all are optional.

    Args:
        min_pe: Minimum P/E ratio
        max_pe: Maximum P/E ratio
        min_pb: Minimum P/B ratio
        max_pb: Maximum P/B ratio
        min_roe: Minimum Return on Equity (%)
        min_roce: Minimum Return on Capital Employed (%)
        max_debt_equity: Maximum debt-to-equity ratio
        sector: Sector filter e.g. 'IT', 'BFSI', 'Pharma', 'Auto', 'FMCG'
        market_cap_cat: Market cap category: 'Large', 'Mid', or 'Small'
        sort_by: Field to sort by e.g. 'total_score', 'pe_ratio', 'roe'
        limit: Max results to return (default 10, max 50)
    """
    params: dict = {"limit": limit}
    for key, val in {
        "min_pe": min_pe, "max_pe": max_pe,
        "min_pb": min_pb, "max_pb": max_pb,
        "min_roe": min_roe, "min_roce": min_roce,
        "max_debt_equity": max_debt_equity,
        "sector": sector, "market_cap_cat": market_cap_cat,
        "sort_by": sort_by,
    }.items():
        if val is not None:
            params[key] = val
    try:
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0) as client:
            resp = await client.get(f"{_API_PREFIX}/proxy/stocks/screener", params=params)
        if resp.status_code == 200:
            return json.dumps(resp.json())
        return json.dumps({"results": [], "total": 0, "error": f"Screener failed (HTTP {resp.status_code})"})
    except Exception as exc:
        logger.error("screen_stocks failed: %s", exc)
        return json.dumps({"results": [], "total": 0, "error": str(exc)})


# ── Fund tools ─────────────────────────────────────────────────────────────────

@tool
async def get_fund_detail(scheme_code: str) -> str:
    """
    Get NAV, risk metrics (Sharpe ratio, Sortino ratio, Alpha, Beta,
    Max Drawdown), CAGR (3Y/5Y), and AUM for a mutual fund scheme.
    Always call this before discussing any specific mutual fund's performance.

    Args:
        scheme_code: AMFI scheme code, e.g. '119598', '100644', '120503'
    """
    code = str(scheme_code).strip()
    try:
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0) as client:
            resp = await client.get(f"{_API_PREFIX}/proxy/funds/{code}")
        if resp.status_code == 200:
            return json.dumps(resp.json())
        return json.dumps({"error": f"Fund {code} not found (HTTP {resp.status_code})"})
    except Exception as exc:
        logger.error("get_fund_detail failed for %s: %s", code, exc)
        return json.dumps({"error": str(exc)})


@tool
async def compare_funds(scheme_codes: list[str]) -> str:
    """
    Compare 2-5 mutual funds side-by-side on key metrics.
    Returns per-fund metrics, a ranking, and a recommendation with reason.
    Always use this when comparing multiple funds.

    Args:
        scheme_codes: List of 2-5 AMFI scheme codes e.g. ['119598', '100644']
    """
    codes_str = ",".join(str(c).strip() for c in scheme_codes)
    try:
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0) as client:
            resp = await client.get(f"{_API_PREFIX}/proxy/funds/compare", params={"scheme_codes": codes_str})
        if resp.status_code == 200:
            return json.dumps(resp.json())
        return json.dumps({"error": f"Fund comparison failed (HTTP {resp.status_code})"})
    except Exception as exc:
        logger.error("compare_funds failed: %s", exc)
        return json.dumps({"error": str(exc)})


# ── Portfolio / Market tools ────────────────────────────────────────────────────

@tool
async def get_portfolio() -> str:
    """
    Get the user's portfolio holdings: symbol, asset type (STOCK/FUND),
    quantity, average cost, and buy date.
    Use this for portfolio review or P&L questions.
    """
    try:
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0) as client:
            resp = await client.get(f"{_API_PREFIX}/local/portfolio/holdings")
        if resp.status_code == 200:
            holdings = resp.json()
            return json.dumps({"holdings": holdings, "count": len(holdings)})
        return json.dumps({"holdings": [], "count": 0, "error": "Portfolio unavailable"})
    except Exception as exc:
        logger.error("get_portfolio failed: %s", exc)
        return json.dumps({"holdings": [], "count": 0, "error": str(exc)})


@tool
async def get_market_overview() -> str:
    """
    Get current levels and recent performance for major Indian market indices:
    Nifty 50, Bank Nifty, Nifty 500, etc.
    Use this for market context questions.
    """
    try:
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0) as client:
            resp = await client.get(f"{_API_PREFIX}/proxy/benchmarks", params={"limit": 10})
        if resp.status_code == 200:
            return json.dumps(resp.json())
        return json.dumps({"error": "Market overview unavailable"})
    except Exception as exc:
        logger.error("get_market_overview failed: %s", exc)
        return json.dumps({"error": str(exc)})


# ── Tool groups (one list per specialist agent) ────────────────────────────────

STOCK_TOOLS = [get_stock_detail, search_stocks, screen_stocks]
FUND_TOOLS = [get_fund_detail, compare_funds]
PORTFOLIO_TOOLS = [get_portfolio, get_market_overview]
