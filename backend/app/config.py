import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Nivesh API"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://nivesh_admin:nivesh_password_123@localhost:5432/nivesh_db")
    API_V1_STR: str = "/api/v1"

    class Config:
        env_file = ".env"

settings = Settings()
