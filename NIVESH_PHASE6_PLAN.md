# Nivesh Platform — Phase 6: Agentic Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Anthropic Claude API into the existing `/agent/sessions/{id}/chat` stub endpoint, implementing a tool-use loop with 7 financial data tools so the agent can answer questions about stocks, funds, portfolios, and Indian markets.

**Architecture:** The agent runner calls `anthropic.AsyncAnthropic` with a tool-use loop (up to 5 iterations). Tools fetch data from the local proxy routes via `httpx` (for server data) and directly from SQLite (for portfolio). Every turn — user messages, assistant responses, tool calls, tool results — is persisted to `agent_messages` in SQLite so conversation history survives restarts. Agent memory from `agent_memory` is injected into the system prompt for personalisation.

**Tech Stack:** `anthropic>=0.51.0` (async tool use), `httpx` (already installed), FastAPI + SQLAlchemy async (existing), React AgentChat.jsx (already built in Phase 5 — no frontend changes needed).

---

## Baseline — What Phase 4/5 Already Built

| Component | Status | Location |
|---|---|---|
| `agent_sessions`, `agent_messages`, `agent_memory` tables | ✅ Done | `app/models/agent.py` |
| All agent CRUD endpoints except `/chat` | ✅ Done | `app/routers/agent.py` |
| `/chat` endpoint | ⚠️ Stub | Returns "Agent not yet connected (Phase 6)" |
| `AgentChat.jsx` UI | ✅ Done | `frontend/src/pages/AgentChat.jsx` |
| `anthropic` SDK | ❌ Missing | Not in `requirements.txt` |
| `app/agent/` package | ❌ Missing | Directory does not exist |

**No database migrations needed** — all agent tables were created in Phase 4.
**No frontend changes needed** — `AgentChat.jsx` already handles tool-use replies correctly.

---

## File Structure

```
nivesh-client/
├── app/
│   ├── agent/                          ← CREATE (entire directory)
│   │   ├── __init__.py                 ← CREATE (empty)
│   │   ├── tools.py                    ← CREATE: TOOLS list + execute_tool()
│   │   ├── memory.py                   ← CREATE: load_memory_context()
│   │   └── runner.py                   ← CREATE: run_turn() main loop
│   ├── config.py                       ← MODIFY: add ANTHROPIC_API_KEY, AGENT_MODEL
│   └── routers/
│       └── agent.py                    ← MODIFY: replace stub in chat endpoint
├── requirements.txt                    ← MODIFY: add anthropic>=0.51.0
```

---

## Task 1: Add Anthropic Dependency and Config

**Files:**
- Modify: `nivesh-client/requirements.txt`
- Modify: `nivesh-client/app/config.py`

- [ ] **Step 1: Add anthropic to requirements.txt**

Open `nivesh-client/requirements.txt`. Add after `apscheduler==3.10.4`:

```text
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic-settings==2.2.1
sqlalchemy[asyncio]==2.0.30
aiosqlite==0.20.0
alembic==1.13.1
httpx==0.27.0
apscheduler==3.10.4
anthropic>=0.51.0
nivesh-shared @ ../nivesh-shared
```

- [ ] **Step 2: Add ANTHROPIC_API_KEY and AGENT_MODEL to config.py**

Open `nivesh-client/app/config.py`. Add two settings after the `CACHE_CLEANUP_INTERVAL_S` line:

```python
    # ── Agentic layer ─────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""         # Set in ~/.nivesh/.env
    AGENT_MODEL: str = "claude-sonnet-4-6"
```

The full `config.py` after the change:

