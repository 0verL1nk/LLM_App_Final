"""
Redis Queue (RQ) task queue setup and management
"""
from typing import Optional
from redis import Redis
from rq import Queue
from rq.exceptions import NoSuchJobError

from llm_app.core.config import settings


# Redis connection
redis_conn = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    password=settings.redis_password,
    decode_responses=True,
)

# Main task queue
task_queue = Queue(
    "tasks",
    connection=redis_conn,
    default_timeout=settings.rq_default_timeout,
)


def get_queue(queue_name: str = "tasks") -> Queue:
    """
    Get a task queue by name

    Args:
        queue_name: Name of the queue

    Returns:
        RQ Queue instance
    """
    return Queue(queue_name, connection=redis_conn)


def enqueue_task(
    func,
    *args,
    queue_name: str = "tasks",
    timeout: Optional[int] = None,
    **kwargs
):
    """
    Enqueue a task to the specified queue

    Args:
        func: Function to execute
        *args: Positional arguments for the function
        queue_name: Name of the queue
        timeout: Task timeout in seconds
        **kwargs: Keyword arguments for the function

    Returns:
        RQ Job instance
    """
    queue = get_queue(queue_name)
    return queue.enqueue(
        func,
        *args,
        timeout=timeout or settings.rq_default_timeout,
        **kwargs
    )


def get_job(job_id: str) -> Optional[object]:
    """
    Get a job by ID

    Args:
        job_id: Job ID

    Returns:
        RQ Job instance or None if not found
    """
    try:
        return task_queue.fetch_job(job_id)
    except NoSuchJobError:
        return None


def cancel_job(job_id: str) -> bool:
    """
    Cancel a running job

    Args:
        job_id: Job ID to cancel

    Returns:
        True if cancelled, False if not found or already completed
    """
    job = get_job(job_id)
    if job and job.get_status() in ["queued", "started"]:
        job.cancel()
        return True
    return False


def get_queue_stats(queue_name: str = "tasks") -> dict:
    """
    Get queue statistics

    Args:
        queue_name: Name of the queue

    Returns:
        Dictionary with queue statistics
    """
    queue = get_queue(queue_name)
    return {
        "size": len(queue),
        "started_jobs": len(queue.started_job_registry),
        "finished_jobs": len(queue.finished_job_registry),
        "failed_jobs": len(queue.failed_job_registry),
    }