from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Nivesh API"
    # Mandatory in production, safe dev default for local testing
    DATABASE_URL: str = (
        "postgresql+asyncpg://nivesh_admin:nivesh_password_123@localhost:5432/nivesh_db"
    )
    API_V1_STR: str = "/api/v1"

    # Security Toggle — set ENABLE_AUTH=true via environment variable in production
    ENABLE_AUTH: bool = False
    SECRET_KEY: str = "dev-secret-key-do-not-use-in-production"
    # Token validity in minutes. Default 30 min; set ACCESS_TOKEN_EXPIRE_MINUTES in env for production.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    ALLOWED_ORIGINS: list = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174"
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
