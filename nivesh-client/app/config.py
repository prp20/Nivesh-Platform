"""
Client configuration using Pydantic BaseSettings.

Reads from ~/.nivesh/.env file and environment variables.
All settings can be overridden via environment variables.
"""

import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings

# Default DB path: ~/.nivesh/client.db
# Using user home keeps it outside the project dir
# so reinstalling the client doesn't wipe data
_DEFAULT_DB_PATH = Path.home() / ".nivesh" / "nivesh_client.db"


class Settings(BaseSettings):
    # ── Server connection ──────────────────────────────────────────────────────
    NIVESH_SERVER_URL: str = "http://localhost:8000"
    # In production: https://nivesh-server.onrender.com

    # ── Client app ────────────────────────────────────────────────────────────
    CLIENT_PORT: int = 8001
    SQLITE_DB_PATH: str = str(_DEFAULT_DB_PATH)

    @field_validator("SQLITE_DB_PATH", mode="before")
    @classmethod
    def expand_db_path(cls, v: str) -> str:
        return str(Path(os.path.expandvars(os.path.expanduser(v))).resolve())
    DEBUG: bool = False

    # ── Cache TTLs (seconds) ──────────────────────────────────────────────────
    # Controls how long server responses are served from local SQLite
    # before being re-fetched from the server.
    CACHE_TTL_FUND_LIST: int = 3600       # 1 hour
    CACHE_TTL_FUND_DETAIL: int = 3600     # 1 hour
    CACHE_TTL_FUND_NAV: int = 86400       # 24 hours — NAV only changes once a day
    CACHE_TTL_STOCK_DETAIL: int = 3600    # 1 hour
    CACHE_TTL_STOCK_LIST: int = 3600      # 1 hour
    CACHE_TTL_SCREENER: int = 900         # 15 minutes — screener results change often
    CACHE_TTL_BENCHMARKS: int = 3600      # 1 hour
    CACHE_TTL_ETL_STATUS: int = 300       # 5 minutes

    # ── Scheduler ─────────────────────────────────────────────────────────────
    HEALTH_PING_INTERVAL_S: int = 60      # How often to ping /health
    CACHE_CLEANUP_INTERVAL_S: int = 3600  # How often to delete expired cache rows

    # ── Agentic layer ─────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""                # Set in ~/.nivesh/.env (gsk_...)
    AGENT_MODEL: str = "llama-3.3-70b-versatile"

    class Config:
        env_file = str(Path.home() / ".nivesh" / ".env")
        extra = "ignore"


settings = Settings()
