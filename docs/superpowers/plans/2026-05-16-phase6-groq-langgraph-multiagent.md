# Phase 6 — Groq + LangGraph Multi-Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Anthropic SDK agent with a LangGraph supervisor + 3 specialist ReAct agents powered by ChatGroq (llama-3.3-70b-versatile), preserving the existing SQLite persistence layer and React UI.

**Architecture:** A LangGraph `StateGraph` routes user queries through a supervisor node that picks one of three specialist worker agents (stock, fund, portfolio/market). Each worker is a `create_react_agent` ReAct loop with its own tool subset. The supervisor decides FINISH after the worker replies. Message history is loaded from and saved back to SQLite `agent_messages`.

**Tech Stack:** `langchain-groq>=1.1.0`, `langgraph>=1.2.0`, `langchain>=1.3.0`, `langchain-core>=0.3.0`, `httpx` (existing), FastAPI + SQLAlchemy async (existing).

---

## Baseline — What Already Exists

| Component | Status | Location |
|---|---|---|
| All agent CRUD endpoints + `/chat` wired to `run_turn` | ✅ Done | `app/routers/agent.py` |
| `agent_sessions`, `agent_messages`, `agent_memory` tables | ✅ Done | `app/models/agent.py` |
| `memory.py` — `load_memory_context`, `save_memory_item` | ✅ Done | `app/agent/memory.py` |
| `tools.py` — 7 LangChain @tool async functions (STOCK/FUND/PORTFOLIO_TOOLS) | ✅ Done | `app/agent/tools.py` |
| `runner.py` — run_turn uses LangGraph supervisor + ChatGroq | ✅ Done | `app/agent/runner.py` |
| `agents.py` — 3 specialist ReAct agents | ✅ Done | `app/agent/agents.py` |
| `supervisor.py` — LangGraph StateGraph with RouteDecision routing | ✅ Done | `app/agent/supervisor.py` |
| `langchain-groq/langgraph/langchain/langchain-core` in requirements | ✅ Done | `nivesh-client/requirements.txt` |
| `GROQ_API_KEY` + `AGENT_MODEL=llama-3.3-70b-versatile` in config | ✅ Done | `app/config.py` |

---

## File Map

```
nivesh-client/
├── requirements.txt              ← MODIFY: swap anthropic for langchain-*
├── app/
│   ├── config.py                 ← MODIFY: GROQ_API_KEY, AGENT_MODEL
│   └── agent/
│       ├── __init__.py           ← UNCHANGED
│       ├── memory.py             ← UNCHANGED
│       ├── tools.py              ← REWRITE: @tool async functions, 3 export lists
│       ├── agents.py             ← CREATE: build_stock_agent, build_fund_agent, build_portfolio_agent
│       ├── supervisor.py         ← CREATE: AgentState, RouteDecision, build_graph()
│       └── runner.py             ← REWRITE: run_turn uses build_graph()
```

---

## Task 1: Update requirements.txt and config.py

**Files:**
- Modify: `nivesh-client/requirements.txt`
- Modify: `nivesh-client/app/config.py`

- [ ] **Step 1: Replace anthropic with langchain packages in requirements.txt**

Open `nivesh-client/requirements.txt`. Replace the line `anthropic>=0.51.0` with:

```text
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic-settings==2.2.1
sqlalchemy[asyncio]==2.0.30
aiosqlite==0.20.0
alembic==1.13.1
httpx==0.27.0
apscheduler==3.10.4
langchain-groq>=1.1.0
langgraph>=1.2.0
langchain>=1.3.0
langchain-core>=0.3.0
nivesh-shared @ ../nivesh-shared
```

- [ ] **Step 2: Update config.py — replace ANTHROPIC_API_KEY with GROQ_API_KEY**

Open `nivesh-client/app/config.py`. Replace:

```python
    # ── Agentic layer ─────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""           # Set in ~/.nivesh/.env
    AGENT_MODEL: str = "claude-sonnet-4-6"
```

With:

```python
    # ── Agentic layer ─────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""                # Set in ~/.nivesh/.env (gsk_...)
    AGENT_MODEL: str = "llama-3.3-70b-versatile"
```