```python
"""
Client configuration using Pydantic BaseSettings.

Reads from ~/.nivesh/.env file and environment variables.
All settings can be overridden via environment variables.
"""

from pathlib import Path
from pydantic_settings import BaseSettings

# Default DB path: ~/.nivesh/client.db
# Using user home keeps it outside the project dir
# so reinstalling the client doesn't wipe data
_DEFAULT_DB_PATH = Path.home() / ".nivesh" / "client.db"


class Settings(BaseSettings):
    # ── Server connection ──────────────────────────────────────────────────────
    NIVESH_SERVER_URL: str = "http://localhost:8000"
    # In production: https://nivesh-server.onrender.com

    # ── Client app ────────────────────────────────────────────────────────────
    CLIENT_PORT: int = 8001
    SQLITE_DB_PATH: str = str(_DEFAULT_DB_PATH)
    DEBUG: bool = False

    # ── Cache TTLs (seconds) ──────────────────────────────────────────────────
    CACHE_TTL_FUND_LIST: int = 3600
    CACHE_TTL_FUND_DETAIL: int = 3600
    CACHE_TTL_FUND_NAV: int = 86400
    CACHE_TTL_STOCK_DETAIL: int = 3600
    CACHE_TTL_STOCK_LIST: int = 3600
    CACHE_TTL_SCREENER: int = 900
    CACHE_TTL_BENCHMARKS: int = 3600
    CACHE_TTL_ETL_STATUS: int = 300

    # ── Scheduler ─────────────────────────────────────────────────────────────
    HEALTH_PING_INTERVAL_S: int = 60
    CACHE_CLEANUP_INTERVAL_S: int = 3600

    # ── Agentic layer ─────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""         # Set in ~/.nivesh/.env
    AGENT_MODEL: str = "claude-sonnet-4-6"

    class Config:
        env_file = str(Path.home() / ".nivesh" / ".env")
        extra = "ignore"


settings = Settings()
```

- [ ] **Step 3: Install the dependency**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
pip install anthropic
```

Expected output: `Successfully installed anthropic-x.x.x ...`

- [ ] **Step 4: Verify import works**

```bash
python -c "import anthropic; print(anthropic.__version__)"
```

Expected output: version string like `0.51.0` or higher.

- [ ] **Step 5: Commit**

```bash
git add nivesh-client/requirements.txt nivesh-client/app/config.py
git commit -m "feat(phase6): add anthropic SDK dependency and ANTHROPIC_API_KEY config"
```

---

## Task 2: Create Agent Package and tools.py

**Files:**
- Create: `nivesh-client/app/agent/__init__.py`
- Create: `nivesh-client/app/agent/tools.py`

- [ ] **Step 1: Create the package directory and empty `__init__.py`**

```bash
mkdir -p /home/prasad/dev_home/projects/stock_platform/nivesh-client/app/agent
touch /home/prasad/dev_home/projects/stock_platform/nivesh-client/app/agent/__init__.py
```

- [ ] **Step 2: Create `tools.py` with the TOOLS list**

Create `nivesh-client/app/agent/tools.py` with the following content:

```python
"""
Agent tools — financial data tool definitions and executor.

TOOLS: List of tool schemas for the Anthropic API (input_schema format).
execute_tool(): Dispatches each tool call to the appropriate local endpoint.

All server data goes through /proxy/* (which handles caching + JWT).
User data (portfolio) goes through /local/portfolio/* (SQLite-only).
"""

import json
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
```

- [ ] **Step 3: Verify the file parses correctly**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python -c "from app.agent.tools import TOOLS, execute_tool; print(f'Loaded {len(TOOLS)} tools')"
```

Expected output: `Loaded 7 tools`

- [ ] **Step 4: Commit**

```bash
git add nivesh-client/app/agent/
git commit -m "feat(phase6): agent package with 7 financial tools + executor"
```

---

## Task 3: Create memory.py

**Files:**
- Create: `nivesh-client/app/agent/memory.py`

- [ ] **Step 1: Create `memory.py`**

Create `nivesh-client/app/agent/memory.py`:

```python
"""
Agent memory — persistent facts across sessions.

load_memory_context(): Returns all stored facts as a formatted string
that is appended to the system prompt. This personalises the agent
to the user's known preferences, risk tolerance, and portfolio context.

save_memory_item(): Upserts a single fact (thin wrapper over the
existing PUT /agent/memory/{key} endpoint logic, for use by runner.py).
"""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agent import AgentMemory

logger = logging.getLogger(__name__)


async def load_memory_context(db: AsyncSession) -> str:
    """
    Returns all stored agent memory rows as a formatted block for injection
    into the system prompt.

    Returns empty string if no memories exist (new user — no personalisation).

    Example output:
        Known facts about the user:
        - risk_tolerance: conservative — prefers large-cap funds
        - preferred_sector: IT, Pharma
        - portfolio_size: medium — 10-20 holdings
    """
    result = await db.execute(
        select(AgentMemory).order_by(AgentMemory.updated_at.desc())
    )
    memories = result.scalars().all()

    if not memories:
        return ""

    lines = ["Known facts about the user:"]
    for m in memories:
        lines.append(f"- {m.key}: {m.value}")
    return "\n".join(lines)


async def save_memory_item(
    db: AsyncSession,
    key: str,
    value: str,
    confidence: str = "inferred",
    source: str = "agent_inferred",
) -> None:
    """
    Upsert a single memory fact.
    Called by runner.py when the LLM explicitly asks to remember something.
    """
    stmt = sqlite_insert(AgentMemory).values(
        key=key, value=value, confidence=confidence, source=source
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"],
        set_={"value": value, "confidence": confidence},
    )
    await db.execute(stmt)
    # Caller is responsible for commit
    logger.debug("Memory saved: %s = %s", key, value)
```

