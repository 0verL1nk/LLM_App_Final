"""
Users API router for profile management and configuration.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_current_user
from models.user import User
from services.user_service import UserService
from schemas.user import (
    UserProfile,
    APIKeyUpdate,
    APIKeyUpdateResponse,
    PreferencesUpdate,
    PreferencesUpdateResponse,
)
from core.logger import get_logger
from core.exceptions import APIException

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=Dict[str, Any],
    summary="Get current user profile",
    description="Get the profile of the currently authenticated user",
)
async def get_user_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's profile information."""
    return {
        "success": True,
        "data": {
            "uuid": current_user.uuid,
            "username": current_user.username,
            "email": current_user.email,
            "has_api_key": current_user.has_api_key,
            "preferred_model": current_user.preferred_model,
            "created_at": current_user.created_at,
        },
    }


@router.put(
    "/api-key",
    response_model=Dict[str, Any],
    summary="Update API key",
    description="Update the user's DashScope API key",
)
async def update_api_key(
    request: APIKeyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the user's DashScope API key."""
    user_service = UserService(db)

    result = await user_service.update_api_key(
        user_uuid=current_user.uuid,
        api_key=request.api_key,
        validate=True,
    )

    if not result.get("success"):
        error_code = result.get("error_code", "API_KEY_UPDATE_FAILED")
        raise APIException(
            error_code=error_code,
            message=result.get("message", "Failed to update API key"),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return {
        "success": True,
        "data": {
            "message": result.get("message"),
            "api_key_configured": result.get("api_key_configured"),
        },
    }


@router.delete(
    "/api-key",
    response_model=Dict[str, Any],
    summary="Clear API key",
    description="Remove the user's DashScope API key",
)
async def clear_api_key(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear the user's DashScope API key."""
    user_service = UserService(db)

    result = await user_service.clear_api_key(user_uuid=current_user.uuid)

    if not result.get("success"):
        raise APIException(
            error_code="API_KEY_CLEAR_FAILED",
            message=result.get("message", "Failed to clear API key"),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return {
        "success": True,
        "data": {
            "message": result.get("message"),
            "api_key_configured": result.get("api_key_configured"),
        },
    }


@router.put(
    "/preferences",
    response_model=Dict[str, Any],
    summary="Update preferences",
    description="Update user preferences like preferred model",
)
async def update_preferences(
    request: PreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user preferences."""
    user_service = UserService(db)

    result = await user_service.update_preferences(
        user_uuid=current_user.uuid,
        preferred_model=request.preferred_model,
    )

    if not result.get("success"):
        error_code = result.get("error_code", "PREFERENCES_UPDATE_FAILED")
        raise APIException(
            error_code=error_code,
            message=result.get("message", "Failed to update preferences"),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return {
        "success": True,
        "data": {
            "message": result.get("message"),
            "preferred_model": result.get("preferred_model"),
        },
    }


@router.get(
    "/stats",
    response_model=Dict[str, Any],
    summary="Get user statistics",
    description="Get statistics about user's files and tasks",
)
async def get_user_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user statistics including file and task counts."""
    user_service = UserService(db)

    result = await user_service.get_user_stats(user_uuid=current_user.uuid)

    if not result.get("success"):
        raise APIException(
            error_code="STATS_FETCH_FAILED",
            message=result.get("message", "Failed to fetch statistics"),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return {
        "success": True,
        "data": result.get("data"),
    }
