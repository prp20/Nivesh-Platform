# Phase 6 — Agentic Layer: Supervisor + Specialist Agents (ChatGroq + LangGraph)
## Design Spec · Nivesh Platform · 2026-05-16

---

## 1. Context

Phase 6 adds an LLM-powered financial research agent to Nivesh Client. The original
plan used the Anthropic SDK with a manual tool-use loop. This spec replaces that
design with **ChatGroq (Groq inference) + LangGraph (multi-agent supervisor pattern)**.

The React `AgentChat.jsx` UI and all SQLite persistence tables (`agent_sessions`,
`agent_messages`, `agent_memory`) remain unchanged — only the Python agent layer changes.

---

## 2. Architecture

```
User Message
     │
     ▼
┌─────────────────────────────────────────────┐
│           LangGraph StateGraph              │
│                                             │
│   ┌─────────────┐                           │
│   │  Supervisor  │ (ChatGroq — routes only) │
│   └──────┬──────┘                           │
│          │ routes to one of:                │
│    ┌─────┼──────────┬────────┐              │
│    ▼     ▼          ▼        ▼              │
│  Stock  Fund    Portfolio  FINISH           │
│  Agent  Agent   Agent                       │
│ (ReAct)(ReAct) (ReAct)                     │
└─────────────────────────────────────────────┘
     │
     ▼
Final reply saved to SQLite agent_messages
```

### Agent Tool Split

| Agent | Tools |
|---|---|
| `stock_agent` | `get_stock_detail`, `search_stocks`, `screen_stocks` |
| `fund_agent` | `get_fund_detail`, `compare_funds` |
| `portfolio_agent` | `get_portfolio`, `get_market_overview` |

### Routing Flow

1. Supervisor receives the full conversation history
2. Supervisor uses `with_structured_output(RouteDecision)` to pick one worker or FINISH
3. Selected worker runs a ReAct loop (ChatGroq + its tools, up to `recursion_limit`)
4. Worker result appended to messages state; control returns to Supervisor
5. Supervisor sees worker output and emits FINISH with synthesized reply

---

## 3. File Structure

```
nivesh-client/app/agent/
├── __init__.py      ← unchanged (empty)
├── tools.py         ← REWRITE: 7 async @tool functions (3 groups)
├── memory.py        ← UNCHANGED: load_memory_context / save_memory_item
├── agents.py        ← NEW: builds 3 worker ReAct agents
├── supervisor.py    ← NEW: RouteDecision schema + LangGraph graph assembly
└── runner.py        ← REWRITE: run_turn() uses the assembled LangGraph graph
```

---

## 4. Component Specifications

### 4.1 tools.py

Rewrite all 7 tools as LangChain `@tool`-decorated async functions. Each tool:
- Uses `httpx.AsyncClient` to hit `http://localhost:8001/proxy/*` or `/local/*`
- Returns `str` (JSON-serialised dict) — LangChain tool results must be strings
- Never raises — errors returned as `json.dumps({"error": "..."})`

Tool groups:
- **Stock tools:** `get_stock_detail(symbol)`, `search_stocks(query)`, `screen_stocks(**filters)`
- **Fund tools:** `get_fund_detail(scheme_code)`, `compare_funds(scheme_codes)`
- **Portfolio/Market tools:** `get_portfolio()`, `get_market_overview()`

### 4.2 agents.py

Builds the three worker agents using `langgraph.prebuilt.create_react_agent`:

```python
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

def build_stock_agent(llm):
    return create_react_agent(llm, [get_stock_detail, search_stocks, screen_stocks])

def build_fund_agent(llm):
    return create_react_agent(llm, [get_fund_detail, compare_funds])

def build_portfolio_agent(llm):
    return create_react_agent(llm, [get_portfolio, get_market_overview])
```

Each agent is invoked as an async node inside the LangGraph graph.

### 4.3 supervisor.py

**RouteDecision schema:**
```python
class RouteDecision(BaseModel):
    next: Literal["stock_agent", "fund_agent", "portfolio_agent", "FINISH"]
    reason: str   # logged for debugging
```

**Supervisor node:** Uses `ChatGroq.with_structured_output(RouteDecision)`. The system
prompt describes each agent's specialty:
- `stock_agent` — NSE stock prices, technicals, fundamentals, screening
- `fund_agent` — mutual fund NAV, Sharpe/Sortino/Alpha, fund comparisons
- `portfolio_agent` — user's portfolio holdings, P&L, Nifty/BankNifty market overview

