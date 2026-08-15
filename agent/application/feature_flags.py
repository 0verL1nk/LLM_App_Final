"""Cohort-scoped feature flags for the durable research runtime.

``DURABLE_AGENT_TASKS_ENABLED`` gates new delegation capability (the
``delegate_task`` tool and the continuation machinery it feeds). Resolution:

1. Environment ``DURABLE_AGENT_TASKS_ENABLED=true|1|yes|on`` enables the flag
   for every scope; ``false|0|no|off`` disables it everywhere (kill switch).
2. Without an env setting the flag is off by default, and per-project or
   per-user overrides stored in ``agent_feature_flags`` may enable it.

The flag only hides the tool from newly built agent sessions. Already persisted
tasks, continuations and their workers always finish or cancel from the durable
tables, so disabling never requires a deployment rollback.
"""

from __future__ import annotations

import os

from ..adapters.orm.feature_flag_repository import read_feature_flag

DURABLE_AGENT_TASKS_FLAG = "DURABLE_AGENT_TASKS_ENABLED"
_TRUTHY = ("1", "true", "yes", "on")
_FALSY = ("0", "false", "no", "off")


def durable_agent_tasks_enabled(
    *,
    user_uuid: str | None = None,
    project_uid: str | None = None,
    db_name: str = "./database.sqlite",
) -> bool:
    """Resolve the durable delegation flag for one user/project scope."""
    override = _env_override(DURABLE_AGENT_TASKS_FLAG)
    if override is not None:
        return override
    if project_uid and project_uid.strip():
        project_value = read_feature_flag(
            flag_name=DURABLE_AGENT_TASKS_FLAG,
            scope_type="project",
            scope_id=project_uid,
            db_name=db_name,
        )
        if project_value is not None:
            return project_value
    if user_uuid and user_uuid.strip():
        user_value = read_feature_flag(
            flag_name=DURABLE_AGENT_TASKS_FLAG,
            scope_type="user",
            scope_id=user_uuid,
            db_name=db_name,
        )
        if user_value is not None:
            return user_value
    return False


def _env_override(name: str) -> bool | None:
    value = os.getenv(name, "").strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    return None


__all__ = ["DURABLE_AGENT_TASKS_FLAG", "durable_agent_tasks_enabled"]