- [ ] **Step 3: Verify config imports**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "from app.config import settings; print('GROQ_API_KEY field:', 'GROQ_API_KEY' in settings.model_fields); print('AGENT_MODEL:', settings.AGENT_MODEL)"
```

Expected output:
```
GROQ_API_KEY field: True
AGENT_MODEL: llama-3.3-70b-versatile
```

- [ ] **Step 4: Commit**

```bash
git add nivesh-client/requirements.txt nivesh-client/app/config.py
git commit -m "feat(phase6): swap anthropic for langchain-groq, GROQ_API_KEY config"
```

---

## Task 2: Rewrite tools.py with LangChain @tool functions

**Files:**
- Rewrite: `nivesh-client/app/agent/tools.py`

All tools are now `@tool`-decorated async functions. They return a JSON string (LangChain tool results must be strings). They never raise — errors are embedded in the returned JSON.

Three export lists (`STOCK_TOOLS`, `FUND_TOOLS`, `PORTFOLIO_TOOLS`) replace the old `TOOLS` list and `execute_tool` dispatcher.

- [ ] **Step 1: Write the new tools.py**

Replace the entire contents of `nivesh-client/app/agent/tools.py` with:

```python
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
            resp = await client.get(f"/proxy/stocks/{sym}")
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
            resp = await client.get("/proxy/stocks/search", params={"q": query.strip()})
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
            resp = await client.get("/proxy/stocks/screener", params=params)
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
            resp = await client.get(f"/proxy/funds/{code}")
        if resp.status_code == 200:
            return json.dumps(resp.json())
        return json.dumps({"error": f"Fund {code} not found (HTTP {resp.status_code})"})
    except Exception as exc:
        logger.error("get_fund_detail failed for %s: %s", code, exc)
        return json.dumps({"error": str(exc)})


@tool
async def compare_funds(scheme_codes: list[str]) -> str:
    """
    Compare 2–5 mutual funds side-by-side on key metrics.
    Returns per-fund metrics, a ranking, and a recommendation with reason.
    Always use this when comparing multiple funds.

    Args:
        scheme_codes: List of 2–5 AMFI scheme codes e.g. ['119598', '100644']
    """
    codes_str = ",".join(str(c).strip() for c in scheme_codes)
    try:
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0) as client:
            resp = await client.get("/proxy/funds/compare", params={"scheme_codes": codes_str})
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
            resp = await client.get("/local/portfolio/holdings")
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
            resp = await client.get("/proxy/benchmarks", params={"limit": 10})
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
```

- [ ] **Step 2: Verify tools load and are recognised as LangChain tools**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "
from app.agent.tools import STOCK_TOOLS, FUND_TOOLS, PORTFOLIO_TOOLS
all_tools = STOCK_TOOLS + FUND_TOOLS + PORTFOLIO_TOOLS
print(f'Total tools: {len(all_tools)}')
for t in all_tools:
    print(f'  {t.name}: {type(t).__name__}')
"
```

Expected output:
```
Total tools: 7
  get_stock_detail: StructuredTool
  search_stocks: StructuredTool
  screen_stocks: StructuredTool
  get_fund_detail: StructuredTool
  compare_funds: StructuredTool
  get_portfolio: StructuredTool
  get_market_overview: StructuredTool
```

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/agent/tools.py
git commit -m "feat(phase6): rewrite tools.py as LangChain @tool async functions (3 groups)"
```

---

## Task 3: Create agents.py — Three Specialist ReAct Agents

**Files:**
- Create: `nivesh-client/app/agent/agents.py`

- [ ] **Step 1: Create agents.py**

Create `nivesh-client/app/agent/agents.py` with the following content:

```python
"""
Specialist ReAct agents for the Nivesh multi-agent system.

Three agents, each with a focused tool subset:
  build_stock_agent()     → get_stock_detail, search_stocks, screen_stocks
  build_fund_agent()      → get_fund_detail, compare_funds
  build_portfolio_agent() → get_portfolio, get_market_overview

Each returns a compiled LangGraph ReAct agent graph.
Pass worker_system_prompt as a string to inject the Nivesh persona + memory context.
"""

from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from .tools import FUND_TOOLS, PORTFOLIO_TOOLS, STOCK_TOOLS


