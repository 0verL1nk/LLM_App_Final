"""
Task workers module for the LLM App.

This module contains task functions that are executed by RQ workers
in the background for long-running operations.
"""

import os
import sys

# Add project root to path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


from ..api.llm_client import LLMClient
from ..core.database import DatabaseManager
from ..core.file_handler import FileHandler
from ..core.text_processor import TextProcessor


def task_text_extraction(
    task_id: str, file_path: str, uid: str, user_uuid: str
) -> tuple[bool, str]:
    """Execute text extraction task asynchronously.

    Args:
        task_id: Task identifier
        file_path: Path to file
        uid: File UID
        user_uuid: User UUID

    Returns:
        Tuple of (success, message)
    """
    try:
        from ..queue.task_queue import TaskQueueManager, TaskStatus

        # Initialize task queue manager
        task_manager = TaskQueueManager()
        task_manager.update_task_status(task_id, TaskStatus.STARTED)

        # Get database and file handler
        db = DatabaseManager()
        file_handler = FileHandler(db)
        text_processor = TextProcessor(db, file_handler)

        # Get user's API key and model
        api_key = db.get_user_api_key(user_uuid)
        if not api_key:
            task_manager.update_task_status(
                task_id, TaskStatus.FAILED, error_message="请先在设置中配置您的 API Key"
            )
            return False, "请先在设置中配置您的 API Key"

        model_name = db.get_user_model_name(user_uuid)

        # Create LLM client
        llm_client = LLMClient(api_key, model_name)
        text_processor.set_llm_client(llm_client)

        # Extract text
        success, error_msg, extracted_data = text_processor.text_extraction(
            file_path, uid
        )

        if not success:
            task_manager.update_task_status(
                task_id, TaskStatus.FAILED, error_message=error_msg
            )
            return False, error_msg

        task_manager.update_task_status(task_id, TaskStatus.FINISHED)
        return True, "文本提取完成"

    except Exception as e:
        from ..queue.task_queue import TaskQueueManager, TaskStatus

        task_manager = TaskQueueManager()
        task_manager.update_task_status(
            task_id, TaskStatus.FAILED, error_message=str(e)
        )
        return False, str(e)


def task_file_summary(
    task_id: str, file_path: str, uid: str, user_uuid: str
) -> tuple[bool, str]:
    """Execute file summary task asynchronously.

    Args:
        task_id: Task identifier
        file_path: Path to file
        uid: File UID
        user_uuid: User UUID

    Returns:
        Tuple of (success, message)
    """
    try:
        from ..queue.task_queue import TaskQueueManager, TaskStatus

        # Initialize task queue manager
        task_manager = TaskQueueManager()
        task_manager.update_task_status(task_id, TaskStatus.STARTED)

        # Get database and file handler
        db = DatabaseManager()
        file_handler = FileHandler(db)
        text_processor = TextProcessor(db, file_handler)

        # Get user's API key and model
        api_key = db.get_user_api_key(user_uuid)
        if not api_key:
            task_manager.update_task_status(
                task_id, TaskStatus.FAILED, error_message="请先在设置中配置您的 API Key"
            )
            return False, "请先在设置中配置您的 API Key"

        model_name = db.get_user_model_name(user_uuid)

        # Create LLM client
        llm_client = LLMClient(api_key, model_name)
        text_processor.set_llm_client(llm_client)

        # Generate summary
        success, summary = text_processor.file_summary(file_path, uid)

        if not success:
            task_manager.update_task_status(
                task_id, TaskStatus.FAILED, error_message=summary
            )
            return False, summary

        task_manager.update_task_status(task_id, TaskStatus.FINISHED)
        return True, "文件总结完成"

    except Exception as e:
        from ..queue.task_queue import TaskQueueManager, TaskStatus

        task_manager = TaskQueueManager()
        task_manager.update_task_status(
            task_id, TaskStatus.FAILED, error_message=str(e)
        )
        return False, str(e)


def task_generate_mindmap(
    task_id: str, file_path: str, uid: str, user_uuid: str
) -> tuple[bool, str]:
    """Execute mindmap generation task asynchronously.

    Args:
        task_id: Task identifier
        file_path: Path to file
        uid: File UID
        user_uuid: User UUID

    Returns:
        Tuple of (success, message)
    """
    try:
        from ..queue.task_queue import TaskQueueManager, TaskStatus

        # Initialize task queue manager
        task_manager = TaskQueueManager()
        task_manager.update_task_status(task_id, TaskStatus.STARTED)

        # Get database and file handler
        db = DatabaseManager()
        file_handler = FileHandler(db)
        text_processor = TextProcessor(db, file_handler)

        # Get user's API key and model
        api_key = db.get_user_api_key(user_uuid)
        if not api_key:
            task_manager.update_task_status(
                task_id, TaskStatus.FAILED, error_message="请先在设置中配置您的 API Key"
            )
            return False, "请先在设置中配置您的 API Key"

        model_name = db.get_user_model_name(user_uuid)

        # Create LLM client
        llm_client = LLMClient(api_key, model_name)
        text_processor.set_llm_client(llm_client)

        # Generate mindmap
        success, message, mindmap_data = text_processor.generate_mindmap(file_path, uid)

        if not success:
            task_manager.update_task_status(
                task_id, TaskStatus.FAILED, error_message=message
            )
            return False, message

        task_manager.update_task_status(task_id, TaskStatus.FINISHED)
        return True, "思维导图生成完成"

    except Exception as e:
        from ..queue.task_queue import TaskQueueManager, TaskStatus

        task_manager = TaskQueueManager()
        task_manager.update_task_status(
            task_id, TaskStatus.FAILED, error_message=str(e)
        )
        return False, str(e)
