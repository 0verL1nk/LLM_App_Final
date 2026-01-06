"""
Statistics service for calculating and aggregating usage metrics.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from llm_app.models.file import File
from llm_app.models.task import Task
from llm_app.models.user import User
from llm_app.core.logger import get_logger

logger = get_logger(__name__)


class StatisticsService:
    """Service for calculating user statistics"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_file_stats(self, user_uuid: str) -> Dict[str, Any]:
        """Calculate file statistics for a user"""
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_query = (
            select(func.count()).select_from(File).where(File.user_uuid == user_uuid)
        )
        total_result = await self.db.execute(total_query)
        total_files = total_result.scalar() or 0

        processed_query = (
            select(func.count())
            .select_from(File)
            .where(
                File.user_uuid == user_uuid,
                File.status == "processed",
            )
        )
        processed_result = await self.db.execute(processed_query)
        processed_files = processed_result.scalar() or 0

        processing_query = (
            select(func.count())
            .select_from(File)
            .where(
                File.user_uuid == user_uuid,
                File.status == "processing",
            )
        )
        processing_result = await self.db.execute(processing_query)
        processing_files = processing_result.scalar() or 0

        pending_query = (
            select(func.count())
            .select_from(File)
            .where(
                File.user_uuid == user_uuid,
                File.status == "pending",
            )
        )
        pending_result = await self.db.execute(pending_query)
        pending_files = pending_result.scalar() or 0

        failed_query = (
            select(func.count())
            .select_from(File)
            .where(
                File.user_uuid == user_uuid,
                File.status == "failed",
            )
        )
        failed_result = await self.db.execute(failed_query)
        failed_files = failed_result.scalar() or 0

        month_query = (
            select(func.count())
            .select_from(File)
            .where(
                File.user_uuid == user_uuid,
                File.created_at >= month_start,
            )
        )
        month_result = await self.db.execute(month_query)
        files_this_month = month_result.scalar() or 0

        size_query = select(func.sum(File.file_size)).where(File.user_uuid == user_uuid)
        size_result = await self.db.execute(size_query)
        total_size_bytes = size_result.scalar() or 0

        return {
            "total_files": total_files,
            "processed_files": processed_files,
            "processing_files": processing_files,
            "pending_files": pending_files,
            "failed_files": failed_files,
            "files_this_month": files_this_month,
            "total_size_bytes": total_size_bytes,
        }

    async def calculate_usage_stats(self, user_uuid: str) -> Dict[str, Any]:
        """Calculate API usage statistics for a user"""
        return {
            "total_api_calls": 0,
            "total_tokens": 0,
            "api_calls_this_month": 0,
            "tokens_this_month": 0,
            "average_response_time_ms": 0.0,
        }

    async def calculate_task_stats(self, user_uuid: str) -> Dict[str, Any]:
        """Calculate task statistics for a user"""
        total_query = (
            select(func.count()).select_from(Task).where(Task.user_uuid == user_uuid)
        )
        total_result = await self.db.execute(total_query)
        total_tasks = total_result.scalar() or 0

        completed_query = (
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_uuid == user_uuid,
                Task.status == "completed",
            )
        )
        completed_result = await self.db.execute(completed_query)
        completed_tasks = completed_result.scalar() or 0

        pending_query = (
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_uuid == user_uuid,
                Task.status == "pending",
            )
        )
        pending_result = await self.db.execute(pending_query)
        pending_tasks = pending_result.scalar() or 0

        processing_query = (
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_uuid == user_uuid,
                Task.status == "processing",
            )
        )
        processing_result = await self.db.execute(processing_query)
        processing_tasks = processing_result.scalar() or 0

        failed_query = (
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_uuid == user_uuid,
                Task.status == "failed",
            )
        )
        failed_result = await self.db.execute(failed_query)
        failed_tasks = failed_result.scalar() or 0

        cancelled_query = (
            select(func.count())
            .select_from(Task)
            .where(
                Task.user_uuid == user_uuid,
                Task.status == "cancelled",
            )
        )
        cancelled_result = await self.db.execute(cancelled_query)
        cancelled_tasks = cancelled_result.scalar() or 0

        avg_time_query = select(
            func.avg(
                func.julianday(Task.completed_at) - func.julianday(Task.created_at)
            )
        ).where(
            Task.user_uuid == user_uuid,
            Task.status == "completed",
            Task.completed_at.isnot(None),
        )
        avg_time_result = await self.db.execute(avg_time_query)
        avg_days = avg_time_result.scalar()
        average_completion_time_seconds = (avg_days * 86400) if avg_days else 0.0

        finished_tasks = completed_tasks + failed_tasks
        success_rate = (
            (completed_tasks / finished_tasks * 100) if finished_tasks > 0 else 0.0
        )

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "processing_tasks": processing_tasks,
            "failed_tasks": failed_tasks,
            "cancelled_tasks": cancelled_tasks,
            "average_completion_time_seconds": round(
                average_completion_time_seconds, 2
            ),
            "success_rate": round(success_rate, 2),
        }

    async def calculate_task_breakdown(self, user_uuid: str) -> Dict[str, int]:
        """Calculate task breakdown by type"""
        task_types = ["extract", "summarize", "qa", "rewrite", "mindmap"]
        breakdown = {}

        for task_type in task_types:
            query = (
                select(func.count())
                .select_from(Task)
                .where(
                    Task.user_uuid == user_uuid,
                    Task.task_type == task_type,
                )
            )
            result = await self.db.execute(query)
            breakdown[task_type] = result.scalar() or 0

        return breakdown

    async def get_statistics(self, user_uuid: str) -> Dict[str, Any]:
        """Get complete statistics for a user"""
        file_stats = await self.calculate_file_stats(user_uuid)
        usage_stats = await self.calculate_usage_stats(user_uuid)
        task_stats = await self.calculate_task_stats(user_uuid)
        task_breakdown = await self.calculate_task_breakdown(user_uuid)

        return {
            "user_uuid": user_uuid,
            "file_stats": file_stats,
            "usage_stats": usage_stats,
            "task_stats": task_stats,
            "task_breakdown": task_breakdown,
            "last_updated": datetime.utcnow(),
        }

    async def get_statistics_summary(self, user_uuid: str) -> Dict[str, Any]:
        """Get a quick summary of statistics"""
        file_stats = await self.calculate_file_stats(user_uuid)
        task_stats = await self.calculate_task_stats(user_uuid)

        return {
            "total_files": file_stats["total_files"],
            "total_tasks": task_stats["total_tasks"],
            "completed_tasks": task_stats["completed_tasks"],
            "success_rate": task_stats["success_rate"],
        }
