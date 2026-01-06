"""
Task service for managing async task operations.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from llm_app.models.task import Task
from llm_app.models.file import File
from llm_app.schemas.task import TaskType, TaskStatus
from llm_app.core.logger import get_logger

logger = get_logger(__name__)


class TaskService:
    """Service for task management operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(
        self,
        user_uuid: str,
        file_id: str,
        task_type: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """
        Create a new async task.

        Args:
            user_uuid: User's UUID
            file_id: File ID to process
            task_type: Type of task (extract, summarize, qa, rewrite, mindmap)
            options: Task-specific options

        Returns:
            Created Task object
        """
        # Verify file exists and belongs to user
        file_query = select(File).where(
            and_(File.id == file_id, File.user_uuid == user_uuid)
        )
        result = await self.db.execute(file_query)
        file = result.scalar_one_or_none()

        if not file:
            raise ValueError(f"File not found: {file_id}")

        # Create task
        task = Task(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            user_uuid=user_uuid,
            file_id=file_id,
            status="pending",
            progress=0,
            result={"options": options} if options else None,
        )

        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        logger.info(
            f"Created task {task.task_id} for file {file_id}, type: {task_type}"
        )

        return task

    async def get_task(
        self,
        task_id: str,
        user_uuid: str,
    ) -> Optional[Task]:
        """
        Get task by ID for a specific user.

        Args:
            task_id: Task ID
            user_uuid: User's UUID

        Returns:
            Task object or None if not found
        """
        query = select(Task).where(
            and_(Task.task_id == task_id, Task.user_uuid == user_uuid)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_task_status(
        self,
        task_id: str,
        user_uuid: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get task status with result.

        Args:
            task_id: Task ID
            user_uuid: User's UUID

        Returns:
            Task status dict or None if not found
        """
        task = await self.get_task(task_id, user_uuid)
        if not task:
            return None

        return {
            "task_id": task.task_id,
            "file_id": task.file_id,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "result": task.result,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "completed_at": task.completed_at,
        }

    async def update_task_status(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Optional[Task]:
        """
        Update task status and progress.

        Args:
            task_id: Task ID
            status: New status
            progress: Progress percentage (0-100)
            result: Task result data
            error_message: Error message if failed
            job_id: RQ job ID

        Returns:
            Updated Task object or None if not found
        """
        query = select(Task).where(Task.task_id == task_id)
        result_obj = await self.db.execute(query)
        task = result_obj.scalar_one_or_none()

        if not task:
            return None

        if status is not None:
            task.status = status
            if status == "processing" and task.started_at is None:
                task.started_at = datetime.utcnow()
            elif status in ["completed", "failed", "cancelled"]:
                task.completed_at = datetime.utcnow()

        if progress is not None:
            task.progress = min(100, max(0, progress))

        if result is not None:
            # Merge with existing result if present
            if task.result:
                task.result = {**task.result, **result}
            else:
                task.result = result

        if error_message is not None:
            task.error_message = error_message

        if job_id is not None:
            task.job_id = job_id

        task.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(task)

        logger.info(
            f"Updated task {task_id}: status={status}, progress={progress}"
        )

        return task

    async def list_tasks(
        self,
        user_uuid: str,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Task], int]:
        """
        List tasks for a user with optional filtering.

        Args:
            user_uuid: User's UUID
            status: Filter by status
            task_type: Filter by task type
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (list of tasks, total count)
        """
        # Build base query
        conditions = [Task.user_uuid == user_uuid]

        if status:
            conditions.append(Task.status == status)
        if task_type:
            conditions.append(Task.task_type == task_type)

        # Count total
        count_query = select(func.count(Task.task_id)).where(and_(*conditions))
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        offset = (page - 1) * page_size
        query = (
            select(Task)
            .where(and_(*conditions))
            .order_by(Task.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        return list(tasks), total

    async def cancel_task(
        self,
        task_id: str,
        user_uuid: str,
    ) -> bool:
        """
        Cancel a running or pending task.

        Args:
            task_id: Task ID
            user_uuid: User's UUID

        Returns:
            True if cancelled, False if not found or already completed
        """
        task = await self.get_task(task_id, user_uuid)

        if not task:
            return False

        if task.status in ["completed", "failed", "cancelled"]:
            return False

        task.status = "cancelled"
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()

        await self.db.commit()

        logger.info(f"Cancelled task {task_id}")

        return True

    async def get_existing_extraction(
        self,
        file_id: str,
        user_uuid: str,
    ) -> Optional[Task]:
        """
        Get existing completed extraction task for a file.

        Args:
            file_id: File ID
            user_uuid: User's UUID

        Returns:
            Completed extraction task or None
        """
        query = select(Task).where(
            and_(
                Task.file_id == file_id,
                Task.user_uuid == user_uuid,
                Task.task_type == "extract",
                Task.status == "completed",
            )
        ).order_by(Task.completed_at.desc())

        result = await self.db.execute(query)
        return result.scalar_one_or_none()