def build_stock_agent(llm: ChatGroq, system_prompt: str):
    """
    ReAct agent specialised in NSE/BSE stock analysis and screening.
    Tools: get_stock_detail, search_stocks, screen_stocks.
    """
    return create_react_agent(llm, STOCK_TOOLS, prompt=system_prompt)


def build_fund_agent(llm: ChatGroq, system_prompt: str):
    """
    ReAct agent specialised in mutual fund research and comparison.
    Tools: get_fund_detail, compare_funds.
    """
    return create_react_agent(llm, FUND_TOOLS, prompt=system_prompt)


def build_portfolio_agent(llm: ChatGroq, system_prompt: str):
    """
    ReAct agent specialised in portfolio holdings and market overview.
    Tools: get_portfolio, get_market_overview.
    """
    return create_react_agent(llm, PORTFOLIO_TOOLS, prompt=system_prompt)
```

- [ ] **Step 2: Verify agents.py imports correctly**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "
from app.agent.agents import build_stock_agent, build_fund_agent, build_portfolio_agent
print('agents.py imports OK')
"
```

Expected: `agents.py imports OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/agent/agents.py
git commit -m "feat(phase6): create agents.py — 3 specialist ReAct agents (stock, fund, portfolio)"
```

---

## Task 4: Create supervisor.py — LangGraph Graph Assembly

**Files:**
- Create: `nivesh-client/app/agent/supervisor.py`

- [ ] **Step 1: Create supervisor.py**

Create `nivesh-client/app/agent/supervisor.py` with the following content:

```python
"""
LangGraph supervisor graph for the Nivesh multi-agent system.

build_graph(memory_context):
    Assembles and compiles the full StateGraph:
      START → supervisor → [stock_agent | fund_agent | portfolio_agent] → supervisor → END

    The supervisor uses ChatGroq with structured output (RouteDecision) to decide
    which specialist agent to invoke, or FINISH when the answer is ready.

    Each worker agent runs as a sub-graph (create_react_agent). New messages
    generated by workers are appended to the shared state; the supervisor sees
    them on the next turn and decides FINISH.
"""

import logging
from typing import Annotated, Literal, Optional

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict

from ..config import settings
from .agents import build_fund_agent, build_portfolio_agent, build_stock_agent

logger = logging.getLogger(__name__)


# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next: Optional[str]


# ── Routing schema ─────────────────────────────────────────────────────────────

class RouteDecision(BaseModel):
    next: Literal["stock_agent", "fund_agent", "portfolio_agent", "FINISH"]
    reason: str


# ── System prompts ─────────────────────────────────────────────────────────────

SUPERVISOR_SYSTEM = """\
You are a routing supervisor for Nivesh, an Indian equity market research platform.
Your ONLY job is to decide which specialist agent should handle the user's query,
then return FINISH once the specialist has provided a complete answer.

Available agents:
- stock_agent: NSE/BSE stock prices, technical indicators (RSI, MACD, EMAs),
  fundamentals (PE, PB, ROE, ROCE, D/E), screening stocks by criteria, symbol search
- fund_agent: mutual fund NAV, Sharpe/Sortino/Alpha/Beta/Max Drawdown, CAGR,
  side-by-side fund comparisons, AMFI scheme codes
- portfolio_agent: user's portfolio holdings and P&L, market indices
  (Nifty 50, Bank Nifty, sector performance)

Routing rules:
1. If the last message is from the user → pick the most relevant agent
2. If the last message is from a specialist agent with a complete answer → return FINISH
3. Never route to the same agent twice consecutively
"""

WORKER_SYSTEM = """\
You are Nivesh Agent, a personal financial research assistant for Indian equity \
markets (NSE/BSE).

Rules:
- Always call a tool to fetch live data before making specific numerical claims
- Use ₹ for Indian currency amounts
- Reference stocks by NSE symbol (e.g. RELIANCE, TCS, INFY)
- If a response contains _offline: true, note that data is from cache
- Be concise — users see a trading/research interface, not a blog post
- For fund comparisons, highlight the ranking and top recommendation
"""


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_graph(memory_context: str = ""):
    """
    Build and compile the full supervisor + worker LangGraph.

    Args:
        memory_context: Optional string of known user facts from agent_memory table.
                        Injected into worker system prompts for personalisation.

    Returns:
        A compiled LangGraph StateGraph ready for ainvoke().
    """
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.AGENT_MODEL,
        temperature=0,
        max_tokens=2048,
    )

    # Worker system prompt — base + optional memory context
    worker_system = WORKER_SYSTEM
    if memory_context:
        worker_system = f"{WORKER_SYSTEM}\n\nKnown facts about the user:\n{memory_context}"

    # Build the three specialist agents
    stock_agent = build_stock_agent(llm, worker_system)
    fund_agent = build_fund_agent(llm, worker_system)
    portfolio_agent = build_portfolio_agent(llm, worker_system)

    # Supervisor LLM uses structured output for routing decisions
    router_llm = llm.with_structured_output(RouteDecision)

    # ── Node definitions ───────────────────────────────────────────────────────

    async def supervisor_node(state: AgentState) -> dict:
        """Route to a specialist agent or decide FINISH."""
        messages = [SystemMessage(content=SUPERVISOR_SYSTEM)] + list(state["messages"])
        decision = await router_llm.ainvoke(messages)
        logger.info(
            "Supervisor → %s (reason: %s)", decision.next, decision.reason
        )
        return {"next": decision.next}

    async def run_stock_agent(state: AgentState) -> dict:
        """Invoke the stock specialist and return only the new messages it generated."""
        n_before = len(state["messages"])
        result = await stock_agent.ainvoke({"messages": list(state["messages"])})
        return {"messages": result["messages"][n_before:]}

    async def run_fund_agent(state: AgentState) -> dict:
        """Invoke the fund specialist and return only the new messages it generated."""
        n_before = len(state["messages"])
        result = await fund_agent.ainvoke({"messages": list(state["messages"])})
        return {"messages": result["messages"][n_before:]}

    async def run_portfolio_agent(state: AgentState) -> dict:
        """Invoke the portfolio/market specialist and return only the new messages it generated."""
        n_before = len(state["messages"])
        result = await portfolio_agent.ainvoke({"messages": list(state["messages"])})
        return {"messages": result["messages"][n_before:]}

    def route_next(state: AgentState) -> str:
        """Conditional edge: read state['next'] set by supervisor_node."""
        next_val = state.get("next") or ""
        if next_val == "FINISH" or not next_val:
            return END
        return next_val

    # ── Graph assembly ─────────────────────────────────────────────────────────

    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("stock_agent", run_stock_agent)
    graph.add_node("fund_agent", run_fund_agent)
    graph.add_node("portfolio_agent", run_portfolio_agent)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_next,
        {
            "stock_agent": "stock_agent",
            "fund_agent": "fund_agent",
            "portfolio_agent": "portfolio_agent",
            END: END,
        },
    )
    graph.add_edge("stock_agent", "supervisor")
    graph.add_edge("fund_agent", "supervisor")
    graph.add_edge("portfolio_agent", "supervisor")

    return graph.compile()
```

