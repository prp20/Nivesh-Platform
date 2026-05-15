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
