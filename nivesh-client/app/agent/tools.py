"""
Agent tools — financial data tool definitions and executor.

TOOLS: List of tool schemas for the Anthropic API (input_schema format).
execute_tool(): Dispatches each tool call to the appropriate local endpoint.

All server data goes through /proxy/* (which handles caching + JWT).
User data (portfolio) goes through /local/portfolio/* (SQLite-only).
"""

import logging

import httpx

logger = logging.getLogger(__name__)

# ── Tool definitions ──────────────────────────────────────────────────────────
# These are passed directly to the Anthropic API messages.create(tools=TOOLS).
# The input_schema must be valid JSON Schema.

TOOLS = [
    {
        "name": "get_stock_detail",
        "description": (
            "Get current price, technical indicators (RSI, MACD, EMAs), "
            "fundamentals (PE, PB, ROE, ROCE, D/E), and composite rating "
            "for an NSE/BSE stock. Use this before making any numerical claim "
            "about a stock's current state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": (
                        "NSE stock symbol in uppercase, e.g. RELIANCE, TCS, "
                        "INFY, HDFCBANK, ICICIBANK"
                    ),
                }
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_fund_detail",
        "description": (
            "Get NAV, risk metrics (Sharpe ratio, Sortino ratio, Alpha, Beta, "
            "Max Drawdown), CAGR (3Y/5Y), and AUM for a mutual fund scheme. "
            "Use this before discussing any specific mutual fund's performance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scheme_code": {
                    "type": "string",
                    "description": "AMFI scheme code, e.g. 119598, 100644, 120503",
                }
            },
            "required": ["scheme_code"],
        },
    },
    {
        "name": "compare_funds",
        "description": (
            "Compare 2–5 mutual funds side-by-side on key metrics. "
            "Returns per-fund metrics, a ranking, and a recommendation "
            "with reason. Always use this when comparing multiple funds."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "scheme_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of 2–5 AMFI scheme codes",
                    "minItems": 2,
                    "maxItems": 5,
                }
            },
            "required": ["scheme_codes"],
        },
    },
    {
        "name": "search_stocks",
        "description": (
            "Search for NSE stocks by company name or partial symbol. "
            "Use this when the user mentions a company name but you are "
            "unsure of the exact NSE symbol before calling get_stock_detail."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query — company name or partial symbol, "
                        "e.g. 'Reliance', 'Tata Consultancy', 'HDFC'"
                    ),
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "screen_stocks",
        "description": (
            "Screen NSE stocks based on fundamental and technical filter "
            "criteria. Returns stocks that match ALL specified conditions, "
            "sorted by composite score by default. Pass only the filters you "
            "need — all are optional."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_pe": {"type": "number", "description": "Minimum P/E ratio"},
                "max_pe": {"type": "number", "description": "Maximum P/E ratio"},
                "min_pb": {"type": "number", "description": "Minimum P/B ratio"},
                "max_pb": {"type": "number", "description": "Maximum P/B ratio"},
                "min_roe": {
                    "type": "number",
                    "description": "Minimum Return on Equity (%)",
                },
                "min_roce": {
                    "type": "number",
                    "description": "Minimum Return on Capital Employed (%)",
                },
                "max_debt_equity": {
                    "type": "number",
                    "description": "Maximum debt-to-equity ratio",
                },
                "sector": {
                    "type": "string",
                    "description": (
                        "Sector filter, e.g. 'IT', 'BFSI', 'Pharma', "
                        "'Auto', 'FMCG', 'Metal', 'Realty'"
                    ),
                },
                "market_cap_cat": {
                    "type": "string",
                    "description": "Market cap category: 'Large', 'Mid', or 'Small'",
                },
                "sort_by": {
                    "type": "string",
                    "description": (
                        "Field to sort by, e.g. 'total_score', 'pe_ratio', "
                        "'roe', 'roce', 'debt_equity'"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 10, max 50)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_market_overview",
        "description": (
            "Get current levels and recent performance for major Indian "
            "market indices: Nifty 50, Bank Nifty, Nifty 500, etc. "
            "Use this for market context questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_portfolio",
        "description": (
            "Get the user's portfolio holdings: symbol, asset type "
            "(STOCK/FUND), quantity, average cost, and buy date. "
            "Use this for portfolio review or P&L questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────────────────────

_CLIENT_BASE_URL = "http://localhost:8001"


async def execute_tool(name: str, tool_input: dict) -> dict:
    """
    Execute a named tool call and return its result as a dict.

    All requests go to localhost:8001 so the proxy layer handles
    JWT injection and caching transparently.

    Returns a dict — always. Never raises (errors are returned as
    {"error": "..."} so the LLM can handle them gracefully).
    """
    try:
        async with httpx.AsyncClient(
            base_url=_CLIENT_BASE_URL, timeout=30.0
        ) as client:
            return await _dispatch(client, name, tool_input)
    except httpx.TimeoutException:
        logger.warning("Tool %s timed out", name)
        return {"error": f"Tool {name} timed out — server may be offline"}
    except Exception as e:
        logger.error("Tool %s failed: %s", name, e)
        return {"error": str(e)}


async def _dispatch(client: httpx.AsyncClient, name: str, tool_input: dict) -> dict:
    """Route a tool name to its HTTP call. Called inside execute_tool."""
    try:
        return await _do_dispatch(client, name, tool_input)
    except KeyError as e:
        return {"error": f"Tool {name} is missing required input: {e}"}


async def _do_dispatch(client: httpx.AsyncClient, name: str, tool_input: dict) -> dict:

    if name == "get_stock_detail":
        symbol = tool_input["symbol"].upper().strip()
        resp = await client.get(f"/proxy/stocks/{symbol}")
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"Stock {symbol} not found (HTTP {resp.status_code})"}

    elif name == "get_fund_detail":
        scheme_code = str(tool_input["scheme_code"]).strip()
        resp = await client.get(f"/proxy/funds/{scheme_code}")
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"Fund {scheme_code} not found (HTTP {resp.status_code})"}

    elif name == "compare_funds":
        codes = tool_input["scheme_codes"]
        scheme_codes_str = ",".join(str(c).strip() for c in codes)
        resp = await client.get(
            "/proxy/funds/compare",
            params={"scheme_codes": scheme_codes_str},
        )
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"Fund comparison failed (HTTP {resp.status_code})"}

    elif name == "search_stocks":
        query = tool_input["query"].strip()
        resp = await client.get("/proxy/stocks/search", params={"q": query})
        if resp.status_code == 200:
            return resp.json()
        return {"results": [], "error": f"Search failed (HTTP {resp.status_code})"}

    elif name == "screen_stocks":
        # Pass all non-None values as query params
        params = {k: v for k, v in tool_input.items() if v is not None}
        if "limit" not in params:
            params["limit"] = 10
        resp = await client.get("/proxy/stocks/screener", params=params)
        if resp.status_code == 200:
            return resp.json()
        return {"results": [], "total": 0, "error": f"Screener failed (HTTP {resp.status_code})"}

    elif name == "get_market_overview":
        resp = await client.get("/proxy/benchmarks", params={"limit": 10})
        if resp.status_code == 200:
            return resp.json()
        return {"error": "Market overview unavailable"}

    elif name == "get_portfolio":
        resp = await client.get("/local/portfolio/holdings")
        if resp.status_code == 200:
            holdings = resp.json()
            return {"holdings": holdings, "count": len(holdings)}
        return {"holdings": [], "count": 0, "error": "Portfolio unavailable"}

    else:
        return {"error": f"Unknown tool: {name}"}
