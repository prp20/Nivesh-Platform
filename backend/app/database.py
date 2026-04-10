from contextlib import asynccontextmanager
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
session_factory = AsyncSessionLocal
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@asynccontextmanager
async def raw_connection():
    """Get a raw asyncpg connection for direct SQL operations."""
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    try:
        yield conn
    finally:
        await conn.close()
