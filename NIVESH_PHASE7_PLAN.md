# Nivesh Platform — Phase 7: Agentic Layer
## Low-Level Implementation Plan · Anthropic API + LangGraph
### Version 1.0 · May 2026

---

## Table of Contents

1. [Phase 7 Goal & Scope](#1-phase-7-goal--scope)
2. [What Prior Phases Built — The Foundation](#2-what-prior-phases-built--the-foundation)
3. [Architecture: How the Agent Works End-to-End](#3-architecture-how-the-agent-works-end-to-end)
4. [Critical Design Decisions](#4-critical-design-decisions)
5. [File-by-File Change Map](#5-file-by-file-change-map)
6. [Task 7.1 — Anthropic Client Setup](#task-71--anthropic-client-setup)
7. [Task 7.2 — Tool Executor](#task-72--tool-executor)
8. [Task 7.3 — LangGraph Agent Graph](#task-73--langgraph-agent-graph)
9. [Task 7.4 — Memory Extraction Node](#task-74--memory-extraction-node)
10. [Task 7.5 — Wire Chat Endpoint](#task-75--wire-chat-endpoint)
11. [Task 7.6 — Streaming Response](#task-76--streaming-response)
12. [Task 7.7 — Context-Aware Agent Variants](#task-77--context-aware-agent-variants)
13. [Task 7.8 — System Prompt Engineering](#task-78--system-prompt-engineering)
14. [Task 7.9 — React: Wire Streaming to AgentChatPage](#task-79--react-wire-streaming-to-agentchatpage)
15. [Task 7.10 — Error Handling & Guardrails](#task-710--error-handling--guardrails)
16. [Task 7.11 — Smoke Tests](#task-711--smoke-tests)
17. [Data Flow: Full Request Trace](#17-data-flow-full-request-trace)
18. [Token Budget & Cost Estimates](#18-token-budget--cost-estimates)
19. [Dependency Changes](#19-dependency-changes)
20. [Environment Variables](#20-environment-variables)
21. [Definition of Done](#21-definition-of-done)
22. [Execution Order — Day by Day](#22-execution-order--day-by-day)

---

## 1. Phase 7 Goal & Scope

**Goal:** Wire the Anthropic API into the Phase 4/5 agent storage and
UI stub to produce a working conversational agent. The agent can analyse
stocks and mutual funds, compare funds, summarise the user's portfolio,
run screener queries, and extract facts into persistent memory — all
using data fetched through the local proxy (which caches server
responses and injects JWT).

**In scope:**
- Anthropic `claude-sonnet-4-6` as the LLM
- LangGraph graph with three nodes: `llm_node`, `tool_node`,
  `memory_node`
- Tool execution wired to the five `TOOL_REGISTRY` functions from
  Phase 4 (`fetch_fund`, `fetch_stock`, `compare_funds`,
  `get_portfolio_summary`, `screen_stocks`)
- Conversation history loaded from `agent_messages` SQLite table
- Memory context injected into system prompt from `agent_memory` table
- Streaming response via FastAPI `StreamingResponse` →
  React `EventSource`
- Context-aware agent variants: stock mode, fund mode, portfolio mode
- System prompt engineering specific to Indian markets and the data
  shapes your server returns
- Memory extraction: agent automatically stores facts it infers about
  the user into `agent_memory`
- Error guardrails: tool failure handling, max turns, cost limits
- React `AgentChatPage` updated for streaming display

**Out of scope for Phase 7:**
- LangGraph persistence (checkpointing to SQLite) — memory is handled
  through the existing `agent_messages` + `agent_memory` tables, which
  is sufficient for this use case
- Multi-user agent (single-user local app — no isolation needed)
- Voice input
- PDF report export (future phase)

**Key constraint from the codebase:**
`ScoringStateSchema` in `schemas.py` (lines 463–478) is a LangGraph
state dict with typed sub-keys (`pl_results`, `bs_results`,
`cf_results`, `statements_data`, `logs`). The existing fundamental
scoring pipeline already uses LangGraph on the server side. Phase 7
uses the same pattern on the client side, keeping the mental model
consistent throughout the codebase.

---

## 2. What Prior Phases Built — The Foundation

Phase 7 builds on exact deliverables from prior phases. Nothing is
re-invented.

### From Phase 4 (client storage + tool definitions)

| Deliverable | File | Phase 7 use |
|---|---|---|
| `AgentSession` model | `models/agent.py` | Load conversation context |
| `AgentMessage` model | `models/agent.py` | Read history, write new turns |
| `AgentMemory` model | `models/agent.py` | Inject into system prompt, write new facts |
| `TOOL_REGISTRY` dict | `services/agent_tools.py` | Call tools by name |
| `TOOL_DEFINITIONS` list | `services/agent_tools.py` | Pass to Anthropic `tools=` param |
| `POST /agent/sessions/{id}/chat` stub | `routers/agent.py` | Replace stub with real LLM call |
| `POST /agent/sessions/{id}/messages` | `routers/agent.py` | Store each turn |
| `GET /agent/memory` | `routers/agent.py` | Read stored memory |
| `PUT /agent/memory/{key}` | `routers/agent.py` | Write extracted memory |

### From Phase 5 (React UI stub)

| Deliverable | File | Phase 7 use |
|---|---|---|
| `AgentChatPage` | `src/pages/AgentChatPage.tsx` | Update for streaming |
| `agentApi.chat()` | `src/services/api.ts` | Replace with SSE fetch |
| Session creation + message list | `AgentChatPage.tsx` | Keep as-is |

### From the existing server codebase (`schemas.py`)

| Schema | How Phase 7 uses it |
|---|---|
| `FundMetricsRead` (all 22 metrics) | Tool result formatted into LLM context |
| `StockDetailResult` (technicals + fundamentals) | Tool result formatted into LLM context |
| `ComparisonResponse` with `ranking` + `group_scores` | Comparison tool result |
| `ScreenerResponse` with `filters_applied` | Screener tool result |
| `FundamentalScoreRead` (PL/BS/CF sub-scores) | Part of fund/stock context |
| `ScoringStateSchema` (`logs`, `statements_data`) | LangGraph state model reference |

---

## 3. Architecture: How the Agent Works End-to-End

```
React AgentChatPage
    │ POST /agent/sessions/{id}/chat  {"message": "Analyse RELIANCE"}
    │ (or SSE: GET /agent/sessions/{id}/stream)
    ▼
Client FastAPI :8001
    │
    ├── Load conversation history from agent_messages (SQLite)
    ├── Load memory context from agent_memory (SQLite)
    ├── Build system prompt (IST-aware, Indian market context)
    │
    ▼
LangGraph AgentGraph.run()
    │
    ┌─────────────────────────────────────────────────┐
    │                  AgentState                     │
    │  messages: list[dict]   (Anthropic format)      │
    │  tool_results: list     (accumulated)           │
    │  turn_count: int        (guardrail)             │
    │  memory_updates: list   (facts to persist)      │
    └─────────────────────────────────────────────────┘
    │
    ├── [llm_node]
    │     Call claude-sonnet-4-6 with tools=TOOL_DEFINITIONS
    │     If response.stop_reason == "tool_use" → route to tool_node
    │     If response.stop_reason == "end_turn"  → route to memory_node
    │
    ├── [tool_node]
    │     For each tool_use block in response:
    │       Call TOOL_REGISTRY[tool_name](**inputs)
    │       → fetch_stock("RELIANCE") → GET /proxy/stocks/RELIANCE
    │         → cache hit: return cached StockDetailResult
    │         → cache miss: GET server /api/stocks/RELIANCE → cache → return
    │       Append tool_result to messages
    │     Route back to llm_node
    │
    ├── [memory_node]  (only on final turn)
    │     Parse assistant reply for extractable facts
    │     Write to agent_memory via PUT /agent/memory/{key}
    │     Return final reply text
    │
    └── Final reply text
    │
    ├── Persist to agent_messages (SQLite): user msg + assistant msg + tool calls
    └── Stream to React (SSE) or return as JSON
```

---

## 4. Critical Design Decisions

### 4.1 Anthropic API over LangChain Anthropic wrapper

Use the `anthropic` Python SDK directly (`from anthropic import AsyncAnthropic`), not through LangChain. Reason: your existing `ScoringStateSchema` shows LangGraph is used directly in the server — Phase 7 keeps the same pattern. The Anthropic SDK's `tool_use` response format maps directly to `TOOL_DEFINITIONS` already written in Phase 4.

### 4.2 Conversation history format

Anthropic requires alternating `user`/`assistant` turns. The `agent_messages` table stores all roles including `tool` and `state`. Phase 7 reconstructs the Anthropic-compatible message list from the stored rows:

```
agent_messages rows          →    Anthropic messages list
─────────────────────────────────────────────────────────
role='user', content_text    →    {role: "user", content: text}
role='assistant', content    →    {role: "assistant", content: text or tool_use blocks}
role='tool', tool_name,      →    appended to user turn as tool_result
  content_json               →    {role: "user", content: [{type: "tool_result", ...}]}
```

The last `user` message is always the current user input. Tool results
are always attached to a `user` turn (Anthropic's protocol).

### 4.3 LangGraph with conditional edges, not a loop

```
START → llm_node → (tool_use?) → tool_node → llm_node
                 → (end_turn?) → memory_node → END
```

Max 8 turns enforced in state (`turn_count <= 8`). If the agent hasn't
produced a final answer by turn 8, the last assistant message is
returned with a note that the analysis was cut short.

### 4.4 Tool results as structured Markdown, not raw JSON

When the agent calls `fetch_stock("RELIANCE")`, the tool returns a
`StockDetailResult` dict. Before appending it to the message list as
a `tool_result`, it is formatted into Markdown with key metrics
highlighted. This dramatically improves the quality of the LLM's
analysis because the LLM can read the Markdown naturally without
parsing JSON mentally.

### 4.5 Memory is injected, not retrieved per-turn

At the start of each conversation turn, all `agent_memory` rows are
loaded once and injected into the system prompt. They are not retrieved
per-message. This keeps the architecture simple and the token count
predictable.

### 4.6 Streaming is optional, not required

Phase 7 implements both: a synchronous `POST /agent/sessions/{id}/chat`
(returns full reply when done) and a streaming `GET
/agent/sessions/{id}/stream?message=...` (Server-Sent Events). The
React `AgentChatPage` uses streaming when available. If the browser's
`EventSource` is blocked, it falls back to the synchronous endpoint.

---

## 5. File-by-File Change Map

```
nivesh-client/app/
├── agent/                            ← NEW directory
│   ├── __init__.py
│   ├── llm.py                        ← Anthropic client singleton
│   ├── state.py                      ← AgentState TypedDict for LangGraph
│   ├── nodes.py                      ← llm_node, tool_node, memory_node
│   ├── graph.py                      ← LangGraph graph assembly
│   ├── formatter.py                  ← Tool result → Markdown formatter
│   ├── memory.py                     ← Memory extraction from LLM reply
│   └── prompts.py                    ← System prompt builders
├── routers/
│   └── agent.py                      ← MODIFY: replace stub with real LLM call
│                                              add streaming endpoint
├── services/
│   └── agent_tools.py                ← MODIFY: add error handling per tool
├── config.py                         ← MODIFY: add ANTHROPIC_API_KEY, MAX_TURNS
└── schemas.py                        ← MODIFY: add StreamChunk schema

frontend/src/pages/
└── AgentChatPage.tsx                 ← MODIFY: wire SSE streaming
```

---

## Task 7.1 — Anthropic Client Setup

**File:** `app/agent/llm.py`
**Estimated time:** 30 minutes

```python
# app/agent/llm.py
"""
Anthropic client singleton.

Using AsyncAnthropic so it works inside FastAPI's async event loop.
Client is created once at import time and reused across all requests —
httpx connection pooling applies at this level.
"""
from anthropic import AsyncAnthropic
from ..config import settings

# Single instance — thread-safe for reads, one connection pool
anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

MODEL        = "claude-sonnet-4-6"
MAX_TOKENS   = 4096    # Per LLM call — enough for detailed stock/fund analysis
TEMPERATURE  = 1       # Anthropic default; do not set for tool_use workflows
```

### Update `app/config.py`

```python
# Add to Settings class in config.py:

ANTHROPIC_API_KEY: str = ""
# Set in ~/.nivesh/.env — never commit

AGENT_MAX_TURNS: int = 8
# Maximum tool-call rounds before returning partial answer

AGENT_MAX_HISTORY_MESSAGES: int = 20
# Load last N messages from agent_messages — avoids very long context windows

AGENT_ENABLE_MEMORY: bool = True
# If True, agent extracts facts into agent_memory after each final reply
```

---

## Task 7.2 — Tool Executor

**File:** `app/services/agent_tools.py` (modify existing)
**Estimated time:** 1 hour

The Phase 4 tools work but have no error handling. Phase 7 wraps each
tool with error handling and formats the result as Markdown. The
`TOOL_REGISTRY` and `TOOL_DEFINITIONS` are kept intact — only the
individual tool functions are updated.

```python
# app/services/agent_tools.py — replace individual tool functions

import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)
CLIENT_BASE = "http://localhost:8001"


async def _get(path: str, params: dict = None) -> dict:
    """Inner HTTP call — raises ToolError on failure."""
    async with httpx.AsyncClient(base_url=CLIENT_BASE, timeout=15) as c:
        resp = await c.get(path, params=params)
        if resp.status_code == 503:
            raise ToolError(f"Data unavailable (server offline): {path}")
        if resp.status_code == 404:
            raise ToolError(f"Not found: {path}")
        resp.raise_for_status()
        return resp.json()


class ToolError(Exception):
    """Raised when a tool call fails. Message is returned to the LLM as
    a tool_result error so it can acknowledge the failure gracefully."""
    pass


async def fetch_fund(scheme_code: str) -> str:
    """
    Fetch fund detail. Returns Markdown string for LLM consumption.
    The LLM gets readable text, not raw JSON.
    """
    try:
        data = await _get(f"/proxy/funds/{scheme_code}")
        return _format_fund(data)
    except ToolError as e:
        return f"Error fetching fund {scheme_code}: {e}"
    except Exception as e:
        logger.warning(f"fetch_fund failed for {scheme_code}: {e}")
        return f"Could not retrieve fund data for scheme code {scheme_code}."


async def fetch_stock(symbol: str) -> str:
    """Fetch stock detail. Returns Markdown string for LLM consumption."""
    symbol = symbol.upper().strip()
    try:
        data = await _get(f"/proxy/stocks/{symbol}")
        return _format_stock(data)
    except ToolError as e:
        return f"Error fetching stock {symbol}: {e}"
    except Exception as e:
        logger.warning(f"fetch_stock failed for {symbol}: {e}")
        return f"Could not retrieve stock data for {symbol}."


async def compare_funds(scheme_codes: list) -> str:
    """Compare up to 5 funds. Returns Markdown comparison table."""
    codes = scheme_codes[:5]
    try:
        data = await _get("/proxy/funds/compare",
                          params={"scheme_codes": ",".join(str(c) for c in codes)})
        return _format_comparison(data)
    except ToolError as e:
        return f"Error comparing funds: {e}"
    except Exception as e:
        logger.warning(f"compare_funds failed: {e}")
        return "Could not retrieve fund comparison data."


async def get_portfolio_summary() -> str:
    """Fetch local holdings and enrich with current prices."""
    try:
        holdings_data = await _get("/local/portfolio/holdings")
        if not holdings_data:
            return "The portfolio is empty — no holdings recorded."

        lines = ["## Portfolio Summary\n",
                 f"Total holdings: {len(holdings_data)}\n"]
        total_invested = 0.0

        for h in holdings_data:
            invested = h["avg_cost"] * h["quantity"]
            total_invested += invested
            current_price = None

            # Enrich with current price
            try:
                if h["asset_type"] == "STOCK":
                    detail = await _get(f"/proxy/stocks/{h['symbol']}")
                    current_price = detail.get("latest_close")
                elif h["asset_type"] == "FUND":
                    detail = await _get(f"/proxy/funds/{h['symbol']}")
                    current_price = (detail.get("metrics") or {}).get("current_nav")
            except Exception:
                pass

            if current_price:
                current_val = current_price * h["quantity"]
                pnl = current_val - invested
                pnl_pct = (pnl / invested * 100) if invested else 0
                pnl_str = f"₹{pnl:+,.0f} ({pnl_pct:+.1f}%)"
            else:
                current_val = invested
                pnl_str = "price unavailable"

            lines.append(
                f"- **{h['symbol']}** ({h['asset_type']}): "
                f"{h['quantity']} units @ ₹{h['avg_cost']:.2f} | "
                f"Invested: ₹{invested:,.0f} | P&L: {pnl_str}"
            )

        lines.append(f"\n**Total Invested:** ₹{total_invested:,.0f}")
        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"get_portfolio_summary failed: {e}")
        return "Could not retrieve portfolio data."


async def screen_stocks(filters: dict) -> str:
    """Run stock screener. Returns Markdown table of top results."""
    try:
        # Limit results to top 10 for LLM context efficiency
        params = {**filters, "limit": 10, "page": 1}
        data = await _get("/proxy/stocks/screener", params=params)
        return _format_screener(data, filters)
    except ToolError as e:
        return f"Screener error: {e}"
    except Exception as e:
        logger.warning(f"screen_stocks failed: {e}")
        return "Could not run stock screener."


# ── Tool registry (unchanged from Phase 4) ───────────────────────────────────
TOOL_REGISTRY = {
    "fetch_fund":            fetch_fund,
    "fetch_stock":           fetch_stock,
    "compare_funds":         compare_funds,
    "get_portfolio_summary": get_portfolio_summary,
    "screen_stocks":         screen_stocks,
}

# TOOL_DEFINITIONS unchanged from Phase 4 — already correct Anthropic format
```

---

## Task 7.3 — LangGraph Agent Graph

**Files:** `app/agent/state.py`, `app/agent/nodes.py`, `app/agent/graph.py`
**Estimated time:** 3 hours

### `app/agent/state.py`

```python
# app/agent/state.py
from typing import TypedDict, Annotated, List, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    LangGraph state for the Nivesh agent.

    messages: Anthropic-format message list.
      add_messages reducer appends new messages rather than replacing.
    turn_count: Incremented each time llm_node runs.
      Guardrail: graph ends when turn_count >= MAX_TURNS.
    memory_updates: Facts extracted during this conversation.
      Persisted to agent_memory table after final turn.
    final_reply: Set by memory_node. The text returned to React.
    error: Set if an unrecoverable error occurs.
    """
    messages:        Annotated[List[dict], add_messages]
    turn_count:      int
    memory_updates:  List[dict]   # [{key, value, confidence}]
    final_reply:     Optional[str]
    error:           Optional[str]
```

### `app/agent/nodes.py`

```python
# app/agent/nodes.py
import json
import logging
from typing import Literal
from .llm import anthropic_client, MODEL, MAX_TOKENS
from .prompts import build_system_prompt
from .formatter import format_tool_result
from .memory import extract_memory_updates
from ..services.agent_tools import TOOL_REGISTRY, TOOL_DEFINITIONS
from ..config import settings

logger = logging.getLogger(__name__)


# ── LLM Node ─────────────────────────────────────────────────────────────────

async def llm_node(state: dict) -> dict:
    """
    Call claude-sonnet-4-6 with the full message history and tool definitions.

    Returns dict with:
    - messages: [new assistant message appended]
    - turn_count: incremented by 1

    The system prompt is rebuilt on every call — it includes the current
    time (IST) which changes, so it must be fresh.
    """
    from .prompts import build_system_prompt
    import asyncio

    system_prompt = build_system_prompt(state.get("_memory_context", ""))

    # Guard: enforce max turns
    if state["turn_count"] >= settings.AGENT_MAX_TURNS:
        cutoff_msg = {
            "role": "assistant",
            "content": (
                "I've reached the maximum number of analysis steps for this query. "
                "Based on what I've gathered so far, here is a summary: "
                + (state.get("final_reply") or "Please try a more specific question.")
            ),
        }
        return {
            "messages": [cutoff_msg],
            "turn_count": state["turn_count"] + 1,
            "final_reply": cutoff_msg["content"],
        }

    response = await anthropic_client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        tools=TOOL_DEFINITIONS,
        messages=state["messages"],
    )

    # Convert Anthropic response to a message dict for the state
    # response.content is a list of TextBlock | ToolUseBlock
    assistant_message = {
        "role": "assistant",
        "content": response.content,   # Keep as list of blocks — tool_node reads it
    }

    return {
        "messages": [assistant_message],
        "turn_count": state["turn_count"] + 1,
    }


# ── Route function ────────────────────────────────────────────────────────────

def should_continue(state: dict) -> Literal["tool_node", "memory_node"]:
    """
    Conditional edge from llm_node.
    If the last assistant message has tool_use blocks → tool_node.
    If stop_reason is end_turn → memory_node.
    """
    last_msg = state["messages"][-1]
    content = last_msg.get("content", [])

    # content is a list of blocks from the Anthropic SDK
    has_tool_use = any(
        getattr(block, "type", None) == "tool_use"
        for block in content
        if hasattr(block, "type")
    )
    return "tool_node" if has_tool_use else "memory_node"


# ── Tool Node ─────────────────────────────────────────────────────────────────

async def tool_node(state: dict) -> dict:
    """
    Execute all tool_use blocks from the last assistant message.
    Returns a user-role message containing tool_result blocks.

    Anthropic protocol: tool results must come back in a 'user' turn
    as content blocks of type 'tool_result'.
    """
    last_msg = state["messages"][-1]
    content_blocks = last_msg.get("content", [])

    tool_result_blocks = []

    for block in content_blocks:
        if not hasattr(block, "type") or block.type != "tool_use":
            continue

        tool_name  = block.name
        tool_input = block.input
        tool_id    = block.id

        logger.info(f"[tool_node] calling {tool_name} with {tool_input}")

        try:
            tool_fn = TOOL_REGISTRY.get(tool_name)
            if not tool_fn:
                result_text = f"Unknown tool: {tool_name}"
            else:
                # Call the tool — returns Markdown string
                if tool_name == "get_portfolio_summary":
                    # No args
                    result_text = await tool_fn()
                elif tool_name == "compare_funds":
                    result_text = await tool_fn(tool_input.get("scheme_codes", []))
                elif tool_name == "screen_stocks":
                    result_text = await tool_fn(tool_input.get("filters", {}))
                else:
                    # fetch_fund(scheme_code=) or fetch_stock(symbol=)
                    result_text = await tool_fn(**tool_input)

        except Exception as e:
            logger.warning(f"[tool_node] {tool_name} failed: {e}")
            result_text = f"Tool {tool_name} encountered an error: {str(e)}"

        tool_result_blocks.append({
            "type":        "tool_result",
            "tool_use_id": tool_id,
            "content":     result_text,
        })

    # Tool results go back as a 'user' message (Anthropic protocol)
    tool_result_message = {
        "role":    "user",
        "content": tool_result_blocks,
    }

    return {"messages": [tool_result_message]}


# ── Memory Node ───────────────────────────────────────────────────────────────

async def memory_node(state: dict) -> dict:
    """
    Final node — runs after the agent produces its answer.

    1. Extracts the text reply from the last assistant message.
    2. Calls extract_memory_updates() to find new facts.
    3. Populates state['memory_updates'] for the router to persist.
    4. Sets state['final_reply'].
    """
    last_msg = state["messages"][-1]
    content  = last_msg.get("content", [])

    # Extract plain text from the response content
    if isinstance(content, list):
        final_text = " ".join(
            getattr(block, "text", "")
            for block in content
            if getattr(block, "type", None) == "text"
        )
    else:
        final_text = str(content)

    # Memory extraction — lightweight, non-blocking
    memory_updates = []
    if settings.AGENT_ENABLE_MEMORY and final_text:
        memory_updates = await extract_memory_updates(final_text, state["messages"])

    return {
        "final_reply":    final_text,
        "memory_updates": memory_updates,
    }
```

### `app/agent/graph.py`

```python
# app/agent/graph.py
"""
Assemble the LangGraph agent graph.

Graph structure:
    START → llm_node → (tool_use?) → tool_node → llm_node (loop)
                     → (end_turn?) → memory_node → END
"""
from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .nodes import llm_node, tool_node, memory_node, should_continue


def build_agent_graph():
    """
    Build and compile the agent graph.
    Called once at module import — compiled graph is reused per request.
    """
    graph = StateGraph(AgentState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    graph.add_node("llm_node",    llm_node)
    graph.add_node("tool_node",   tool_node)
    graph.add_node("memory_node", memory_node)

    # ── Edges ─────────────────────────────────────────────────────────────────
    graph.add_edge(START, "llm_node")

    # Conditional: after llm_node, either call tools or finish
    graph.add_conditional_edges(
        "llm_node",
        should_continue,
        {
            "tool_node":   "tool_node",
            "memory_node": "memory_node",
        },
    )

    # After tool_node, always return to llm_node for another LLM turn
    graph.add_edge("tool_node", "llm_node")

    # memory_node is always the final step
    graph.add_edge("memory_node", END)

    return graph.compile()


# Compiled graph — singleton, reused for all conversations
agent_graph = build_agent_graph()
```

---

## Task 7.4 — Memory Extraction Node

**File:** `app/agent/memory.py`
**Estimated time:** 1 hour

```python
# app/agent/memory.py
"""
Extracts persistent facts from the agent's final reply.

Strategy: lightweight rule-based extraction — no extra LLM call.
Looks for specific patterns in the agent's text and the user's
messages that indicate a persistent fact worth storing.

Examples of facts extracted:
  User: "I only invest in direct plans"
    → key="plan_type_preference", value="Direct plans only"
  User: "My risk tolerance is moderate"
    → key="risk_tolerance", value="moderate"
  Agent detects user has large IT holdings:
    → key="dominant_sector", value="IT"

This is intentionally simple — does not call the LLM again.
A full semantic extraction LLM call would double costs per turn.
"""
import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Patterns: (regex to match in user messages, key, value_extractor)
_USER_PATTERNS = [
    # Risk tolerance
    (r"risk[- ]tolerance[:\s]+(\w+)", "risk_tolerance"),
    (r"(conservative|moderate|aggressive)\s+investor", "risk_profile"),
    # Plan type
    (r"(direct|regular)\s+plan", "plan_type_preference"),
    # Investment horizon
    (r"invest\s+for\s+(\d+)\s+year", "investment_horizon_years"),
    # Preferred sector
    (r"prefer\s+(it|banking|pharma|auto|fmcg|metal)\s+sector", "preferred_sector"),
]


async def extract_memory_updates(
    final_reply: str,
    messages: List[dict],
) -> List[Dict]:
    """
    Scan the conversation messages and final reply for extractable facts.

    Returns list of {key, value, confidence} dicts.
    The caller writes these to agent_memory via PUT /agent/memory/{key}.
    """
    updates = []

    # Scan user messages for explicit statements
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue
        text = content.lower()

        for pattern, key in _USER_PATTERNS:
            m = re.search(pattern, text)
            if m:
                value = m.group(1) if m.lastindex else m.group(0)
                updates.append({
                    "key":        key,
                    "value":      value.strip(),
                    "confidence": "high",
                    "source":     "user_stated",
                })

    # Scan final reply for inferred facts
    reply_lower = final_reply.lower()

    if "direct plan" in reply_lower and "recommend" in reply_lower:
        updates.append({
            "key":        "recommended_plan_type",
            "value":      "Direct",
            "confidence": "medium",
            "source":     "inferred",
        })

    # Deduplicate by key — last one wins
    seen = {}
    for u in updates:
        seen[u["key"]] = u
    return list(seen.values())
```

---

## Task 7.5 — Wire Chat Endpoint

**File:** `app/routers/agent.py` (modify Phase 4 stub)
**Estimated time:** 2 hours

Replace the Phase 4 stub in `POST /agent/sessions/{id}/chat` with the
real LangGraph call. Keep all other endpoints unchanged.

```python
# app/routers/agent.py — replace the chat() function only

from ..agent.graph import agent_graph
from ..agent.prompts import build_system_prompt
from ..config import settings
from sqlalchemy import select
import json

@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: int,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Main chat endpoint. Runs the LangGraph agent and returns the reply.

    Steps:
      1. Load conversation history from agent_messages
      2. Load memory from agent_memory
      3. Build initial LangGraph state
      4. Run agent_graph.ainvoke()
      5. Persist new messages to agent_messages
      6. Persist memory_updates to agent_memory
      7. Return final_reply
    """

    # ── 1. Load history ───────────────────────────────────────────────────────
    history_rows = await _load_history(db, session_id)
    anthropic_messages = _to_anthropic_format(history_rows)

    # Append current user message
    anthropic_messages.append({"role": "user", "content": body.message})

    # ── 2. Load memory ────────────────────────────────────────────────────────
    memory_context = await _load_memory_context(db)

    # ── 3. Build initial state ────────────────────────────────────────────────
    initial_state = {
        "messages":       anthropic_messages,
        "turn_count":     0,
        "memory_updates": [],
        "final_reply":    None,
        "error":          None,
        "_memory_context": memory_context,  # Private — not part of AgentState schema
    }

    # ── 4. Run LangGraph agent ────────────────────────────────────────────────
    try:
        final_state = await agent_graph.ainvoke(initial_state)
    except Exception as e:
        logger.exception(f"Agent graph failed for session {session_id}")
        final_reply = "I encountered an error while processing your request. Please try again."
        final_state = {"final_reply": final_reply, "memory_updates": []}

    reply_text = final_state.get("final_reply") or "I couldn't generate a response."

    # ── 5. Persist messages ───────────────────────────────────────────────────
    # Get current sequence number
    seq_res = await db.execute(
        select(AgentMessage.sequence_num)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.sequence_num.desc())
        .limit(1)
    )
    last_seq = seq_res.scalar_one_or_none() or 0

    # User message
    db.add(AgentMessage(
        session_id=session_id, sequence_num=last_seq + 1,
        role="user", content_text=body.message,
    ))

    # Tool call messages (from agent state — the turns between user and assistant)
    # Scan final_state["messages"] for new turns beyond history_rows length
    new_turns = final_state.get("messages", [])[len(anthropic_messages) - 1:]
    seq = last_seq + 2
    for turn in new_turns:
        role = turn.get("role", "")
        content = turn.get("content", "")

        if role == "assistant":
            # Extract text blocks
            if isinstance(content, list):
                text = " ".join(
                    getattr(b, "text", "") for b in content
                    if getattr(b, "type", None) == "text"
                )
                # Tool use blocks — log separately
                for b in content:
                    if getattr(b, "type", None) == "tool_use":
                        db.add(AgentMessage(
                            session_id=session_id, sequence_num=seq,
                            role="tool",
                            tool_name=b.name,
                            content_json=b.input,
                            content_text=f"Called {b.name}",
                        ))
                        seq += 1
            else:
                text = str(content)

            db.add(AgentMessage(
                session_id=session_id, sequence_num=seq,
                role="assistant", content_text=text,
            ))
            seq += 1

    await db.commit()

    # ── 6. Persist memory updates ──────────────────────────────────────────────
    for update in final_state.get("memory_updates", []):
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        stmt = sqlite_insert(AgentMemory).values(
            key=update["key"],
            value=update["value"],
            confidence=update.get("confidence", "medium"),
            source=update.get("source", "inferred"),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={"value": update["value"], "confidence": update.get("confidence", "medium")},
        )
        await db.execute(stmt)
    await db.commit()

    return {"reply": reply_text, "session_id": session_id}


# ── Helper functions ───────────────────────────────────────────────────────────

async def _load_history(db: AsyncSession, session_id: int) -> list:
    """Load the last N messages for a session."""
    result = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.sequence_num.asc())
        .limit(settings.AGENT_MAX_HISTORY_MESSAGES)
    )
    return result.scalars().all()


def _to_anthropic_format(rows: list) -> list:
    """
    Convert agent_messages rows to Anthropic message list format.

    Anthropic requires strictly alternating user/assistant turns.
    Tool results (role='tool') are appended to the preceding user turn
    as tool_result content blocks.
    """
    messages = []
    pending_tool_results = []

    for row in rows:
        if row.role == "user":
            if pending_tool_results:
                # Flush pending tool results into the last user turn
                if messages and messages[-1]["role"] == "user":
                    messages[-1]["content"] = (
                        [messages[-1]["content"]] if isinstance(messages[-1]["content"], str)
                        else messages[-1]["content"]
                    ) + pending_tool_results
                pending_tool_results = []
            messages.append({"role": "user", "content": row.content_text or ""})

        elif row.role == "assistant":
            messages.append({
                "role":    "assistant",
                "content": row.content_text or "",
            })

        elif row.role == "tool":
            # Tool results attach to user turn that follows the tool call
            pending_tool_results.append({
                "type":    "tool_result",
                "content": json.dumps(row.content_json) if row.content_json else "",
            })

    # Flush any remaining tool results
    if pending_tool_results and messages and messages[-1]["role"] == "user":
        messages[-1]["content"] = pending_tool_results

    return messages


async def _load_memory_context(db: AsyncSession) -> str:
    """Format all agent_memory rows as a context string for the system prompt."""
    result = await db.execute(select(AgentMemory))
    rows = result.scalars().all()
    if not rows:
        return ""
    lines = [f"- {r.key}: {r.value} (confidence: {r.confidence})" for r in rows]
    return "Known facts about this user:\n" + "\n".join(lines)
```

---

## Task 7.6 — Streaming Response

**File:** `app/routers/agent.py` (add streaming endpoint)
**Estimated time:** 1.5 hours

```python
# app/routers/agent.py — add streaming endpoint

from fastapi import Request
from fastapi.responses import StreamingResponse
import asyncio

@router.get("/sessions/{session_id}/stream")
async def chat_stream(
    session_id: int,
    message: str,            # Query param: ?message=Analyse+RELIANCE
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Streaming chat via Server-Sent Events (SSE).

    React connects with EventSource:
      const source = new EventSource(
        `/agent/sessions/${sessionId}/stream?message=${encodeURIComponent(msg)}`
      );
      source.onmessage = e => appendChunk(e.data);
      source.addEventListener("done", () => source.close());
      source.addEventListener("error", e => handleError(e));

    Events sent:
      data: <text chunk>      ← partial reply text
      event: done             ← final event, closes the stream
      event: error            ← error event with data: error message
    """

    async def event_generator():
        history_rows     = await _load_history(db, session_id)
        anthropic_messages = _to_anthropic_format(history_rows)
        anthropic_messages.append({"role": "user", "content": message})
        memory_context   = await _load_memory_context(db)

        # Stream directly from Anthropic SDK
        try:
            async with anthropic_client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=build_system_prompt(memory_context),
                tools=TOOL_DEFINITIONS,
                messages=anthropic_messages,
            ) as stream:
                full_text = ""
                async for text_chunk in stream.text_stream:
                    full_text += text_chunk
                    # SSE format: "data: <chunk>\n\n"
                    yield f"data: {text_chunk}\n\n"
                    await asyncio.sleep(0)   # Yield to event loop

                # After streaming completes, get the final message for tool handling
                final_message = await stream.get_final_message()

                # If the model wants to use tools, handle that outside the stream
                # For simplicity in Phase 7: tool calls use the non-streaming endpoint.
                # Full streaming with tool calls is a Phase 8 enhancement.
                if final_message.stop_reason == "tool_use":
                    yield "data: [Processing data...]\n\n"
                    # Fall back to non-streaming for tool-use turns
                    result = await chat(
                        session_id, ChatRequest(message=message), db
                    )
                    remaining = result["reply"].replace(full_text, "")
                    if remaining:
                        yield f"data: {remaining}\n\n"

                yield "event: done\ndata: \n\n"

        except Exception as e:
            logger.exception("Streaming failed")
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable Nginx buffering if behind proxy
        },
    )
```

---

## Task 7.7 — Context-Aware Agent Variants

**File:** `app/agent/prompts.py`
**Estimated time:** 1 hour

The agent behaves differently depending on what the user is looking at.
A session created with `context_type="stock"` and `context_id="RELIANCE"`
automatically pre-loads RELIANCE data and tells the LLM what context
it's working in.

```python
# app/agent/prompts.py
"""
System prompt builders for the Nivesh agent.

The system prompt is the most important leverage point for agent quality.
It tells the LLM:
  1. Who it is and what it can do
  2. What data it has access to (the tool descriptions are in TOOL_DEFINITIONS)
  3. How to format its responses (Markdown, INR formatting, IST dates)
  4. What the user's context is (stock mode / fund mode / portfolio mode)
  5. What facts it already knows about the user (from agent_memory)
"""
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")


def _now_ist() -> str:
    return datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")


BASE_SYSTEM = """You are Nivesh Agent, a financial analysis assistant specialised in \
Indian equity markets and mutual funds. You have access to real-time data for NSE-listed \
stocks and AMFI-registered mutual funds.

Current time: {now_ist}

## Your capabilities
- Analyse individual stocks: price, technical indicators, fundamental ratios, ratings
- Analyse mutual funds: NAV, performance metrics (Sharpe, Sortino, Alpha, Beta), \
  comparisons
- Compare up to 5 mutual funds side by side
- Summarise the user's local portfolio with current P&L
- Screen stocks using financial filters (PE, ROE, RSI, etc.)

## Response guidelines
- Always use Indian number formatting (lakhs and crores, not millions)
- All amounts in INR (₹)
- When giving returns, always specify the time period
- When comparing funds, mention the benchmark category
- Be concise but complete — the user is a sophisticated investor
- If data is unavailable or stale (marked _offline), say so clearly
- Never make buy/sell recommendations — present data and analysis only
- Format responses in Markdown with clear headings

## Data freshness
Price data refreshes daily after NSE closes (~18:30 IST).
NAV data refreshes daily after AMFI publishes (~21:00 IST).
Fundamental data refreshes weekly (Screener.in scrape, Sunday).
If data seems outdated, the user can trigger a manual sync.
"""

STOCK_CONTEXT = """
## Current context
You are in stock analysis mode for **{symbol}**.
The user is viewing the detail page for this stock.
When they ask a question without specifying a stock, assume they mean {symbol}.
Start by fetching {symbol} data if you haven't already.
"""

FUND_CONTEXT = """
## Current context
You are in fund analysis mode for scheme code **{scheme_code}**.
The user is viewing the detail page for this fund.
When they ask a question without specifying a fund, assume they mean {scheme_code}.
Start by fetching fund {scheme_code} data if you haven't already.
"""

PORTFOLIO_CONTEXT = """
## Current context
You are in portfolio analysis mode.
The user is reviewing their personal portfolio.
When they ask a general question, assume it's about their portfolio.
Start by calling get_portfolio_summary if you haven't already.
"""


def build_system_prompt(
    memory_context: str = "",
    context_type: str = "general",
    context_id: str = None,
) -> str:
    """
    Build the full system prompt for a conversation turn.

    Args:
        memory_context: formatted string from _load_memory_context()
        context_type: 'stock' | 'fund' | 'portfolio' | 'general'
        context_id: NSE symbol (stock) or scheme_code (fund)
    """
    prompt = BASE_SYSTEM.format(now_ist=_now_ist())

    if context_type == "stock" and context_id:
        prompt += STOCK_CONTEXT.format(symbol=context_id.upper())
    elif context_type == "fund" and context_id:
        prompt += FUND_CONTEXT.format(scheme_code=context_id)
    elif context_type == "portfolio":
        prompt += PORTFOLIO_CONTEXT

    if memory_context:
        prompt += f"\n\n## User preferences (from memory)\n{memory_context}"

    return prompt
```

---

## Task 7.8 — Tool Result Formatter

**File:** `app/agent/formatter.py`
**Estimated time:** 1.5 hours

This is the function that converts raw API response dicts into readable
Markdown. The quality of the agent's analysis depends heavily on this —
the LLM reads Markdown far better than raw JSON.

```python
# app/agent/formatter.py
"""
Format tool results (API response dicts) as Markdown for LLM consumption.

Each formatter takes the raw API response shape (matching the server's
Pydantic schema) and returns a Markdown string. The LLM can read and
reason about Markdown naturally without JSON parsing overhead.
"""
from typing import Optional


def _fmt_pct(v: Optional[float], suffix="%") -> str:
    if v is None: return "N/A"
    return f"{v:+.2f}{suffix}"

def _fmt_num(v: Optional[float], prefix="₹", decimals=2) -> str:
    if v is None: return "N/A"
    return f"{prefix}{v:,.{decimals}f}"

def _fmt_score(v: Optional[float]) -> str:
    if v is None: return "N/A"
    return f"{v:.1f}/10"

def _rating_emoji(label: Optional[str]) -> str:
    m = {
        "Strong Buy": "🟢", "Buy": "🟩", "Neutral": "🟡",
        "Sell": "🟥", "Strong Sell": "🔴",
    }
    return m.get(label, "⬜")


def _format_fund(data: dict) -> str:
    """Format FundMasterRead → Markdown."""
    m = data.get("metrics") or {}
    name = data.get("scheme_name", "Unknown Fund")
    lines = [
        f"## {name}",
        f"**Scheme Code:** {data.get('scheme_code')} | "
        f"**AMC:** {data.get('amc_name')} | "
        f"**Plan:** {data.get('plan_type')} | "
        f"**Category:** {data.get('scheme_category')}",
        "",
        "### Current Snapshot",
        f"- **NAV:** ₹{m.get('current_nav', 'N/A')} (as of {m.get('nav_date', 'N/A')})",
        f"- **AUM:** ₹{m.get('aum_in_crores', 'N/A')} Cr | "
        f"**Expense Ratio:** {m.get('expense_ratio', 'N/A')}%",
        "",
        "### Returns",
        f"| Period | Return |",
        f"|---|---|",
        f"| 6 Months | {_fmt_pct(m.get('short_term_return_6m'))} |",
        f"| 1 Year | {_fmt_pct(m.get('absolute_return_1y'))} |",
        f"| 3 Year | {_fmt_pct(m.get('absolute_return_3y'))} |",
        f"| 5 Year | {_fmt_pct(m.get('absolute_return_5y'))} |",
        f"| 10 Year | {_fmt_pct(m.get('absolute_return_10y'))} |",
        f"| CAGR 3Y | {_fmt_pct(m.get('cagr_3year'))} |",
        f"| CAGR 5Y | {_fmt_pct(m.get('cagr_5year'))} |",
        "",
        "### Risk Metrics",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Sharpe Ratio | {m.get('sharpe_ratio', 'N/A')} |",
        f"| Sortino Ratio | {m.get('sortino_ratio', 'N/A')} |",
        f"| Alpha | {_fmt_pct(m.get('alpha'))} |",
        f"| Beta | {m.get('beta', 'N/A')} |",
        f"| Std Dev | {_fmt_pct(m.get('standard_deviation'))} |",
        f"| Max Drawdown | {_fmt_pct(m.get('maximum_drawdown'))} |",
        f"| Tracking Error | {_fmt_pct(m.get('tracking_error'))} |",
        f"| Info Ratio | {m.get('information_ratio', 'N/A')} |",
        "",
        "### Capture Ratios",
        f"- **Upside Capture:** {m.get('upside_capture', 'N/A')}% | "
        f"**Downside Capture:** {m.get('downside_capture', 'N/A')}%",
    ]
    if m.get("final_verdict"):
        lines += ["", "### Verdict", m["final_verdict"]]
    if data.get("_offline"):
        lines.insert(2, "> ⚡ *Data served from cache — may be stale*")
    return "\n".join(lines)


def _format_stock(data: dict) -> str:
    """Format StockDetailResult → Markdown."""
    label = data.get("rating_label", "N/A")
    emoji = _rating_emoji(label)
    lines = [
        f"## {data.get('company_name', data.get('symbol', 'Unknown'))} "
        f"({data.get('symbol', '')})",
        f"**Sector:** {data.get('sector', 'N/A')} | "
        f"**Industry:** {data.get('industry', 'N/A')} | "
        f"**Market Cap:** {data.get('market_cap_cat', 'N/A')}",
        "",
        "### Price",
        f"- **Close:** {_fmt_num(data.get('latest_close'))} "
        f"({_fmt_pct(data.get('change_pct'))})",
        f"- **High:** {_fmt_num(data.get('latest_high'))} | "
        f"**Low:** {_fmt_num(data.get('latest_low'))} | "
        f"**Volume:** {data.get('latest_volume', 'N/A'):,}" if data.get("latest_volume") else "",
        f"- **52W High dist:** {_fmt_pct(data.get('pct_from_52w_high'))} | "
        f"**52W Low dist:** {_fmt_pct(data.get('pct_from_52w_low'))}",
        "",
        "### Rating",
        f"{emoji} **{label}** | "
        f"Total Score: {_fmt_score(data.get('total_score'))} | "
        f"Fundamental: {_fmt_score(data.get('fundamental_score'))} | "
        f"Technical: {_fmt_score(data.get('technical_score'))}",
        "",
        "### Technicals",
        f"| Indicator | Value |",
        f"|---|---|",
        f"| RSI (14) | {data.get('rsi_14', 'N/A')} |",
        f"| MACD Hist | {data.get('macd_hist', 'N/A')} |",
        f"| SMA 50 | {_fmt_num(data.get('sma_50'))} |",
        f"| SMA 200 | {_fmt_num(data.get('sma_200'))} |",
        "",
        "### Fundamentals (Latest)",
        f"| Ratio | Value |",
        f"|---|---|",
        f"| P/E | {data.get('pe_ratio', 'N/A')} |",
        f"| P/B | {data.get('pb_ratio', 'N/A')} |",
        f"| ROE | {_fmt_pct(data.get('roe'))} |",
        f"| ROCE | {_fmt_pct(data.get('roce'))} |",
        f"| Debt/Equity | {data.get('debt_equity', 'N/A')} |",
        f"| EBITDA Margin | {_fmt_pct(data.get('ebitda_margin'))} |",
        f"| EV/EBITDA | {data.get('ev_ebitda', 'N/A')} |",
        f"| Piotroski F | {data.get('piotroski_f_score', 'N/A')}/9 |",
    ]
    if data.get("_offline"):
        lines.insert(2, "> ⚡ *Data served from cache — may be stale*")
    return "\n".join(l for l in lines if l)


def _format_comparison(data: dict) -> str:
    """Format ComparisonResponse → Markdown comparison table."""
    funds = data.get("funds", [])
    ranking = data.get("ranking", {})
    if not funds:
        return "No fund data available for comparison."

    lines = ["## Fund Comparison\n"]

    # Rankings summary
    if ranking and ranking.get("rankings"):
        lines.append("### Rankings")
        for r in ranking["rankings"]:
            is_rec = "✅ Recommended" if r.get("is_recommended") else ""
            lines.append(
                f"{r['rank']}. **{r['scheme_code']}** — "
                f"Score: {r['composite_score']:.2f} {is_rec}"
            )
            if r.get("recommendation_reason"):
                lines.append(f"   *{r['recommendation_reason']}*")
        if ranking.get("comparison_summary"):
            lines.append(f"\n{ranking['comparison_summary']}")
        lines.append("")

    # Metrics table
    if funds:
        headers = ["Metric"] + [f.get("scheme_code", "?") for f in funds]
        lines.append("### Metrics\n")
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        metric_rows = [
            ("Category",    lambda m, fi: fi.get("scheme_category", "N/A"), False),
            ("NAV",         lambda m, fi: f"₹{m.get('current_nav', 'N/A')}", False),
            ("AUM (Cr)",    lambda m, fi: f"₹{m.get('aum_in_crores', 'N/A')}", False),
            ("1Y Return",   lambda m, fi: _fmt_pct(m.get("absolute_return_1y")), True),
            ("3Y CAGR",     lambda m, fi: _fmt_pct(m.get("cagr_3year")), True),
            ("5Y CAGR",     lambda m, fi: _fmt_pct(m.get("cagr_5year")), True),
            ("Sharpe",      lambda m, fi: str(m.get("sharpe_ratio", "N/A")), True),
            ("Sortino",     lambda m, fi: str(m.get("sortino_ratio", "N/A")), True),
            ("Alpha",       lambda m, fi: _fmt_pct(m.get("alpha")), True),
            ("Max DD",      lambda m, fi: _fmt_pct(m.get("maximum_drawdown")), False),
            ("Expense",     lambda m, fi: f"{m.get('expense_ratio', 'N/A')}%", False),
        ]
        for row_label, extractor, _ in metric_rows:
            values = []
            for f in funds:
                m = f.get("metrics") or {}
                fi = f.get("fund_info") or {}
                values.append(extractor(m, fi))
            lines.append("| " + " | ".join([row_label] + values) + " |")

    if data.get("warning"):
        lines.append(f"\n> ⚠️ {data['warning']}")
    return "\n".join(lines)


def _format_screener(data: dict, filters: dict) -> str:
    """Format ScreenerResponse → Markdown table."""
    results = data.get("results", [])
    total   = data.get("total", 0)
    if not results:
        return f"No stocks found matching the criteria: {filters}"

    filter_summary = ", ".join(
        f"{k}={v}" for k, v in filters.items() if v is not None
    )
    lines = [
        f"## Screener Results",
        f"**Filters:** {filter_summary}",
        f"**Showing:** {len(results)} of {total} matching stocks\n",
        "| Symbol | Company | Sector | PE | ROE | Debt/Eq | Rating |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results[:10]:
        lines.append(
            f"| {r.get('symbol')} | {r.get('company_name', '')[:25]} | "
            f"{r.get('sector', 'N/A')[:15]} | "
            f"{r.get('pe_ratio', 'N/A')} | "
            f"{_fmt_pct(r.get('roe'))} | "
            f"{r.get('debt_equity', 'N/A')} | "
            f"{_rating_emoji(r.get('rating_label'))} {r.get('rating_label', 'N/A')} |"
        )
    return "\n".join(lines)


# Public dispatch — called by tool functions
def format_tool_result(tool_name: str, data: dict) -> str:
    dispatch = {
        "fetch_fund":    _format_fund,
        "fetch_stock":   _format_stock,
        "compare_funds": _format_comparison,
    }
    fn = dispatch.get(tool_name)
    return fn(data) if fn else str(data)
```

---

## Task 7.9 — React: Wire Streaming to AgentChatPage

**File:** `src/pages/AgentChatPage.tsx` (modify Phase 5 stub)
**Estimated time:** 1 hour

Replace the `agentApi.chat()` call with an SSE stream. The existing
session management, message display, and suggestion chips remain unchanged.

```typescript
// src/pages/AgentChatPage.tsx — replace handleSend function only

async function handleSend(e: React.FormEvent) {
  e.preventDefault();
  if (!sessionId || !input.trim() || loading) return;

  const userMsg = input.trim();
  setInput("");
  setLoading(true);

  // Optimistic UI: show user message immediately
  const userBubble: AgentMessage = {
    id: Date.now(), session_id: sessionId,
    sequence_num: messages.length + 1,
    role: "user", content_text: userMsg,
    created_at: new Date().toISOString(),
  };
  setMessages(m => [...m, userBubble]);

  // Add empty assistant bubble for streaming
  const assistantId = Date.now() + 1;
  const assistantBubble: AgentMessage = {
    id: assistantId, session_id: sessionId,
    sequence_num: messages.length + 2,
    role: "assistant", content_text: "",
    created_at: new Date().toISOString(),
  };
  setMessages(m => [...m, assistantBubble]);

  // ── SSE streaming ─────────────────────────────────────────────────────────
  const url = `http://localhost:8001/agent/sessions/${sessionId}/stream` +
    `?message=${encodeURIComponent(userMsg)}`;

  const eventSource = new EventSource(url);
  let accumulated = "";

  eventSource.onmessage = (e) => {
    accumulated += e.data;
    setMessages(m => m.map(msg =>
      msg.id === assistantId
        ? { ...msg, content_text: accumulated }
        : msg
    ));
  };

  eventSource.addEventListener("done", () => {
    eventSource.close();
    setLoading(false);
  });

  eventSource.addEventListener("error", (e) => {
    eventSource.close();
    setLoading(false);
    // If SSE fails entirely, fall back to POST
    if (!accumulated) {
      fallbackToPost(sessionId, userMsg, assistantId);
    }
  });
}

// Fallback: non-streaming POST if SSE is blocked
async function fallbackToPost(sessionId: number, message: string, assistantId: number) {
  try {
    const resp = await agentApi.chat(sessionId, message);
    setMessages(m => m.map(msg =>
      msg.id === assistantId
        ? { ...msg, content_text: resp.reply }
        : msg
    ));
  } catch {
    setMessages(m => m.map(msg =>
      msg.id === assistantId
        ? { ...msg, content_text: "Request failed. Please try again." }
        : msg
    ));
  } finally {
    setLoading(false);
  }
}
```

---

## Task 7.10 — Error Handling & Guardrails

**Estimated time:** 1 hour

### Turn limit guardrail

Enforced in `llm_node` via `turn_count >= settings.AGENT_MAX_TURNS`. At 8 turns the graph ends and returns the last assistant message. In practice, most queries finish in 2–3 turns: one tool call, one analysis.

### Tool timeout

Each tool has a 15-second timeout via `httpx.AsyncClient(timeout=15)`. If the proxy is offline, `ToolError` is raised and the LLM receives a graceful error message and can say "I couldn't retrieve the data for X."

### Token budget

`MAX_TOKENS=4096` per LLM call. The system prompt is ~600 tokens. History (20 messages × ~100 tokens avg) = ~2000 tokens. Tool results (2–3 tools × ~500 tokens each) = ~1500 tokens. Total input context typically 4000–5000 tokens. Output capped at 4096. Total per conversation: ~8–10K tokens = ~$0.03–0.05 per conversation on Sonnet 4.6.

### Context window overflow

If `_to_anthropic_format()` produces more than 15,000 tokens (estimated), trim the oldest messages from the middle of history while always keeping: (1) the first user message, (2) the last 5 turns, (3) the current user message.

```python
# In _to_anthropic_format() — add trim step at end:
if len(messages) > 20:
    # Keep first 2 + last 18
    messages = messages[:2] + messages[-18:]
```

### Investment advice guardrail

The system prompt explicitly says "Never make buy/sell recommendations." If the LLM still produces a recommendation (unlikely with the current prompt), this is caught in the memory extraction step — the `extract_memory_updates` function does not extract buy/sell signals as memory facts.

---

## Task 7.11 — Smoke Tests

**Estimated time:** 1 hour

Run these manually after implementation. Every test must pass.

```bash
BASE="http://localhost:8001"

# 1. Create a session
SESSION=$(curl -s -X POST $BASE/agent/sessions \
  -H "Content-Type: application/json" \
  -d '{"context_type": "stock", "context_id": "RELIANCE"}' \
  | python -m json.tool | grep session_id | grep -o '[0-9]*')
echo "Session ID: $SESSION"

# 2. Basic stock query — should call fetch_stock tool
curl -s -X POST "$BASE/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the current RSI and is RELIANCE overbought?"}' \
  | python -m json.tool
# Expected: reply with RSI value, SMA comparison, analysis

# 3. Fund query — should call fetch_fund tool
curl -s -X POST "$BASE/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Compare Axis Bluechip and Mirae Asset Large Cap"}' \
  | python -m json.tool
# Expected: comparison table with scheme codes, Sharpe ratios etc.

# 4. Portfolio query
curl -s -X POST "$BASE/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "How is my portfolio performing?"}' \
  | python -m json.tool
# Expected: portfolio summary with P&L per holding

# 5. Screener query
curl -s -X POST "$BASE/agent/sessions/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Find large cap IT stocks with ROE above 20% and PE below 30"}' \
  | python -m json.tool
# Expected: screener results table

# 6. Message history persisted
curl -s "$BASE/agent/sessions/$SESSION/messages" | python -m json.tool
# Expected: user + assistant + tool messages in order

# 7. Memory extraction
curl -s "$BASE/agent/memory" | python -m json.tool
# Expected: any inferred facts from the conversation

# 8. Streaming endpoint
curl -N "$BASE/agent/sessions/$SESSION/stream?message=What+is+RELIANCE+PE+ratio"
# Expected: SSE chunks arriving, then "event: done"

# 9. Offline tool handling (stop client proxy, test graceful failure)
# Expected: "I couldn't retrieve data for X" in reply, not a 500 error

# 10. Max turns guardrail (requires manual test with a very complex query)
# Expected: reply within 8 LLM turns, not an infinite loop
```

---

## 17. Data Flow: Full Request Trace

A single user message `"Analyse RELIANCE"` with context_type=stock:

```
1. React POST /agent/sessions/1/chat  {"message": "Analyse RELIANCE"}

2. agent.py chat():
   - Loads 0 history messages (new session)
   - Loads memory context: "risk_tolerance: moderate"
   - Builds initial state: {messages: [user_msg], turn_count: 0}

3. LangGraph START → llm_node (turn 1):
   - Calls claude-sonnet-4-6 with system prompt + 1 user message + 5 tools
   - System prompt: "You are in stock mode for RELIANCE..."
   - LLM responds: tool_use block → fetch_stock("RELIANCE")
   - State: turn_count=1, stop_reason=tool_use

4. should_continue → tool_node
   - Calls fetch_stock("RELIANCE")
   - → GET http://localhost:8001/proxy/stocks/RELIANCE
   - → cache HIT → returns StockDetailResult JSON
   - → _format_stock() → Markdown with price, RSI, PE, rating...
   - Appends tool_result to messages as user turn

5. tool_node → llm_node (turn 2):
   - LLM has: user message + tool result (RELIANCE Markdown)
   - Generates analysis: "RELIANCE is trading at ₹2,850...
     RSI at 58 suggests neutral momentum...
     PE of 23x is reasonable for the sector..."
   - stop_reason=end_turn

6. should_continue → memory_node
   - Extracts text from assistant response
   - extract_memory_updates(): no new facts to extract this turn
   - Sets final_reply = analysis text
   - State: memory_updates=[]

7. agent.py chat():
   - Persists user message to agent_messages (seq=1)
   - Persists tool message to agent_messages (seq=2, role=tool, tool_name=fetch_stock)
   - Persists assistant message to agent_messages (seq=3)
   - No memory updates to write
   - Returns {"reply": "RELIANCE analysis...", "session_id": 1}

8. React receives reply, renders in AgentChatPage
   Total time: ~3-5 seconds (1 tool call + 2 LLM turns)
   Anthropic tokens: ~3,500 input + ~800 output ≈ $0.018
```

---

## 18. Token Budget & Cost Estimates

| Scenario | Input tokens | Output tokens | Cost (Sonnet 4.6) |
|---|---|---|---|
| Simple stock query (1 tool) | ~3,500 | ~600 | ~$0.018 |
| Fund comparison (2 tools) | ~5,000 | ~1,000 | ~$0.027 |
| Portfolio summary (5 holdings) | ~4,500 | ~800 | ~$0.022 |
| Screener + analysis (2 tools) | ~4,800 | ~1,000 | ~$0.026 |
| Complex multi-fund analysis | ~7,000 | ~1,500 | ~$0.040 |
| **Daily usage (10 conversations)** | — | — | **~$0.25/day** |
| **Monthly** | — | — | **~$7.50/month** |

Sonnet 4.6 pricing (May 2026): ~$3/MTok input, ~$15/MTok output.
At typical usage, the agent costs less than a coffee per month.

Set a soft alert in `config.py`:
```python
AGENT_DAILY_TOKEN_BUDGET: int = 100_000  # Alert if exceeded
```

---

## 19. Dependency Changes

```text
# Add to nivesh-client/requirements.txt:

anthropic==0.28.0         # Anthropic Python SDK (may already be listed)
langgraph==0.2.0          # LangGraph agent framework
langchain-core==0.2.0     # Required by LangGraph (types and message utilities)
```

**Note:** LangGraph `0.2.x` is used because it has stable `TypedDict`-based
state and `StateGraph` with `add_messages` annotation. Avoid `0.1.x` —
the `add_messages` reducer was added in `0.2.0`. Check latest stable
version before installing.

---

## 20. Environment Variables

```bash
# Add to ~/.nivesh/.env

# Anthropic API key — required for Phase 7
ANTHROPIC_API_KEY=sk-ant-...

# Agent configuration — optional, sensible defaults in config.py
AGENT_MAX_TURNS=8
AGENT_MAX_HISTORY_MESSAGES=20
AGENT_ENABLE_MEMORY=true
AGENT_DAILY_TOKEN_BUDGET=100000
```

---

## 21. Definition of Done

Phase 7 is complete when all of the following are true:

- [ ] `POST /agent/sessions/{id}/chat` returns a real LLM reply (not the stub)
- [ ] Agent calls `fetch_stock` tool when asked about a stock
- [ ] Agent calls `fetch_fund` tool when asked about a fund
- [ ] Agent calls `compare_funds` tool when asked to compare funds
- [ ] Agent calls `get_portfolio_summary` when asked about portfolio
- [ ] Agent calls `screen_stocks` with correct filters when screener query is made
- [ ] Tool results are formatted as Markdown, not raw JSON, in LLM context
- [ ] Conversation history is loaded from `agent_messages` on each turn
- [ ] Memory context from `agent_memory` is injected into system prompt
- [ ] `extract_memory_updates` detects and persists user-stated facts
- [ ] `GET /agent/sessions/{id}/stream` returns SSE chunks
- [ ] React `AgentChatPage` renders streaming chunks in real time
- [ ] Turn count guardrail triggers at 8 turns — no infinite loops
- [ ] Tool timeout (15s) produces graceful error message in reply
- [ ] Tool call with offline server returns friendly error, not 500
- [ ] All 10 smoke tests in Task 7.11 pass
- [ ] `GET /agent/sessions/{id}/messages` shows user + tool + assistant rows
- [ ] `GET /agent/memory` shows facts extracted from conversation
- [ ] Cost per conversation is under $0.05 for typical queries
- [ ] Agent never makes explicit buy/sell recommendations

---

## 22. Execution Order — Day by Day

```
Day 1 (4h)
  Task 7.1  Anthropic client + config.py additions        30 min
  Task 7.2  Tool executor — error handling + formatters   1h
  Task 7.8  formatter.py (fund, stock, comparison, screener) 1.5h
  Task 7.3  state.py + graph.py (LangGraph assembly)      1h

Day 2 (4h)
  Task 7.3  nodes.py (llm_node, tool_node, memory_node)   2h
  Task 7.4  memory.py (extraction logic)                  1h
  Task 7.7  prompts.py (system prompt + context variants) 1h

Day 3 (4h)
  Task 7.5  Wire chat endpoint (replace stub in agent.py) 2h
  Task 7.6  Streaming SSE endpoint                        1.5h
  Task 7.9  React AgentChatPage streaming wiring          0.5h

Day 4 (3h)
  Task 7.10 Error handling + guardrails review            1h
  Task 7.11 Full smoke tests — fix issues                 2h
```

**Total: 4 working days**

---

*Phase 7 Implementation Plan · Nivesh Platform · May 2026*
*Previous: Phase 5 — React UI Adaptation*
*Next: Phase 8 — CI/CD + Production Hardening*
