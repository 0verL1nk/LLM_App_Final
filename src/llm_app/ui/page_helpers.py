"""
Page helper module for the LLM App.

This module provides helper functions for Streamlit pages including
task queue management, API key checking, and UI utilities.
"""

import json
import uuid
from typing import Any, Dict, Optional, Tuple

import streamlit as st

from ..core.auth import AuthManager
from ..core.database import DatabaseManager
from ..queue.task_queue import TaskQueueManager, TaskStatus


def check_api_key_configured() -> Tuple[bool, Optional[str]]:
    """Check if API key is configured for the user.

    Returns:
        Tuple of (is_configured, error_message)
    """
    if "token" not in st.session_state or not st.session_state["token"]:
        return False, "请先登录"

    if "uuid" not in st.session_state or not st.session_state["uuid"]:
        auth = AuthManager()
        st.session_state["uuid"] = auth.get_uuid_by_token(st.session_state["token"])

    if not st.session_state.get("uuid"):
        return False, "无法获取用户信息"

    db = DatabaseManager()
    api_key = db.get_user_api_key(st.session_state["uuid"])
    if not api_key:
        return False, "请先在侧边栏设置中配置您的 API Key"

    return True, None


def start_async_task(
    uid: str, content_type: str, task_func: callable, *args: Any
) -> Optional[str]:
    """Start an asynchronous task.

    Args:
        uid: File UID
        content_type: Content type ('file_extraction', 'file_summary', 'file_mindmap')
        task_func: Task function to execute
        *args: Arguments to pass to task function

    Returns:
        Task ID if successful, None otherwise
    """
    try:
        # Check API key configuration
        is_configured, error_msg = check_api_key_configured()
        if not is_configured:
            st.warning(f"⚠️ {error_msg}")
            return None

        # Generate task ID
        task_id = str(uuid.uuid4())

        # Create task record
        task_manager = TaskQueueManager()
        task_manager.create_task(task_id, uid, content_type)

        # Get user UUID
        user_uuid = st.session_state["uuid"]

        # Enqueue task
        job_id = task_manager.enqueue_task(task_func, task_id, *args, user_uuid)

        if job_id:
            # Update task status to queued
            task_manager.update_task_status(task_id, TaskStatus.QUEUED, job_id=job_id)
            return task_id

        return None

    except Exception as e:
        st.error(f"启动任务失败: {e!s}")
        return None


def check_task_and_content(
    uid: str, content_type: str, auto_start: bool = False
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Check task status and content availability.

    Args:
        uid: File UID
        content_type: Content type
        auto_start: Whether to auto-start task if no content exists

    Returns:
        Tuple of (content_dict, task_status, task_id)
    """
    db = DatabaseManager()

    # Check if content already exists
    content = db.get_content_by_uid(uid, content_type)
    if content:
        try:
            if content_type == "file_summary":
                return {"summary": content}, None, None
            else:
                # file_extraction and file_mindmap are JSON format
                return json.loads(content), None, None
        except json.JSONDecodeError:
            return {"raw": content}, None, None

    # Check for running task
    task_manager = TaskQueueManager()
    task_info = task_manager.get_task_status_by_uid(uid, content_type)

    if task_info:
        task_status = task_info["status"]
        task_id = task_info["task_id"]

        # If task is finished, check content again (might be newly completed)
        if task_status == TaskStatus.FINISHED.value:
            content = db.get_content_by_uid(uid, content_type)
            if content:
                try:
                    if content_type == "file_summary":
                        return {"summary": content}, None, None
                    else:
                        return json.loads(content), None, None
                except json.JSONDecodeError:
                    return {"raw": content}, None, None

        # Check RQ job status
        if task_info.get("job_id"):
            rq_status = task_manager.get_job_status(task_info["job_id"])
            if rq_status:
                # Sync status
                if rq_status == "finished":
                    task_status = TaskStatus.FINISHED.value
                elif rq_status == "failed":
                    task_status = TaskStatus.FAILED.value
                elif rq_status == "started":
                    task_status = TaskStatus.STARTED.value

        return None, task_status, task_id

    # If no content and no task, and auto-start is enabled
    if auto_start:
        return None, None, None

    return None, None, None


def display_task_status(
    task_status: str, error_message: Optional[str] = None, auto_refresh: bool = True
) -> None:
    """Display task status in the UI.

    Args:
        task_status: Task status string
        error_message: Error message if any
        auto_refresh: Whether to auto-refresh the page
    """
    status_messages = {
        TaskStatus.PENDING.value: ("⏳", "任务等待中..."),
        TaskStatus.QUEUED.value: ("📋", "任务已加入队列，等待处理..."),
        TaskStatus.STARTED.value: ("🔄", "正在处理中，请稍候..."),
        TaskStatus.FINISHED.value: ("✅", "处理完成"),
        TaskStatus.FAILED.value: ("❌", f"处理失败: {error_message or '未知错误'}"),
    }

    icon, message = status_messages.get(task_status, ("❓", "未知状态"))

    if task_status == TaskStatus.FAILED.value:
        st.error(f"{icon} {message}")
    elif task_status in [
        TaskStatus.PENDING.value,
        TaskStatus.QUEUED.value,
        TaskStatus.STARTED.value,
    ]:
        st.info(f"{icon} {message}")
        # Auto-refresh page to check task status
        if auto_refresh:
            import time

            time.sleep(2)
            st.rerun()
    else:
        st.success(f"{icon} {message}")


def print_contents(content: Dict[str, Any]) -> None:
    """Print formatted contents to Streamlit.

    Args:
        content: Content dictionary to display
    """
    for key, value in content.items():
        st.write(f"### {key}\n")
        if isinstance(value, list):
            for item in value:
                st.write(f"- {item}\n")
        else:
            st.write(f"{value}\n")


def show_sidebar_api_key_setting() -> None:
    """Display API key setting in sidebar."""
    with st.sidebar:
        st.header("⚙️ 设置")

        if st.session_state.get("uuid"):
            db = DatabaseManager()
            api_key = db.get_user_api_key(st.session_state["uuid"])

            if not api_key:
                st.warning("请配置您的 API Key")
                new_api_key = st.text_input(
                    "DashScope API Key", type="password", key="api_key_input"
                )
                if st.button("保存 API Key"):
                    if new_api_key:
                        db.update_user_api_key(st.session_state["uuid"], new_api_key)
                        st.success("API Key 保存成功!")
                        st.rerun()
                    else:
                        st.error("请输入有效的 API Key")
            else:
                st.success("✅ API Key 已配置")

            # Model selection
            current_model = db.get_user_model_name(st.session_state["uuid"])
            new_model = st.selectbox(
                "选择模型",
                options=["qwen-max", "qwen-plus", "qwen-turbo"],
                index=["qwen-max", "qwen-plus", "qwen-turbo"].index(current_model),
                key="model_selector",
            )

            if new_model != current_model:
                # Update model preference
                import sqlite3

                conn = sqlite3.connect(db.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET model_name = ? WHERE uuid = ?",
                    (new_model, st.session_state["uuid"]),
                )
                conn.commit()
                conn.close()
                st.rerun()