- [ ] **Step 2: Verify supervisor.py imports correctly**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "
from app.agent.supervisor import build_graph, AgentState, RouteDecision
print('supervisor.py imports OK')
print('RouteDecision next options:', RouteDecision.model_fields['next'].annotation)
"
```

Expected output contains: `supervisor.py imports OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/agent/supervisor.py
git commit -m "feat(phase6): create supervisor.py — LangGraph StateGraph with RouteDecision routing"
```

---

## Task 5: Rewrite runner.py — run_turn Uses the LangGraph Graph

**Files:**
- Rewrite: `nivesh-client/app/agent/runner.py`

- [ ] **Step 1: Write the new runner.py**

Replace the entire contents of `nivesh-client/app/agent/runner.py` with:

```python
"""
Agent runner — orchestrates one conversational turn via the LangGraph multi-agent graph.

run_turn(session_id, user_message, db):
    1. Guards on empty GROQ_API_KEY
    2. Loads conversation history from agent_messages (SQLite)
    3. Converts rows to LangChain message objects
    4. Injects agent memory into the worker system prompt via build_graph()
    5. Runs the supervisor + specialist graph with recursion_limit=10
    6. Persists new messages (assistant turns + tool calls/results) to SQLite
    7. Returns the final AIMessage text as the reply string
"""

import json
import logging
from typing import Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from ..config import settings
from ..models.agent import AgentMessage, AgentSession
from .memory import load_memory_context
from .supervisor import build_graph

