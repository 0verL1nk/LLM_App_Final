from pathlib import Path

from langchain_core.messages import AIMessage

from agent.memory.consolidation import process_memory_event
from agent.memory.repository import (
    create_memory_event,
    get_memory_event,
    list_project_memory_items,
)


class _StructuredModel:
    def invoke(self, _messages):
        return AIMessage(
            content=(
                "<think>The user asked for concise Chinese responses.</think>\n"
                "```json\n"
                '{"operations": [{"action": "create", "memory_type": "procedural", '
                '"title": "Response preference", '
                '"content": "The user prefers concise Chinese responses.", '
                '"reason": "Explicit standing preference"}]}\n'
                "```"
            )
        )


def test_process_memory_event_uses_model_operations(monkeypatch, tmp_path: Path) -> None:
    db_path = str(tmp_path / "memory.sqlite")
    event_uid = create_memory_event(
        uuid="u1",
        project_uid="p1",
        session_uid="s1",
        prompt="以后请用简洁中文回答",
        answer="好的",
        db_name=db_path,
    )
    monkeypatch.setattr(
        "agent.memory.consolidation._build_model_for_user",
        lambda _uuid: _StructuredModel(),
    )

    process_memory_event(event_uid, db_name=db_path)

    event = get_memory_event(event_uid=event_uid, db_name=db_path)
    memories = list_project_memory_items(uuid="u1", project_uid="p1", db_name=db_path)
    assert event is not None and event["status"] == "completed"
    assert event["prompt"] == "" and event["answer"] == ""
    assert [memory["content"] for memory in memories] == [
        "The user prefers concise Chinese responses."
    ]


def test_completed_memory_event_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    db_path = str(tmp_path / "memory.sqlite")
    event_uid = create_memory_event(
        uuid="u1",
        project_uid="p1",
        session_uid="s1",
        prompt="remember this preference",
        answer="acknowledged",
        db_name=db_path,
    )
    model = _StructuredModel()
    monkeypatch.setattr(
        "agent.memory.consolidation._build_model_for_user", lambda _uuid: model
    )

    process_memory_event(event_uid, db_name=db_path)
    process_memory_event(event_uid, db_name=db_path)

    assert len(list_project_memory_items(uuid="u1", project_uid="p1", db_name=db_path)) == 1
