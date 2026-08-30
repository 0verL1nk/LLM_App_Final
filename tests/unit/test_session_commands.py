"""Session slash command use case tests (skills listing + manual compact)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agent.application import session_commands
from agent.application.session_commands import (
    SessionCommandConflict,
    SessionCommandError,
    execute_session_command,
    format_skills_reply,
    list_skill_catalog,
)
from agent.skills.loader import SkillMetadata

PROJECT = "p1"
SESSION = "s1"
USER = "u1"


class _FakeModel:
    def __init__(self, content: str = "这是压缩后的会话摘要。") -> None:
        self.content = content
        self.calls: list[list[dict[str, str]]] = []

    def invoke(self, messages: list[dict[str, str]]) -> Any:
        self.calls.append(messages)
        return type("Response", (), {"content": self.content})()


def _patch_membership(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_commands, "require_project", lambda **_kwargs: {"uid": PROJECT})
    monkeypatch.setattr(
        session_commands,
        "list_project_sessions",
        lambda **_kwargs: [{"session_uid": SESSION, "project_uid": PROJECT}],
    )


def _patch_storage(monkeypatch: pytest.MonkeyPatch, initial: list[dict[str, str]]) -> dict[str, Any]:
    state: dict[str, Any] = {"messages": [dict(item) for item in initial], "saves": []}

    def _list(**_kwargs: Any) -> list[dict[str, str]]:
        return [dict(item) for item in state["messages"]]

    def _save(*, messages: list[dict[str, str]], **_kwargs: Any) -> None:
        state["saves"].append([dict(item) for item in messages])
        state["messages"] = [dict(item) for item in messages]

    monkeypatch.setattr(session_commands, "list_project_session_messages", _list)
    monkeypatch.setattr(session_commands, "save_project_session_messages", _save)
    return state


def _patch_model(monkeypatch: pytest.MonkeyPatch, model: _FakeModel) -> None:
    monkeypatch.setattr(session_commands, "read_api_key_for_user", lambda **_kwargs: "key")
    monkeypatch.setattr(session_commands, "read_model_name_for_user", lambda **_kwargs: "gpt-test")
    monkeypatch.setattr(session_commands, "read_base_url_for_user", lambda **_kwargs: "http://localhost")
    monkeypatch.setattr(session_commands, "build_openai_compatible_chat_model", lambda **_kwargs: model)


def _history(count: int) -> list[dict[str, str]]:
    return [
        {"role": "user" if index % 2 == 0 else "assistant", "content": f"历史消息 {index}"}
        for index in range(count)
    ]


def test_list_skill_catalog_sorts_entries_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        session_commands,
        "discover_available_skills",
        lambda: [
            SkillMetadata(name="translation", description="翻译", skill_path=Path("t")),
            SkillMetadata(name="summary", description="总结", skill_path=Path("s")),
        ],
    )

    catalog = list_skill_catalog()

    assert [item["name"] for item in catalog] == ["summary", "translation"]
    assert catalog[0]["description"] == "总结"


def test_format_skills_reply_lists_names_and_usage_hint() -> None:
    reply = format_skills_reply(
        [{"name": "summary", "description": "总结论文"}, {"name": "translation", "description": ""}]
    )

    assert "/summary" in reply and "/translation" in reply
    assert "总结论文" in reply
    assert "/技能名" in reply


def test_execute_session_command_rejects_unknown_command(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_membership(monkeypatch)
    _patch_storage(monkeypatch, [])

    with pytest.raises(SessionCommandError, match="未知命令"):
        execute_session_command(
            project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="foobar"
        )


def test_execute_session_command_requires_known_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_commands, "require_project", lambda **_kwargs: {"uid": PROJECT})
    monkeypatch.setattr(session_commands, "list_project_sessions", lambda **_kwargs: [])

    with pytest.raises(LookupError):
        execute_session_command(
            project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="skills"
        )


def test_skills_command_appends_user_and_assistant_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_membership(monkeypatch)
    state = _patch_storage(monkeypatch, _history(2))
    monkeypatch.setattr(
        session_commands,
        "discover_available_skills",
        lambda: [SkillMetadata(name="summary", description="总结论文", skill_path=Path("s"))],
    )

    result = execute_session_command(
        project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="skills"
    )

    saved = state["saves"][0]
    assert saved[-2] == {"role": "user", "content": "/skills"}
    assert saved[-1]["role"] == "assistant"
    assert "/summary" in saved[-1]["content"]
    assert result["message"] == saved[-1]
    assert result["stats"] is None


def test_help_command_lists_every_builtin_command(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_membership(monkeypatch)
    state = _patch_storage(monkeypatch, _history(2))

    result = execute_session_command(
        project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="help"
    )

    content = result["message"]["content"]
    for name in ("/skills", "/compact", "/help", "/documents", "/memory", "/model", "/new", "/rename"):
        assert name in content
    assert state["saves"][0][-2] == {"role": "user", "content": "/help"}


def test_documents_command_lists_files_with_ingestion_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_membership(monkeypatch)
    state = _patch_storage(monkeypatch, _history(2))
    monkeypatch.setattr(
        session_commands,
        "list_project_files",
        lambda **_kwargs: [
            {"uid": "d1", "file_name": "attention.pdf", "is_active": 1},
            {"uid": "d2", "file_name": "旧版本.docx", "is_active": 0},
        ],
    )
    monkeypatch.setattr(
        session_commands,
        "list_project_ingestions",
        lambda **_kwargs: [{"doc_uid": "d1", "status": "published", "stage": "done"}],
    )

    result = execute_session_command(
        project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="documents"
    )

    content = result["message"]["content"]
    assert "attention.pdf" in content
    assert "published" in content
    assert "旧版本.docx" in content
    assert state["saves"][0][-1]["role"] == "assistant"


def test_documents_command_handles_empty_library(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_membership(monkeypatch)
    _patch_storage(monkeypatch, [])
    monkeypatch.setattr(session_commands, "list_project_files", lambda **_kwargs: [])
    monkeypatch.setattr(session_commands, "list_project_ingestions", lambda **_kwargs: [])

    result = execute_session_command(
        project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="documents"
    )

    assert "尚未上传资料" in result["message"]["content"]


def test_memory_command_lists_l3_and_l4_items(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_membership(monkeypatch)
    state = _patch_storage(monkeypatch, _history(2))

    def _memory_items(*, level: str, **_kwargs: Any) -> list[dict[str, Any]]:
        if level == "L3":
            return [{"title": "方法偏好", "content": "优先对比实验设计", "memory_type": "semantic"}]
        return [{"title": "输出语言", "content": "中文回答", "memory_type": "preference"}]

    monkeypatch.setattr(session_commands, "list_memory_items", _memory_items)

    result = execute_session_command(
        project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="memory"
    )

    content = result["message"]["content"]
    assert "方法偏好" in content
    assert "中文回答" in content
    assert state["saves"][0][-1]["role"] == "assistant"


def test_model_command_reports_configuration_without_leaking_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_membership(monkeypatch)
    state = _patch_storage(monkeypatch, _history(2))
    monkeypatch.setattr(session_commands, "read_api_key_for_user", lambda **_kwargs: "sk-secret")
    monkeypatch.setattr(session_commands, "read_model_name_for_user", lambda **_kwargs: "qwen-max")
    monkeypatch.setattr(
        session_commands, "read_base_url_for_user", lambda **_kwargs: "https://dashscope.example.com/v1"
    )

    result = execute_session_command(
        project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="model"
    )

    content = result["message"]["content"]
    assert "qwen-max" in content
    assert "dashscope.example.com" in content
    assert "已配置" in content
    assert "sk-secret" not in content
    assert state["saves"][0][-1]["role"] == "assistant"


def test_compact_below_threshold_is_noop_without_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_membership(monkeypatch)
    state = _patch_storage(monkeypatch, _history(3))
    _patch_model(monkeypatch, _FakeModel())
    monkeypatch.setattr(session_commands, "list_session_runs", lambda **_kwargs: [])

    def _forbidden(**_kwargs: Any) -> None:
        raise AssertionError("model must not be built for a no-op compact")

    monkeypatch.setattr(session_commands, "build_openai_compatible_chat_model", _forbidden)

    result = execute_session_command(
        project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="compact"
    )

    assert result["stats"]["compacted"] is False
    assert "无需压缩" in result["message"]["content"]
    assert state["saves"][0][-2]["content"] == "/compact"


def test_compact_blocked_while_run_active(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_membership(monkeypatch)
    _patch_storage(monkeypatch, _history(12))
    monkeypatch.setattr(
        session_commands, "list_session_runs", lambda **_kwargs: [{"run_uid": "r1", "status": "running"}]
    )

    with pytest.raises(SessionCommandConflict):
        execute_session_command(
            project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="compact"
        )


def test_compact_replaces_history_with_summary_and_recent_tail(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_membership(monkeypatch)
    history = _history(16)
    state = _patch_storage(monkeypatch, history)
    model = _FakeModel()
    _patch_model(monkeypatch, model)
    monkeypatch.setattr(session_commands, "list_session_runs", lambda **_kwargs: [])

    result = execute_session_command(
        project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="compact", args=""
    )

    assert len(model.calls) == 1
    transcript = model.calls[0][1]["content"]
    assert "历史消息 0" in transcript
    assert "历史消息 9" in transcript
    assert "历史消息 10" not in transcript

    saved = state["saves"][0]
    keep = session_commands.COMPACT_KEEP_RECENT_MESSAGES
    assert saved[0]["role"] == "assistant"
    assert saved[0]["content"].startswith("【会话摘要")
    assert f"压缩自 {16 - keep} 条历史消息" in saved[0]["content"]
    assert saved[1 : 1 + keep] == history[-keep:]
    assert saved[-2] == {"role": "user", "content": "/compact"}
    assert saved[-1]["role"] == "assistant"

    stats = result["stats"]
    assert stats is not None and stats["compacted"] is True
    assert stats["messages_before"] == 16
    assert stats["messages_after"] == len(saved)
    assert stats["tokens_after"] < stats["tokens_before"]


def test_compact_requires_configured_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_membership(monkeypatch)
    _patch_storage(monkeypatch, _history(16))
    monkeypatch.setattr(session_commands, "list_session_runs", lambda **_kwargs: [])
    monkeypatch.setattr(session_commands, "read_api_key_for_user", lambda **_kwargs: "")
    monkeypatch.setattr(session_commands, "read_model_name_for_user", lambda **_kwargs: "")

    with pytest.raises(SessionCommandError, match="Model provider"):
        execute_session_command(
            project_uid=PROJECT, session_uid=SESSION, user_uuid=USER, command="compact"
        )
