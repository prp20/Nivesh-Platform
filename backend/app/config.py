import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Nivesh API"
    # Mandatory in production, safe dev default for local testing
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://nivesh_admin:nivesh_password_123@localhost:5432/nivesh_db")
    API_V1_STR: str = "/api/v1"
    
    # Security Toggle
    ENABLE_AUTH: bool = os.getenv("ENABLE_AUTH", "False").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-do-not-use-in-production")
    
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
