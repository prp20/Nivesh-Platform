from pydantic_settings import BaseSettings

_DEV_SECRET_KEY = "dev-secret-key-do-not-use-in-production"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Nivesh API"
    # Mandatory in production, safe dev default for local testing
    DATABASE_URL: str = (
        "postgresql+asyncpg://nivesh_admin:nivesh_password_123@localhost:5432/nivesh_db"
    )
    API_V1_STR: str = "/api/v1"

    # Security Toggle — set ENABLE_AUTH=true via environment variable in production
    ENABLE_AUTH: bool = False
    SECRET_KEY: str = _DEV_SECRET_KEY
    # Token validity in minutes. Default 30 min; set ACCESS_TOKEN_EXPIRE_MINUTES in env for production.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    ALLOWED_ORIGINS: list = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Fail fast if auth is enabled but the secret key is still the known dev value.
# This prevents accidentally deploying with a forgeable JWT secret.
if settings.ENABLE_AUTH and settings.SECRET_KEY == _DEV_SECRET_KEY:
    raise ValueError(
        "ENABLE_AUTH is True but SECRET_KEY is still the insecure dev default. "
        "Set a strong random SECRET_KEY via environment variable before enabling auth."
    )
