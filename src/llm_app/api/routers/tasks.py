"""
Tasks API router for task management and monitoring.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from llm_app.api.deps import get_db, get_current_user
from llm_app.models.user import User
from llm_app.services.task_service import TaskService
from llm_app.schemas.task import TaskStatusResponse, TaskListResponse, TaskListItem
from llm_app.core.logger import get_logger
from llm_app.core.exceptions import APIException

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get(
    "",
    response_model=Dict[str, Any],
    summary="List user tasks",
    description="Get paginated list of user's tasks with optional filtering",
)
async def list_tasks(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status (pending, processing, completed, failed, cancelled)",
    ),
    task_type: Optional[str] = Query(
        None,
        description="Filter by task type (extract, summarize, qa, rewrite, mindmap)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all tasks for the current user.

    Supports filtering by status and task type, with pagination.
    """
    task_service = TaskService(db)

    tasks, total = await task_service.list_tasks(
        user_uuid=current_user.uuid,
        status=status_filter,
        task_type=task_type,
        page=page,
        page_size=page_size,
    )

    total_pages = (total + page_size - 1) // page_size

    items = [
        {
            "task_id": task.task_id,
            "file_id": task.file_id,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "completed_at": task.completed_at,
        }
        for task in tasks
    ]

    return {
        "success": True,
        "data": {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
        },
    }


@router.get(
    "/{task_id}",
    response_model=Dict[str, Any],
    summary="Get task status",
    description="Get detailed status and result for a specific task",
)
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the status and result of a specific task.

    Returns task details including progress, result (if completed), and error message (if failed).
    """
    task_service = TaskService(db)

    task_status = await task_service.get_task_status(
        task_id=task_id,
        user_uuid=current_user.uuid,
    )

    if not task_status:
        raise APIException(
            error_code="TASK_NOT_FOUND",
            message=f"任务不存在: {task_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return {
        "success": True,
        "data": task_status,
    }


@router.post(
    "/{task_id}/cancel",
    response_model=Dict[str, Any],
    summary="Cancel a task",
    description="Cancel a pending or running task",
)
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a pending or running task.

    Returns success if the task was cancelled, or an error if the task
    is already completed or doesn't exist.
    """
    task_service = TaskService(db)

    # First check if task exists
    task = await task_service.get_task(task_id, current_user.uuid)
    if not task:
        raise APIException(
            error_code="TASK_NOT_FOUND",
            message=f"任务不存在: {task_id}",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if task.status in ["completed", "failed", "cancelled"]:
        raise APIException(
            error_code="TASK_ALREADY_COMPLETED",
            message=f"任务已完成，无法取消",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Cancel the task
    success = await task_service.cancel_task(task_id, current_user.uuid)

    if not success:
        raise APIException(
            error_code="TASK_CANCEL_FAILED",
            message="取消任务失败",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # TODO: Also cancel the RQ job if running
    # if task.job_id:
    #     try:
    #         from rq import cancel_job
    #         cancel_job(task.job_id, connection=redis_conn)
    #     except Exception as e:
    #         logger.warning(f"Failed to cancel RQ job {task.job_id}: {e}")

    return {
        "success": True,
        "message": "任务已取消",
        "data": {
            "task_id": task_id,
            "status": "cancelled",
        },
    }
