"""Cohort-scoped DURABLE_AGENT_TASKS_ENABLED flag resolution and storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.adapters.orm.feature_flag_repository import (
    clear_feature_flag,
    list_feature_flags,
    read_feature_flag,
    set_feature_flag,
)
from agent.application.feature_flags import DURABLE_AGENT_TASKS_FLAG, durable_agent_tasks_enabled


@pytest.fixture(autouse=True)
def _no_flag_env(monkeypatch) -> None:
    monkeypatch.delenv(DURABLE_AGENT_TASKS_FLAG, raising=False)


def test_flag_defaults_off_without_env_or_overrides(tmp_path: Path) -> None:
    database = str(tmp_path / "flags.sqlite")

    assert not durable_agent_tasks_enabled(user_uuid="user-1", project_uid="project-1", db_name=database)
    assert not durable_agent_tasks_enabled(db_name=database)


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "TRUE"])
def test_env_enables_flag_for_every_scope(monkeypatch, tmp_path: Path, value: str) -> None:
    monkeypatch.setenv(DURABLE_AGENT_TASKS_FLAG, value)

    assert durable_agent_tasks_enabled(db_name=str(tmp_path / "unused.sqlite"))


def test_env_kill_switch_overrides_stored_enablers(monkeypatch, tmp_path: Path) -> None:
    database = str(tmp_path / "flags.sqlite")
    set_feature_flag(
        flag_name=DURABLE_AGENT_TASKS_FLAG,
        scope_type="user",
        scope_id="user-1",
        enabled=True,
        db_name=database,
    )
    monkeypatch.setenv(DURABLE_AGENT_TASKS_FLAG, "false")

    assert not durable_agent_tasks_enabled(user_uuid="user-1", db_name=database)


def test_project_and_user_overrides_enable_the_flag(tmp_path: Path) -> None:
    database = str(tmp_path / "flags.sqlite")
    set_feature_flag(
        flag_name=DURABLE_AGENT_TASKS_FLAG,
        scope_type="project",
        scope_id="project-1",
        enabled=True,
        db_name=database,
    )

    assert durable_agent_tasks_enabled(user_uuid="user-1", project_uid="project-1", db_name=database)
    assert durable_agent_tasks_enabled(project_uid="project-1", db_name=database)

    set_feature_flag(
        flag_name=DURABLE_AGENT_TASKS_FLAG,
        scope_type="user",
        scope_id="user-2",
        enabled=True,
        db_name=database,
    )
    assert durable_agent_tasks_enabled(user_uuid="user-2", project_uid="project-2", db_name=database)


def test_project_override_takes_precedence_over_user_override(tmp_path: Path) -> None:
    database = str(tmp_path / "flags.sqlite")
    set_feature_flag(
        flag_name=DURABLE_AGENT_TASKS_FLAG, scope_type="user", scope_id="user-1", enabled=True, db_name=database
    )
    set_feature_flag(
        flag_name=DURABLE_AGENT_TASKS_FLAG, scope_type="project", scope_id="project-1", enabled=False, db_name=database
    )

    assert not durable_agent_tasks_enabled(user_uuid="user-1", project_uid="project-1", db_name=database)
    assert durable_agent_tasks_enabled(user_uuid="user-1", project_uid="project-2", db_name=database)


def test_cleared_override_falls_back_to_default_off(tmp_path: Path) -> None:
    database = str(tmp_path / "flags.sqlite")
    set_feature_flag(
        flag_name=DURABLE_AGENT_TASKS_FLAG, scope_type="user", scope_id="user-1", enabled=True, db_name=database
    )
    assert clear_feature_flag(
        flag_name=DURABLE_AGENT_TASKS_FLAG, scope_type="user", scope_id="user-1", db_name=database
    )
    assert not clear_feature_flag(
        flag_name=DURABLE_AGENT_TASKS_FLAG, scope_type="user", scope_id="user-1", db_name=database
    )
    assert not durable_agent_tasks_enabled(user_uuid="user-1", db_name=database)


def test_repository_rejects_invalid_scopes(tmp_path: Path) -> None:
    database = str(tmp_path / "flags.sqlite")
    with pytest.raises(ValueError):
        set_feature_flag(
            flag_name=DURABLE_AGENT_TASKS_FLAG, scope_type="session", scope_id="s-1", enabled=True, db_name=database
        )
    with pytest.raises(ValueError):
        set_feature_flag(flag_name="", scope_type="user", scope_id="u-1", enabled=True, db_name=database)
    with pytest.raises(ValueError):
        set_feature_flag(flag_name=DURABLE_AGENT_TASKS_FLAG, scope_type="user", scope_id="", enabled=True, db_name=database)


def test_list_feature_flags_reports_overrides_for_audits(tmp_path: Path) -> None:
    database = str(tmp_path / "flags.sqlite")
    set_feature_flag(
        flag_name=DURABLE_AGENT_TASKS_FLAG, scope_type="project", scope_id="project-1", enabled=True, db_name=database
    )
    set_feature_flag(
        flag_name=DURABLE_AGENT_TASKS_FLAG, scope_type="user", scope_id="user-1", enabled=False, db_name=database
    )

    overrides = list_feature_flags(flag_name=DURABLE_AGENT_TASKS_FLAG, db_name=database)

    assert overrides == [
        {"flag_name": DURABLE_AGENT_TASKS_FLAG, "scope_type": "project", "scope_id": "project-1", "enabled": True},
        {"flag_name": DURABLE_AGENT_TASKS_FLAG, "scope_type": "user", "scope_id": "user-1", "enabled": False},
    ]
    assert read_feature_flag(
        flag_name=DURABLE_AGENT_TASKS_FLAG, scope_type="user", scope_id="user-9", db_name=database
    ) is None
