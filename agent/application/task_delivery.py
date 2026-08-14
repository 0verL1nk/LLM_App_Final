"""Configured transport trigger for already-persisted durable tasks."""

from __future__ import annotations

import os
from typing import Any


def dispatch_task(*, task_uid: str) -> dict[str, Any] | None:
    """Optionally nudge local delivery; the durable outbox remains authoritative.

    ``outbox`` is the production setting: API processes do not start work, and
    the independently supervised outbox worker polls the task record. ``local``
    preserves desktop/development responsiveness without changing task ownership.
    """
    mode = os.getenv("PAPERSAGE_TASK_TRANSPORT", "local").strip().lower()
    if mode == "outbox":
        return None
    if mode != "local":
        raise ValueError("PAPERSAGE_TASK_TRANSPORT must be 'local' or 'outbox'")
    from utils.task_queue import enqueue_background_task

    from .task_worker_host import execute_registered_task

    return enqueue_background_task(execute_registered_task, task_uid=task_uid)


__all__ = ["dispatch_task"]