- [ ] **Step 2: Verify import**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python -c "from app.agent.memory import load_memory_context, save_memory_item; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/agent/memory.py
git commit -m "feat(phase6): agent memory context loader"
```

---

## Task 4: Create runner.py — Main Agent Loop

**Files:**
- Create: `nivesh-client/app/agent/runner.py`

This is the core of Phase 6. The `run_turn` function:
1. Loads conversation history from SQLite
2. Reconstructs the Anthropic messages list
3. Injects agent memory into the system prompt
4. Runs the tool-use loop (Claude → tools → Claude, up to 5 iterations)
5. Persists every step to SQLite
6. Returns the final reply text

- [ ] **Step 1: Create `runner.py`**

Create `nivesh-client/app/agent/runner.py`:

```python
"""
Agent runner — main LLM interaction loop.

run_turn(session_id, user_message, db):
    Assumes the user message has already been stored in agent_messages
    (done by the chat endpoint before calling this function).

    Loads full conversation history, calls Claude with the tool-use API,
    executes any tool calls, and stores all responses to agent_messages.

    Returns the final text reply string.
"""

import json
import logging
from typing import Optional

import anthropic
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from ..config import settings
from ..models.agent import AgentMessage, AgentSession
from .memory import load_memory_context
from .tools import TOOLS, execute_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5

SYSTEM_PROMPT = """\
You are Nivesh Agent, a personal financial research assistant for Indian equity \
markets (NSE/BSE).

You help users:
- Analyse individual stocks (price, fundamentals, technicals, composite rating)
- Research mutual funds (NAV, Sharpe/Sortino/Alpha/Beta, CAGR, comparisons)
- Review portfolio holdings and P&L
- Screen stocks using fundamental or technical criteria
- Understand market context (Nifty 50, Bank Nifty, sector performance)

Rules:
- Always call a tool to fetch data before making specific numerical claims
- Use ₹ for Indian currency amounts
- Reference stocks by NSE symbol (e.g. RELIANCE, TCS, INFY)
- If a response has _offline:true, note the data is from cache
- Be concise — users see a trading/research interface, not a blog post
- For fund comparisons, highlight the ranking and recommendation
- If the user asks you to remember something, do so by noting it clearly
"""


