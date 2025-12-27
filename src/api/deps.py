"""
FastAPI dependencies for database sessions and authentication
"""
from typing import Generator, Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import async_session_factory
from models.user import User
from services.auth_service import AuthService
from core.logger import get_logger

logger = get_logger(__name__)

# Security scheme for JWT tokens
security = HTTPBearer(
    scheme_name="JWT",
    description="JWT Bearer token authentication",
    auto_error=True
)


async def get_db() -> Generator[AsyncSession, None, None]:
    """
    FastAPI dependency to get a database session

    Yields:
        AsyncSession: Database session

    Note:
        This dependency handles session lifecycle (creation and cleanup)
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get the current authenticated user

    Args:
        credentials: JWT token from Authorization header
        db: Database session

    Returns:
        User: Current authenticated user

    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    try:
        token = credentials.credentials

        # Verify token and get user
        user = await AuthService.verify_token_validity(db, token)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user

    except Exception as e:
        # Convert service exceptions to HTTPException
        # The service already logs the error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    FastAPI dependency to get the current authenticated user
    Additional checks can be added here (e.g., active status)

    Args:
        current_user: Current user from get_current_user

    Returns:
        User: Current active user

    Raises:
        HTTPException: 401 if user is inactive
    """
    # Add checks for user status if needed
    # For example: if not current_user.is_active:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Inactive user"
    #     )

    return current_user


# Type alias for authenticated user dependency
CurrentUser = Annotated[User, Depends(get_current_active_user)]


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    FastAPI dependency to optionally get the current authenticated user

    Args:
        credentials: JWT token from Authorization header (optional)
        db: Database session

    Returns:
        User or None: Current user if authenticated, None otherwise

    Note:
        This dependency won't raise an error if no token is provided
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        user = await AuthService.verify_token_validity(db, token)
        return user
    except Exception:
        # Return None if token is invalid
        return None


# Type alias for optional authenticated user dependency
OptionalCurrentUser = Annotated[Optional[User], Depends(get_optional_current_user)]


async def get_admin_user(
    current_user: CurrentUser
) -> User:
    """
    FastAPI dependency to get the current authenticated user with admin role

    Args:
        current_user: Current user from get_current_user

    Returns:
        User: Current admin user

    Raises:
        HTTPException: 403 if user is not admin
    """
    # TODO: Implement admin role check when user roles are added
    # For now, this just returns the current user
    # Add logic like: if not current_user.is_admin:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Not enough permissions"
    #     )

    return current_user


# Type alias for admin user dependency
AdminUser = Annotated[User, Depends(get_admin_user)]


async def get_db_session_direct() -> AsyncSession:
    """
    Direct database session dependency (for background tasks, etc.)

    Returns:
        AsyncSession: Database session

    Note:
        This is for cases where you need to manage the session lifecycle manually
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {str(e)}")
            await session.rollback()
            raise
        finally:
            await session.close()


def get_bearer_token() -> str:
    """
    Helper function to extract and validate bearer token from headers

    Args:
        credentials: HTTPAuthorizationCredentials

    Returns:
        str: JWT token

    Raises:
        HTTPException: If token format is invalid
    """
    return "placeholder"