logger = logging.getLogger(__name__)


async def run_turn(session_id: int, user_message: str, db: AsyncSession) -> str:
    """
    Execute one conversational turn for the given session.

    Precondition: The user message has already been stored in agent_messages
    with the correct sequence_num (done by the /chat endpoint before this call).

    Returns: final assistant reply text string.
    """
    # ── Guard ──────────────────────────────────────────────────────────────────
    if not settings.GROQ_API_KEY:
        return (
            "Groq API key is not configured. "
            "Add GROQ_API_KEY=gsk_... to ~/.nivesh/.env and restart."
        )

    # ── Load conversation history from SQLite ──────────────────────────────────
    history_result = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.sequence_num.asc())
    )
    history = list(history_result.scalars().all())

    last_seq = max((m.sequence_num for m in history), default=0)
    next_seq = last_seq + 1

    # ── Convert SQLite rows → LangChain messages ───────────────────────────────
    lc_messages = _build_lc_messages(history)

    # ── Load agent memory for system prompt personalisation ────────────────────
    memory_context = await load_memory_context(db)

    # ── Run the supervisor + specialist graph ──────────────────────────────────
    try:
        graph = build_graph(memory_context=memory_context)
        result = await graph.ainvoke(
            {"messages": lc_messages, "next": None},
            config={"recursion_limit": 10},
        )
    except Exception as exc:
        # Catches GraphRecursionError and any Groq API errors
        err_msg = str(exc)
        if "recursion" in err_msg.lower():
            logger.warning("Recursion limit hit for session %d", session_id)
            return "I reached my reasoning limit. Please ask a more focused question."
        logger.error("Graph execution failed for session %d: %s", session_id, exc)
        return (
            "Sorry, I encountered an error processing your request. "
            "Check that GROQ_API_KEY is set in ~/.nivesh/.env"
        )

    # ── Persist new messages to SQLite ─────────────────────────────────────────
    n_input = len(lc_messages)
    new_messages: list[BaseMessage] = result["messages"][n_input:]

    final_reply = "I could not generate a response. Please try again."

    for msg in new_messages:
        if isinstance(msg, AIMessage):
            # Extract tool_calls JSON for storage if present
            tool_calls_json = None
            if msg.tool_calls:
                tool_calls_json = [
                    {"name": tc["name"], "id": tc["id"], "args": tc["args"]}
                    for tc in msg.tool_calls
                ]

            content_str = msg.content if isinstance(msg.content, str) else None

            await _save_message(
                db, session_id, next_seq,
                role="assistant",
                content_text=content_str,
                content_json=tool_calls_json,
                tool_name=None,
            )
            next_seq += 1

            # Track the last non-empty text response as the final reply
            if content_str:
                final_reply = content_str

        elif isinstance(msg, ToolMessage):
            await _save_message(
                db, session_id, next_seq,
                role="tool",
                content_text=None,
                content_json={
                    "tool_call_id": msg.tool_call_id,
                    "result": msg.content,
                },
                tool_name=getattr(msg, "name", None),
            )
            next_seq += 1

    # ── Update session timestamp and commit ────────────────────────────────────
    await db.execute(
        update(AgentSession)
        .where(AgentSession.id == session_id)
        .values(last_msg_at=func.now())
    )
    await db.commit()

    return final_reply


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_lc_messages(history: list[AgentMessage]) -> list[BaseMessage]:
    """
    Convert SQLite agent_messages rows to LangChain message objects.

    SQLite role → LangChain type:
      'user'      → HumanMessage(content=content_text)
      'assistant' without content_json → AIMessage(content=content_text)
      'assistant' with content_json    → AIMessage(content=..., tool_calls=[...])
      'tool'      → ToolMessage(content=result_json, tool_call_id=..., name=...)
    """
    messages: list[BaseMessage] = []

    for row in history:
        if row.role == "user":
            messages.append(HumanMessage(content=row.content_text or ""))

        elif row.role == "assistant":
            if row.content_json and isinstance(row.content_json, list):
                # Stored tool_calls list
                tool_calls = [
                    {"name": tc["name"], "id": tc["id"], "args": tc["args"]}
                    for tc in row.content_json
                    if "name" in tc and "id" in tc
                ]
                messages.append(AIMessage(
                    content=row.content_text or "",
                    tool_calls=tool_calls,
                ))
            else:
                messages.append(AIMessage(content=row.content_text or ""))

        elif row.role == "tool":
            cj = row.content_json or {}
            tool_call_id = cj.get("tool_call_id", "")
            result = cj.get("result", "")
            content = result if isinstance(result, str) else json.dumps(result, default=str)
            messages.append(ToolMessage(
                content=content,
                tool_call_id=tool_call_id,
                name=row.tool_name or "",
            ))

    return messages