async def run_turn(session_id: int, user_message: str, db: AsyncSession) -> str:
    """
    Execute one conversational turn for the given session.

    Precondition: The user message has already been stored in agent_messages
    with the next available sequence_num (done by the /chat endpoint).

    Returns: final assistant reply text.
    """
    if not settings.ANTHROPIC_API_KEY:
        return (
            "Anthropic API key is not configured. "
            "Add ANTHROPIC_API_KEY=sk-ant-... to ~/.nivesh/.env and restart."
        )

    # ── Load full conversation history ─────────────────────────────────────────
    history_result = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.sequence_num.asc())
    )
    history = list(history_result.scalars().all())

    # next_seq: the next sequence number to assign to assistant/tool messages
    last_seq = max((m.sequence_num for m in history), default=0)
    next_seq = last_seq + 1

    # ── Reconstruct Anthropic messages list ────────────────────────────────────
    messages = _build_messages(history)

    # ── Build system prompt (base + agent memory) ──────────────────────────────
    memory_context = await load_memory_context(db)
    system = SYSTEM_PROMPT
    if memory_context:
        system = f"{SYSTEM_PROMPT}\n\n{memory_context}"

    # ── Tool-use loop ──────────────────────────────────────────────────────────
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    final_reply = "I encountered an error. Please try again."

    for iteration in range(MAX_TOOL_ITERATIONS):
        logger.debug(
            "Agent turn iteration %d/%d for session %d",
            iteration + 1, MAX_TOOL_ITERATIONS, session_id,
        )

        response = await client.messages.create(
            model=settings.AGENT_MODEL,
            max_tokens=2048,
            system=system,
            messages=messages,
            tools=TOOLS,
        )

        if response.stop_reason == "end_turn":
            # ── Final text response ─────────────────────────────────────────
            text_block = next(
                (b for b in response.content if b.type == "text"), None
            )
            final_reply = text_block.text if text_block else ""

            await _save_message(
                db, session_id, next_seq,
                role="assistant",
                content_text=final_reply,
                content_json=None,
                tool_name=None,
            )
            next_seq += 1
            break

        elif response.stop_reason == "tool_use":
            # ── Assistant message with tool_use blocks ──────────────────────
            content_blocks = [_block_to_dict(b) for b in response.content]
            text_parts = [
                b.text for b in response.content
                if b.type == "text" and b.text
            ]
            text_summary = " ".join(text_parts) if text_parts else None

            await _save_message(
                db, session_id, next_seq,
                role="assistant",
                content_text=text_summary,
                content_json=content_blocks,
                tool_name=None,
            )
            next_seq += 1

            # Append to messages for next API call
            messages.append({"role": "assistant", "content": content_blocks})

            # ── Execute each tool call ──────────────────────────────────────
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                logger.info("Tool call: %s(%s)", block.name, block.input)
                result = await execute_tool(block.name, block.input)

                result_str = json.dumps(result, default=str)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })

                # Persist each tool result separately
                await _save_message(
                    db, session_id, next_seq,
                    role="tool",
                    content_text=None,
                    content_json={"tool_use_id": block.id, "result": result},
                    tool_name=block.name,
                )
                next_seq += 1

            # Append tool results as user message for next iteration
            messages.append({"role": "user", "content": tool_results})

        else:
            # max_tokens or other stop reason — extract whatever text we have
            text_block = next(
                (b for b in response.content if b.type == "text"), None
            )
            final_reply = (
                text_block.text if text_block
                else "My response was cut off. Please ask again."
            )
            await _save_message(
                db, session_id, next_seq,
                role="assistant",
                content_text=final_reply,
                content_json=None,
                tool_name=None,
            )
            next_seq += 1
            break

    # ── Update session timestamp + commit ──────────────────────────────────────
    await db.execute(
        update(AgentSession)
        .where(AgentSession.id == session_id)
        .values(last_msg_at=func.now())
    )
    await db.commit()

    return final_reply


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_messages(history: list[AgentMessage]) -> list[dict]:
    """
    Reconstruct the Anthropic messages list from stored DB rows.

    Row role mapping → Anthropic format:
      'user'      → {"role": "user", "content": text}
      'assistant' with content_json  → {"role": "assistant", "content": [blocks]}
      'assistant' without content_json → {"role": "assistant", "content": text}
      'tool'      → consecutive tool rows merged into one
                    {"role": "user", "content": [tool_result, ...]}

    The last row in history is the current user message (already stored by
    the chat endpoint). It gets included here as the final user turn.
    """
    messages: list[dict] = []
    i = 0

    while i < len(history):
        row = history[i]

        if row.role == "user":
            messages.append({
                "role": "user",
                "content": row.content_text or "",
            })
            i += 1

        elif row.role == "assistant":
            if row.content_json:
                # Stored as list of content blocks (text + tool_use)
                messages.append({
                    "role": "assistant",
                    "content": row.content_json,
                })
            else:
                messages.append({
                    "role": "assistant",
                    "content": row.content_text or "",
                })
            i += 1

        elif row.role == "tool":
            # Merge consecutive tool result rows into one user message
            tool_results = []
            while i < len(history) and history[i].role == "tool":
                tr = history[i]
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tr.content_json.get("tool_use_id", ""),
                    "content": json.dumps(
                        tr.content_json.get("result", {}), default=str
                    ),
                })
                i += 1
            messages.append({"role": "user", "content": tool_results})

        else:
            # Skip 'state' rows or any future roles
            i += 1

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


def _block_to_dict(block) -> dict:
    """
    Convert an Anthropic SDK content block object to a plain dict
    suitable for JSON storage in SQLite and for passing back to the API.
    """
    if block.type == "text":
        return {"type": "text", "text": block.text}
    elif block.type == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,  # Already a dict
        }
    else:
        return {"type": block.type}
