"""
Application configuration using Pydantic BaseSettings.

Reads from environment variables and .env file. All settings can be overridden
via environment variables (recommended for production deployments).
"""

import os
import logging
from pydantic_settings import BaseSettings

_logger = logging.getLogger(__name__)

_DEV_SECRET_KEY = "dev-secret-key-do-not-use-in-production"

# Default CORS origins for local development
_DEV_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]


class Settings(BaseSettings):
    """Application configuration loaded from environment and .env file."""

    PROJECT_NAME: str = "Nivesh API"

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://nivesh_admin:nivesh_password_123@localhost:5432/nivesh_db"
    )
    API_V1_STR: str = "/api/v1"

    # Security: Authentication
    ENABLE_AUTH: bool = True
    SECRET_KEY: str = _DEV_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ADMIN_TOKEN: str = ""  # Dev mode: explicit admin token, optional

    # Admin portal credentials (set during setup)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = ""  # bcrypt hash written by setup script

    # CORS: Read from environment, fall back to dev defaults
    ALLOWED_ORIGINS: list = []

    class Config:
        env_file = ".env"
        extra = "ignore"

    def __init__(self, **data):
        """Initialize settings and resolve CORS origins from environment."""
        super().__init__(**data)

        # If ALLOWED_ORIGINS not set via env, use dev defaults
        if not self.ALLOWED_ORIGINS:
            self.ALLOWED_ORIGINS = _DEV_CORS_ORIGINS

        # Also check CORS_ORIGINS env var (comma-separated)
        cors_env = os.getenv("ALLOWED_ORIGINS")
        if cors_env:
            self.ALLOWED_ORIGINS = [origin.strip() for origin in cors_env.split(",")]


settings = Settings()


# Warn if auth is enabled with an insecure key (don't hard-fail to allow local dev)
if settings.ENABLE_AUTH and settings.SECRET_KEY == _DEV_SECRET_KEY:
    _logger.warning(
        "SECURITY WARNING: ENABLE_AUTH=True but SECRET_KEY is the insecure dev default. "
        "Set a strong random SECRET_KEY via environment variable for any non-local deployment. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

if settings.ENABLE_AUTH and not settings.SECRET_KEY:
    raise ValueError(
        "ENABLE_AUTH is True but SECRET_KEY is empty. "
        "Set SECRET_KEY environment variable to a cryptographically secure random value."
    )