async def _save_message(
    db: AsyncSession,
    session_id: int,
    seq: int,
    role: str,
    content_text: Optional[str],
    content_json: Optional[dict | list],
    tool_name: Optional[str],
) -> None:
    """Insert one AgentMessage row. Does NOT commit — caller commits."""
    msg = AgentMessage(
        session_id=session_id,
        sequence_num=seq,
        role=role,
        content_text=content_text,
        content_json=content_json,
        tool_name=tool_name,
    )
    db.add(msg)
    await db.flush()
```

- [ ] **Step 2: Verify runner.py imports correctly**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python3 -c "from app.agent.runner import run_turn, _build_lc_messages; print('runner.py imports OK')"
```

Expected: `runner.py imports OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/agent/runner.py
git commit -m "feat(phase6): rewrite runner.py — run_turn uses LangGraph supervisor + ChatGroq"
```

---

## Task 6: Verify Server Starts and Wire Check

**Files:**
- Verify: `nivesh-client/app/routers/agent.py` (already updated — just confirm)

- [ ] **Step 1: Confirm the chat endpoint already calls run_turn**

```bash
grep -n "run_turn\|run_in_background" /home/prasad/dev_home/projects/stock_platform/nivesh-client/app/routers/agent.py
```

Expected output contains a line like:
```
        reply = await run_turn(session_id, body.message, db)
```

If the line is NOT there (still has the Phase 4 stub), apply this fix:

Find in `app/routers/agent.py`:
```python
    await db.commit()

    # Phase 4 placeholder — Phase 6 wires the actual LLM
    return {
        "reply": "Agent not yet connected (Phase 6). Message stored successfully.",
        "session_id": session_id,
        "sequence_num": last_seq + 1,
    }
```

Replace with:
```python
    await db.commit()

    # ── Phase 6: call agent runner ─────────────────────────────────────────
    try:
        from ..agent.runner import run_turn
        reply = await run_turn(session_id, body.message, db)
    except Exception as exc:
        logger.error("Agent runner failed for session %d: %s", session_id, exc)
        reply = (
            "Sorry, I encountered an error processing your request. "
            "Check that GROQ_API_KEY is set in ~/.nivesh/.env"
        )

    return {
        "reply": reply,
        "session_id": session_id,
    }
```

- [ ] **Step 2: Start the server and verify it boots without import errors**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
uvicorn app.main:app --port 8001 --reload &
sleep 4
curl -s http://localhost:8001/health | python3 -m json.tool
pkill -f "uvicorn app.main"
```

Expected: JSON health response (status ok), no `ImportError` or `ModuleNotFoundError` in the uvicorn output.

- [ ] **Step 3: Commit agent.py if it was modified**

```bash
git add nivesh-client/app/routers/agent.py
git commit -m "feat(phase6): wire run_turn into /chat endpoint (replaces Phase 4 stub)" 2>/dev/null || echo "Already committed"
```

---

## Task 7: Add GROQ_API_KEY and Run Smoke Tests

- [ ] **Step 1: Add GROQ_API_KEY to ~/.nivesh/.env**

```bash
echo "GROQ_API_KEY=gsk_YOUR_KEY_HERE" >> ~/.nivesh/.env
```

Replace `gsk_YOUR_KEY_HERE` with the actual Groq API key from console.groq.com.

- [ ] **Step 2: Start the server**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
uvicorn app.main:app --port 8001 --reload &
sleep 4
```

- [ ] **Step 3: Smoke test — create session and send a stock query**

```bash
SESSION=$(curl -s -X POST http://localhost:8001/agent/sessions \
  -H "Content-Type: application/json" \
  -d '{"context_type": "general"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
echo "Session ID: $SESSION"

curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the current price and PE ratio for RELIANCE?"}' \
  | python3 -m json.tool
```