```

- [ ] **Step 2: Verify import**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
python -c "from app.agent.runner import run_turn; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/agent/runner.py
git commit -m "feat(phase6): agent runner with Anthropic tool-use loop (up to 5 iterations)"
```

---

## Task 5: Wire Runner into the Chat Endpoint

**Files:**
- Modify: `nivesh-client/app/routers/agent.py` (the `chat` function only)

The chat endpoint already stores the user message and commits. We replace the placeholder return with a call to `run_turn`.

- [ ] **Step 1: Update the chat endpoint in `agent.py`**

Find the `chat` function in `nivesh-client/app/routers/agent.py`. The function currently ends with:

```python
    # Phase 4 placeholder — Phase 6 wires the actual LLM
    return {
        "reply": "Agent not yet connected (Phase 6). Message stored successfully.",
        "session_id": session_id,
        "sequence_num": last_seq + 1,
    }
```

Replace those 4 lines AND add the import at the top of the file. The full updated `chat` function:

```python
@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: int,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Main chat endpoint.

    Stores the user message, then delegates to the agent runner
    which calls Claude with the tool-use loop and returns a reply.
    """
    # Verify session exists
    result = await db.execute(
        select(AgentSession).where(AgentSession.id == session_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(404, f"Session {session_id} not found")

    # Get next sequence number
    seq_result = await db.execute(
        select(AgentMessage.sequence_num)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.sequence_num.desc())
        .limit(1)
    )
    last_seq = seq_result.scalar_one_or_none() or 0

    # Store user message
    user_msg = AgentMessage(
        session_id=session_id,
        sequence_num=last_seq + 1,
        role="user",
        content_text=body.message,
    )
    db.add(user_msg)

    # Update session last_msg_at
    from sqlalchemy.sql import func
    await db.execute(
        update(AgentSession)
        .where(AgentSession.id == session_id)
        .values(last_msg_at=func.now())
    )
    await db.commit()

    # ── Phase 6: call agent runner ─────────────────────────────────────────
    try:
        from ..agent.runner import run_turn
        reply = await run_turn(session_id, body.message, db)
    except Exception as exc:
        logger.error("Agent runner failed for session %d: %s", session_id, exc)
        reply = (
            "Sorry, I encountered an error processing your request. "
            "Check that ANTHROPIC_API_KEY is set in ~/.nivesh/.env"
        )

    return {
        "reply": reply,
        "session_id": session_id,
    }
```

Note: The `from ..agent.runner import run_turn` import is inside the function body to avoid circular imports at module load time.

- [ ] **Step 2: Verify the server starts**

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
uvicorn app.main:app --port 8001 --reload &
sleep 3
curl -s http://localhost:8001/health | python -m json.tool
```

Expected: `{"status": "ok", "port": 8001}` (or similar health response).

Kill the background server: `pkill -f "uvicorn app.main"` after the check.

- [ ] **Step 3: Commit**

```bash
git add nivesh-client/app/routers/agent.py
git commit -m "feat(phase6): wire agent runner into /chat endpoint, replace Phase 4 stub"
```

---

## Task 6: Update CLAUDE.md and Manual Smoke Test

**Files:**
- Modify: `CLAUDE.md` (root)

- [ ] **Step 1: Update CLAUDE.md phases table**

In the root `CLAUDE.md`, find the Implementation Phases table row for P6 and update it:

```markdown
| P6 | Done | Client: Agentic layer — Anthropic tool-use loop, 7 financial tools, memory injection |
```

- [ ] **Step 2: Set API key for testing**

Add the Anthropic API key to `~/.nivesh/.env`:

```bash
echo "ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE" >> ~/.nivesh/.env
```

Replace `sk-ant-YOUR_KEY_HERE` with the actual key. Then restart the client:

```bash
cd /home/prasad/dev_home/projects/stock_platform/nivesh-client
uvicorn app.main:app --port 8001 --reload
```

- [ ] **Step 3: Run smoke test — stock query**

```bash
# Create a new session
SESSION=$(curl -s -X POST http://localhost:8001/agent/sessions \
  -H "Content-Type: application/json" \
  -d '{"context_type": "general"}' | python -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
echo "Session: $SESSION"

# Send a stock query
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the current price and rating for RELIANCE?"}' \
  | python -m json.tool
```

Expected: JSON with `"reply"` field containing a paragraph about Reliance Industries with actual numbers (not the stub message). The reply should reference price, RSI or P/E or some metric from the `get_stock_detail` tool.

- [ ] **Step 4: Run smoke test — fund comparison**

```bash
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Compare these two funds: 119598 and 100644"}' \
  | python -m json.tool
```

Expected: JSON with `"reply"` field mentioning both funds by name, with metrics and a recommendation.

- [ ] **Step 5: Run smoke test — portfolio query**

First add a test holding (if portfolio is empty):

```bash
curl -s -X POST http://localhost:8001/local/portfolio/holdings \
  -H "Content-Type: application/json" \
  -d '{"symbol": "RELIANCE", "asset_type": "STOCK", "quantity": 10, "avg_cost": 2500.00, "buy_date": "2025-01-01"}' \
  | python -m json.tool
```

Then ask the agent:

```bash
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "How is my portfolio doing?"}' \
  | python -m json.tool
