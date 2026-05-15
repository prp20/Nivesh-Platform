"""
Agent memory — persistent facts across sessions.

load_memory_context(): Returns all stored facts as a formatted string
that is appended to the system prompt. This personalises the agent
to the user's known preferences, risk tolerance, and portfolio context.

save_memory_item(): Upserts a single fact (thin wrapper over the
existing PUT /agent/memory/{key} endpoint logic, for use by runner.py).
"""

import logging

from sqlalchemy import func as sa_func
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
    confidence: str = "medium",
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
        set_={
            "value": value,
            "confidence": confidence,
            "updated_at": sa_func.now(),  # Core INSERT bypasses ORM onupdate hook
            # Note: source is intentionally excluded — user_stated facts keep
            # their source even when the agent later re-infers the same key.
        },
    )
    await db.execute(stmt)
    # Caller is responsible for commit
    logger.debug("Memory saved: %s = %s", key, value)
