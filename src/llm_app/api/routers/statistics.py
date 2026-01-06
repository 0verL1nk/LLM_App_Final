"""
Statistics API router for usage metrics and monitoring.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from llm_app.api.deps import get_db, get_current_user
from llm_app.models.user import User
from llm_app.services.statistics_service import StatisticsService
from llm_app.schemas.statistics import StatisticsResponse, StatisticsSummary
from llm_app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="Get user statistics",
    description="Get complete usage statistics for the current user",
)
async def get_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get complete statistics for the authenticated user."""
    service = StatisticsService(db)
    stats = await service.get_statistics(current_user.uuid)

    return {
        "success": True,
        "data": stats,
    }


@router.get(
    "/summary",
    response_model=Dict[str, Any],
    summary="Get statistics summary",
    description="Get a quick summary of user statistics",
)
async def get_statistics_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a quick summary of statistics for the authenticated user."""
    service = StatisticsService(db)
    summary = await service.get_statistics_summary(current_user.uuid)

    return {
        "success": True,
        "data": summary,
    }


@router.get(
    "/files",
    response_model=Dict[str, Any],
    summary="Get file statistics",
    description="Get file-related statistics for the current user",
)
async def get_file_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get file statistics for the authenticated user."""
    service = StatisticsService(db)
    file_stats = await service.calculate_file_stats(current_user.uuid)

    return {
        "success": True,
        "data": file_stats,
    }


@router.get(
    "/tasks",
    response_model=Dict[str, Any],
    summary="Get task statistics",
    description="Get task-related statistics for the current user",
)
async def get_task_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get task statistics for the authenticated user."""
    service = StatisticsService(db)
    task_stats = await service.calculate_task_stats(current_user.uuid)
    task_breakdown = await service.calculate_task_breakdown(current_user.uuid)

    return {
        "success": True,
        "data": {
            "task_stats": task_stats,
            "task_breakdown": task_breakdown,
        },
    }
