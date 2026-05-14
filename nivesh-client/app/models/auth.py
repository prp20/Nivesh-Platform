"""
Auth and server config models.

AuthToken: stores the current JWT access and refresh tokens.
  Single row (id=1) — replaced on every login or token refresh.
  Tokens stored in SQLite, never in browser storage or env vars.

ServerConfig: key-value store for server connection state.
  Updated on every health ping.
"""

from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func

from ..database import Base


class AuthToken(Base):
    """
    Current JWT access and refresh tokens.
    Only one row ever exists (id=1). Replaced on each login/refresh.
    """
    __tablename__ = "auth_tokens"

    id            = Column(Integer, primary_key=True, default=1)
    access_token  = Column(Text, nullable=False)
    refresh_token = Column(Text)
    expires_at    = Column(TIMESTAMP, nullable=False)
    username      = Column(String(50))
    created_at    = Column(TIMESTAMP, server_default=func.now())


class ServerConfig(Base):
    """
    Key-value store for server connection state.
    Single-row-per-key table updated on every health ping.

    Keys:
      'server_url'        → from NIVESH_SERVER_URL env var
      'is_online'         → 'true' | 'false'
      'last_connected_at' → ISO timestamp
      'server_version'    → from /health response
      'last_health_check' → ISO timestamp of last ping
    """
    __tablename__ = "server_config"

    key   = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
