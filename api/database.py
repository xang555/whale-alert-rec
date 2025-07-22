"""Async database engine setup for Whale Alert API."""
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from api.config import api_settings

# Ensure asyncpg driver in URL for SQLAlchemy asyncio engine
raw_url = str(api_settings.TIMESCALEDB_URL)
if raw_url.startswith("postgresql://"):
    async_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif raw_url.startswith("postgres://"):
    async_url = raw_url.replace("postgres://", "postgres+asyncpg://", 1)
else:
    async_url = raw_url

engine: AsyncEngine = create_async_engine(
    async_url,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20,
)
