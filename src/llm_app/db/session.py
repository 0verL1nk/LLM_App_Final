"""
Database session management utilities
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from .database import async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.
    This is a wrapper around get_db for more explicit usage.
    """
    async with async_session_factory() as session:
        yield session


async def get_transactional_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session with automatic transaction handling.
    Commits on success, rolls back on exception.
    """
    async with async_session_factory() as session:
        try:
            async with session.begin():
                yield session
        except Exception:
            await session.rollback()
            raise