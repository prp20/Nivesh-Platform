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

    # ── Convert SQLite rows -> LangChain messages ──────────────────────────────
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

    SQLite role -> LangChain type:
      'user'      -> HumanMessage(content=content_text)
      'assistant' without content_json -> AIMessage(content=content_text)
      'assistant' with content_json    -> AIMessage(content=..., tool_calls=[...])
      'tool'      -> ToolMessage(content=result_json, tool_call_id=..., name=...)
    """
    messages: list[BaseMessage] = []

    for row in history:
        if row.role == "user":
            messages.append(HumanMessage(content=row.content_text or ""))

        elif row.role == "assistant":
            if row.content_json and isinstance(row.content_json, list):
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