Expected: `"reply"` field contains actual Reliance Industries data (price, PE ratio) — not the stub message. The supervisor should route to `stock_agent`.

- [ ] **Step 4: Smoke test — fund comparison**

```bash
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Compare funds 119598 and 100644"}' \
  | python3 -m json.tool
```

Expected: reply mentions both funds by name, includes metrics and a recommendation. Supervisor routes to `fund_agent`.

- [ ] **Step 5: Smoke test — portfolio query**

```bash
# Add a test holding first
curl -s -X POST http://localhost:8001/local/portfolio/holdings \
  -H "Content-Type: application/json" \
  -d '{"symbol": "TCS", "asset_type": "STOCK", "quantity": 5, "avg_cost": 3800.0, "buy_date": "2025-01-15"}' \
  | python3 -m json.tool

# Ask the agent
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "How is my portfolio doing?"}' \
  | python3 -m json.tool
```

Expected: reply mentions TCS holdings. Supervisor routes to `portfolio_agent`.

- [ ] **Step 6: Smoke test — missing API key returns a clean error**

```bash
# Temporarily test with an invalid key
GROQ_API_KEY="" curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Test"}' \
  | python3 -m json.tool
```

Expected: reply contains "Groq API key is not configured" — no 500 error.

- [ ] **Step 7: Verify messages persisted in SQLite**

```bash
curl -s "http://localhost:8001/agent/sessions/$SESSION/messages" \
  | python3 -c "import sys,json; msgs=json.load(sys.stdin); print(f'Messages stored: {len(msgs)}')"
```

Expected: `Messages stored: N` where N > 6 (multiple user + assistant + tool messages across the smoke tests).

- [ ] **Step 8: Stop the server**

```bash
pkill -f "uvicorn app.main"
```

---

## Task 8: Update CLAUDE.md and Docs

**Files:**
- Modify: `CLAUDE.md` (repo root)
- Modify: `nivesh-client/CLAUDE.md`

- [ ] **Step 1: Update root CLAUDE.md phases table**

In `/home/prasad/dev_home/projects/stock_platform/CLAUDE.md`, find the P6 row:

```markdown
| P6 | Pending | Client: Agentic layer (LLM wiring) |
```

Replace with:

```markdown
| P6 | Done | Client: Agentic layer — LangGraph supervisor + 3 specialist ChatGroq agents (stock/fund/portfolio), 7 financial tools, memory injection |
```

- [ ] **Step 2: Update nivesh-client/CLAUDE.md — Anthropic SDK stack entry**

In `nivesh-client/CLAUDE.md`, find:

```markdown
- **Anthropic SDK** — LLM calls for agentic layer
```

Replace with:

```markdown
- **ChatGroq** (`langchain-groq`) — LLM calls via Groq inference (llama-3.3-70b-versatile)
- **LangGraph** — multi-agent supervisor graph (stock / fund / portfolio specialists)
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md nivesh-client/CLAUDE.md
git commit -m "docs(phase6): mark P6 complete, update stack to ChatGroq + LangGraph"
```

---

## Definition of Done

- [ ] `python3 -c "from app.agent.tools import STOCK_TOOLS, FUND_TOOLS, PORTFOLIO_TOOLS"` prints 7 tools
- [ ] `python3 -c "from app.agent.supervisor import build_graph"` imports without error
- [ ] `python3 -c "from app.agent.runner import run_turn"` imports without error
- [ ] Server starts without `ImportError` on any agent module
- [ ] `POST /agent/sessions/{id}/chat` with a stock query returns Groq-generated reply (not stub)
- [ ] Stock query routes to `stock_agent` (visible in server logs: `Supervisor → stock_agent`)
- [ ] Fund comparison query routes to `fund_agent`
- [ ] Portfolio query routes to `portfolio_agent`
- [ ] All new messages (AIMessage + ToolMessage) persisted to `agent_messages`
- [ ] Empty `GROQ_API_KEY` returns human-readable error, not a 500
- [ ] Root `CLAUDE.md` shows P6 as Done

---

*Phase 6 Implementation Plan · Nivesh Platform · 2026-05-16*
*Spec: docs/superpowers/specs/2026-05-16-phase6-groq-langgraph-design.md*
