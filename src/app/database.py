from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    # One connection per checkout in tests avoids cross-event-loop pool reuse.
    poolclass=NullPool if settings.environment == "test" else None,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an async database session."""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables. Dev convenience only — use `alembic upgrade head` in production."""
    # Import models so their tables are registered on Base.metadata.
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
