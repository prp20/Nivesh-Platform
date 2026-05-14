"""
Client-side agentic storage.

Three tables:
  agent_sessions  — one row per conversation thread
  agent_messages  — one row per message/tool call in a session
  agent_memory    — persistent facts extracted from conversations

The existing server project uses LangGraph for the fundamental scoring pipeline
(ScoringStateSchema in server schemas.py). The client agent layer uses the same
pattern: state is a dict stored as JSON, not a fixed schema.

AgentMessage supports both plain text (content_text) and LangGraph state dicts
(content_json) so Phase 6 can store full pipeline state without a schema change.
"""

from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Boolean
from sqlalchemy.dialects.sqlite import JSON

from ..database import Base
from sqlalchemy.sql import func


class AgentSession(Base):
    """One session = one focused conversation (e.g. 'Analyse RELIANCE')."""
    __tablename__ = "agent_sessions"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    title        = Column(String(255))
    # Auto-generated from first user message if not provided
    context_type = Column(String(20))
    # context_type: 'stock' | 'fund' | 'portfolio' | 'screener' | 'general'
    context_id   = Column(String(50))
    # context_id: NSE symbol, scheme_code, or None for portfolio/general
    model_used   = Column(String(50), default="claude-sonnet-4-6")
    is_active    = Column(Boolean, default=True)
    started_at   = Column(TIMESTAMP, server_default=func.now())
    last_msg_at  = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class AgentMessage(Base):
    """
    One row per turn in a session.
    Stores both plain text messages and LangGraph state dicts.

    role values:
      'user'      — user input
      'assistant' — LLM response
      'tool'      — tool call result (JSON payload from a server API call)
      'state'     — full LangGraph state snapshot (for complex pipelines)

    content_json stores either:
      - A string (for user/assistant messages)
      - A JSON dict (for tool results and LangGraph state)
    """
    __tablename__ = "agent_messages"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    session_id    = Column(Integer, nullable=False)
    # FK to agent_sessions.id — not using SQLAlchemy FK to keep Alembic batch-mode simple
    sequence_num  = Column(Integer, nullable=False)
    # Order within the session — used for reconstructing conversation history
    role          = Column(String(15), nullable=False)
    content_text  = Column(Text)
    # Plain text version (for user/assistant messages — UI display)
    content_json  = Column(JSON)
    # JSON version (for tool results and LangGraph state dicts)
    tool_name     = Column(String(100))
    # Populated when role='tool' — which tool was called
    created_at    = Column(TIMESTAMP, server_default=func.now())


class AgentMemory(Base):
    """
    Persistent facts extracted across sessions.
    Read at the start of each new session to personalise responses.

    Examples:
      key='risk_tolerance',   value='conservative — prefers large-cap funds'
      key='preferred_sector', value='IT, Pharma'
      key='portfolio_size',   value='medium — 10-20 holdings'
    """
    __tablename__ = "agent_memory"

    key        = Column(String(200), primary_key=True)
    value      = Column(Text, nullable=False)
    source     = Column(String(50))
    # source: 'user_stated' | 'inferred' | 'manual'
    confidence = Column(String(10), default="high")
    # confidence: 'high' | 'medium' | 'low'
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
