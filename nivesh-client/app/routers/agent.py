"""
Agent router — /agent/*

Session storage and message persistence for the local agent.
Phase 4: builds the storage + API scaffolding.
Phase 6: wires in the actual LLM call (Anthropic API).

The message model is designed to store LangGraph state dicts
(matching ScoringStateSchema pattern from the server):
  - content_json stores the full state dict
  - content_text stores a human-readable summary for UI display
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.agent import AgentMemory, AgentMessage, AgentSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    title: Optional[str] = None
    context_type: str = "general"    # 'stock' | 'fund' | 'portfolio' | 'general'
    context_id: Optional[str] = None
    model_used: str = "claude-sonnet-4-6"


class MessageCreate(BaseModel):
    role: str                            # 'user' | 'assistant' | 'tool' | 'state'
    content_text: Optional[str] = None
    content_json: Optional[dict] = None
    tool_name: Optional[str] = None


class ChatRequest(BaseModel):
    message: str                         # User's plain text input


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.post("/sessions", status_code=201)
async def create_session(
    body: SessionCreate, db: AsyncSession = Depends(get_db)
):
    session = AgentSession(**body.model_dump())
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": session.id, "title": session.title}


@router.get("/sessions")
async def list_sessions(
    is_active: bool = True,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentSession)
        .where(AgentSession.is_active == is_active)
        .order_by(AgentSession.last_msg_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.delete("/sessions/{session_id}", status_code=204)
async def close_session(
    session_id: int, db: AsyncSession = Depends(get_db)
):
    """Mark session as inactive (soft delete)."""
    await db.execute(
        update(AgentSession)
        .where(AgentSession.id == session_id)
        .values(is_active=False)
    )
    await db.commit()


# ── Messages ──────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.sequence_num.asc())
    )
    return result.scalars().all()


@router.post("/sessions/{session_id}/messages", status_code=201)
async def add_message(
    session_id: int,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Store a single message turn.
    Called by the Phase 6 agent runner after each LLM interaction.
    """
    result = await db.execute(
        select(AgentMessage.sequence_num)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.sequence_num.desc())
        .limit(1)
    )
    last_seq = result.scalar_one_or_none() or 0

    msg = AgentMessage(
        session_id=session_id,
        sequence_num=last_seq + 1,
        **body.model_dump(),
    )
    db.add(msg)

    # Bump session last_msg_at
    from sqlalchemy.sql import func
    await db.execute(
        update(AgentSession)
        .where(AgentSession.id == session_id)
        .values(last_msg_at=func.now())
    )

    await db.commit()
    return {"id": msg.id, "sequence_num": msg.sequence_num}


@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: int,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Main chat endpoint.

    Phase 4: stores the user message, returns a placeholder response.
    Phase 6: replaces the placeholder with actual LLM call + tool execution.
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

    # Phase 4 placeholder — Phase 6 wires the actual LLM
    return {
        "reply": "Agent not yet connected (Phase 6). Message stored successfully.",
        "session_id": session_id,
        "sequence_num": last_seq + 1,
    }


# ── Memory ────────────────────────────────────────────────────────────────────

@router.get("/memory")
async def get_memory(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentMemory))
    rows = result.scalars().all()
    return {r.key: {"value": r.value, "confidence": r.confidence, "source": r.source} for r in rows}


@router.put("/memory/{key}")
async def set_memory(
    key: str,
    value: str,
    confidence: str = "high",
    source: str = "user_stated",
    db: AsyncSession = Depends(get_db),
):
    stmt = sqlite_insert(AgentMemory).values(
        key=key, value=value, confidence=confidence, source=source
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"],
        set_={"value": value, "confidence": confidence},
    )
    await db.execute(stmt)
    await db.commit()
    return {"key": key, "value": value}


@router.delete("/memory/{key}", status_code=204)
async def delete_memory(key: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete as sa_delete
    await db.execute(sa_delete(AgentMemory).where(AgentMemory.key == key))
    await db.commit()
