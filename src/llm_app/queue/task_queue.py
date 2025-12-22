"""
Task queue module for the LLM App.

This module provides asynchronous task processing using RQ (Redis Queue).
"""

import datetime
import sqlite3
from enum import Enum
from typing import Any, Dict, Optional

from redis import Redis
from rq import Queue
from rq.job import Job

from ..config import Config
from ..core.database import DatabaseManager


class TaskStatus(Enum):
    """Task status enumeration."""

    PENDING = "pending"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"
    QUEUED = "queued"


class TaskQueueManager:
    """Task queue manager for asynchronous processing."""

    def __init__(self) -> None:
        """Initialize task queue manager."""
        self.redis_conn = None
        self.task_queue = None
        self.db = DatabaseManager()

        # Check if Redis is enabled in config
        if Config.USE_REDIS:
            self.redis_conn = self._create_redis_connection()
            if self.redis_conn:
                self.task_queue = Queue("tasks", connection=self.redis_conn)
                # Successfully connected to Redis
            else:
                # Redis enabled but connection failed
                pass
        else:
            # Using memory-based mode (no Redis)
            pass

    def _create_redis_connection(self) -> Optional[Redis]:
        """Create Redis connection.

        Returns:
            Redis connection instance or None if connection fails
        """
        try:
            redis_conn = Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                password=Config.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            redis_conn.ping()
            return redis_conn
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            return None

    def init_task_table(self) -> None:
        """Initialize task status table."""
        self.db._init_task_table()

    def create_task(self, task_id: str, uid: str, content_type: str) -> None:
        """Create a new task record.

        Args:
            task_id: Unique task identifier
            uid: File UID
            content_type: Type of content (e.g., 'file_extraction')
        """
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            INSERT OR REPLACE INTO task_status
            (task_id, uid, content_type, status, created_at, updated_at, job_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                task_id,
                uid,
                content_type,
                TaskStatus.PENDING.value,
                current_time,
                current_time,
                None,
            ),
        )

        conn.commit()
        conn.close()

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        job_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update task status.

        Args:
            task_id: Task identifier
            status: New task status
            job_id: RQ job ID
            error_message: Error message if failed
        """
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if error_message:
            cursor.execute(
                """
                UPDATE task_status
                SET status = ?, updated_at = ?, error_message = ?, job_id = ?
                WHERE task_id = ?
            """,
                (status.value, current_time, error_message, job_id, task_id),
            )
        else:
            cursor.execute(
                """
                UPDATE task_status
                SET status = ?, updated_at = ?, job_id = ?
                WHERE task_id = ?
            """,
                (status.value, current_time, job_id, task_id),
            )

        conn.commit()
        conn.close()

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task status dictionary or None
        """
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT task_id, uid, content_type, status, created_at, updated_at, error_message, job_id
            FROM task_status
            WHERE task_id = ?
        """,
            (task_id,),
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return {
            "task_id": result[0],
            "uid": result[1],
            "content_type": result[2],
            "status": result[3],
            "created_at": result[4],
            "updated_at": result[5],
            "error_message": result[6],
            "job_id": result[7],
        }

    def get_task_status_by_uid(
        self, uid: str, content_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get latest task status by UID and content type.

        Args:
            uid: File UID
            content_type: Content type

        Returns:
            Task status dictionary or None
        """
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT task_id, uid, content_type, status, created_at, updated_at, error_message, job_id
            FROM task_status
            WHERE uid = ? AND content_type = ?
            ORDER BY created_at DESC
            LIMIT 1
        """,
            (uid, content_type),
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        return {
            "task_id": result[0],
            "uid": result[1],
            "content_type": result[2],
            "status": result[3],
            "created_at": result[4],
            "updated_at": result[5],
            "error_message": result[6],
            "job_id": result[7],
        }

    def get_job_status(self, job_id: str) -> Optional[str]:
        """Get job status from RQ.

        Args:
            job_id: RQ job ID

        Returns:
            Job status string or None
        """
        if not self.redis_conn or not job_id:
            return None

        try:
            job = Job.fetch(job_id, connection=self.redis_conn)
            return job.get_status()
        except Exception:
            return None

    def enqueue_task(
        self, task_func, *args, job_timeout: str = "10m", **kwargs
    ) -> Optional[str]:
        """Enqueue task to RQ queue.

        Args:
            task_func: Task function to execute
            *args: Positional arguments
            job_timeout: Job timeout
            **kwargs: Keyword arguments

        Returns:
            Job ID if successful (async mode) or "sync_execution" if synchronous
        """
        if not self.task_queue:
            # Synchronous execution when Redis is not available
            try:
                task_func(*args, **kwargs)
                return "sync_execution"
            except Exception:
                raise

        # Asynchronous execution with Redis
        try:
            job = self.task_queue.enqueue(
                task_func, *args, **kwargs, job_timeout=job_timeout
            )
            return job.id
        except Exception:
            # Fallback to synchronous execution
            try:
                task_func(*args, **kwargs)
                return "sync_execution"
            except Exception:
                raise

    def is_queue_available(self) -> bool:
        """Check if Redis queue is available.

        Returns:
            True if queue is available, False otherwise
        """
        return self.task_queue is not None

    def get_queue_mode(self) -> str:
        """Get the current queue mode.

        Returns:
            "redis" if using Redis, "memory" if using synchronous mode
        """
        return "redis" if self.task_queue else "memory"

    def get_redis_status(self) -> Dict[str, Any]:
        """Get Redis connection status.

        Returns:
            Dictionary with Redis connection status and config
        """
        return {
            "enabled": Config.USE_REDIS,
            "connected": self.redis_conn is not None,
            "mode": self.get_queue_mode(),
            "host": Config.REDIS_HOST,
            "port": Config.REDIS_PORT,
            "db": Config.REDIS_DB,
        }