**Graph assembly:**
```
START → supervisor_node
supervisor_node → [stock_agent_node | fund_agent_node | portfolio_agent_node | END]
stock_agent_node → supervisor_node
fund_agent_node  → supervisor_node
portfolio_agent_node → supervisor_node
```

Conditional edge routes on `RouteDecision.next`.

**Recursion limit:** `graph.compile()` with no explicit limit; invoke with
`config={"recursion_limit": 10}` — prevents infinite supervisor ↔ worker loops.

### 4.4 runner.py

`run_turn(session_id, user_message, db)`:

1. Guard: return error string if `GROQ_API_KEY` is empty
2. Load `agent_messages` rows from SQLite, ordered by `sequence_num`
3. Convert to LangChain messages:
   - `role="user"` → `HumanMessage(content=content_text)`
   - `role="assistant"` with no `content_json` → `AIMessage(content=content_text)`
   - `role="assistant"` with `content_json` → `AIMessage` with `tool_calls`
   - `role="tool"` → `ToolMessage(content=..., tool_call_id=...)`
4. Inject agent memory into system message prepended to messages list
5. Call `await graph.ainvoke({"messages": lc_messages}, config={"recursion_limit": 10})`
6. Diff output: `new_lc_messages = result["messages"][len(lc_messages):]`
7. Save each new message to `agent_messages` SQLite table
8. Update `agent_sessions.last_msg_at` and commit
9. Extract and return final `AIMessage.content` string

---

## 5. Configuration Changes

**config.py:**
```python
# Remove:
ANTHROPIC_API_KEY: str = ""
AGENT_MODEL: str = "claude-sonnet-4-6"

# Add:
GROQ_API_KEY: str = ""          # Set in ~/.nivesh/.env
AGENT_MODEL: str = "llama-3.3-70b-versatile"
```

**requirements.txt:**
```
# Remove:
anthropic>=0.51.0

# Add (all already installed, pinning for reproducibility):
langchain-groq>=1.1.0
langgraph>=1.2.0
langchain>=1.3.0
langchain-core>=0.3.0
```

---

## 6. Message Persistence

New LangChain message types → SQLite `agent_messages.role` mapping:

| LangChain Type | SQLite `role` | Notes |
|---|---|---|
| `HumanMessage` | `user` | `content_text = msg.content` |
| `AIMessage` (no tool_calls) | `assistant` | `content_text = msg.content` |
| `AIMessage` (with tool_calls) | `assistant` | `content_json = [tool_call dicts]` |
| `ToolMessage` | `tool` | `content_json = {"tool_call_id": ..., "result": ...}`, `tool_name` set |

---

## 7. Error Handling

| Scenario | Behaviour |
|---|---|
| `GROQ_API_KEY` empty | Return descriptive error string before graph call |
| Groq API unreachable | LangChain raises; `run_turn` catches, returns user-friendly message |
| Tool HTTP timeout (30s) | Tool returns `{"error": "timed out"}` — agent handles gracefully |
| `recursion_limit` hit | LangGraph raises `GraphRecursionError`; caught in `run_turn`, returns partial reply |

---

## 8. What Does NOT Change

- `memory.py` — unchanged
- `agent.py` router — already updated in Phase 6 Task 5 (run_turn wired in)
- All SQLite tables (`agent_sessions`, `agent_messages`, `agent_memory`)
- React `AgentChat.jsx` UI
- The `/chat` endpoint interface (`{reply, session_id}`)

---

## 9. Definition of Done

- `POST /agent/sessions/{id}/chat` returns a Groq-generated reply (not stub)
- A stock query routes to `stock_agent` and fires `get_stock_detail`
- A fund comparison query routes to `fund_agent` and fires `compare_funds`
- A portfolio query routes to `portfolio_agent` and fires `get_portfolio`
- All new messages (assistant + tool) saved to `agent_messages`
- Empty `GROQ_API_KEY` returns human-readable error (not 500)
- `CLAUDE.md` phases table updated: P6 marked Done

---

*Spec version 1.0 · Phase 6 Agentic Layer · Nivesh Platform · 2026-05-16*