```

Expected: `"reply"` should mention RELIANCE holding, the quantity (10 shares), and either current price data or a note that price data requires checking.

- [ ] **Step 6: Run smoke test — screener query**

```bash
curl -s -X POST "http://localhost:8001/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Find large-cap IT stocks with ROE above 20%"}' \
  | python -m json.tool
```

Expected: `"reply"` listing IT sector stocks that match the ROE criteria.

- [ ] **Step 7: Verify conversation history persists**

```bash
curl -s "http://localhost:8001/agent/sessions/$SESSION/messages" \
  | python -c "import sys,json; msgs=json.load(sys.stdin); print(f'Messages stored: {len(msgs)}')"
```

Expected: `Messages stored: N` where N > 8 (multiple user + assistant + tool messages).

- [ ] **Step 8: Test via the React UI**

With the client running on :8001 and the React dev server on :5173:

1. Open `http://localhost:5173`
2. Log in
3. Navigate to `/agent`
4. Type: `"Analyse INFY"`
5. Verify the reply contains actual Infosys stock data (not the stub message)
6. Type: `"Show me the market overview"`
7. Verify a response about Nifty/BankNifty levels

- [ ] **Step 9: Commit CLAUDE.md**

```bash
git add CLAUDE.md
git commit -m "docs(phase6): mark P6 complete in CLAUDE.md"
```

---

## Definition of Done

Phase 6 is complete when all of the following are true:

- [ ] `pip install anthropic` succeeds from `nivesh-client/requirements.txt`
- [ ] `ANTHROPIC_API_KEY` is read from `~/.nivesh/.env` via `settings.ANTHROPIC_API_KEY`
- [ ] `POST /agent/sessions/{id}/chat` returns an actual Claude-generated reply (not the Phase 4 stub)
- [ ] A stock query (e.g. "Analyse RELIANCE") causes the `get_stock_detail` tool to fire and returns data
- [ ] A fund comparison query causes `compare_funds` to fire and returns a recommendation
- [ ] A portfolio query causes `get_portfolio` to fire and returns holding data
- [ ] A screener query causes `screen_stocks` to fire and returns filtered results
- [ ] All conversation turns (user, assistant, tool results) are persisted in `agent_messages`
- [ ] The conversation history is used in subsequent turns (agent remembers what was discussed)
- [ ] The React `AgentChat.jsx` UI shows actual replies (not the stub message)
- [ ] If `ANTHROPIC_API_KEY` is empty, a clear human-readable error is returned (not a 500)

---

## Risk Notes

| Risk | Mitigation |
|---|---|
| Anthropic API key not set | `run_turn` checks for empty key before calling the API; returns a descriptive error |
| Tool call against offline server | `execute_tool` wraps all httpx calls; returns `{"error": "..."}` gracefully |
| Conversation history too long (token limit) | Tool-use loop limit of 5 iterations; Claude's context window handles ~100K tokens |
| `agent_messages.content_json` type mismatch | SQLite stores JSON, SQLAlchemy loads as dict/list — matches what Anthropic SDK expects |
| Model produces empty text block | `final_reply` defaults to empty string; UI shows blank bubble (acceptable for now) |

---

*Phase 6 Implementation Plan · Nivesh Platform · May 2026*
*Previous: Phase 5 — React UI Adaptation*
*Next: Phase 7 — Sync Engine + JWT Refresh*
