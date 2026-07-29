import datetime
from pathlib import Path

from agent.adapters.sqlite.project_repository import (
    create_project,
    create_project_session,
    delete_project_session,
    ensure_default_project_session,
    list_project_session_messages,
    list_project_sessions,
    save_project_session_messages,
    update_project_session,
)
from agent.memory.store import (
    list_project_memory_items,
    search_project_memory_items,
    upsert_project_memory_item,
)
from utils.utils import (
    ensure_local_user,
    init_database,
)


def _prepare_project(tmp_path: Path) -> tuple[Path, str]:
    db_path = tmp_path / "database.sqlite"
    init_database(str(db_path))
    ensure_local_user("local-user", db_name=str(db_path))
    project = create_project(
        uuid="local-user",
        project_name="session-demo",
        db_name=str(db_path),
    )
    return db_path, str(project["project_uid"])


def test_project_session_message_roundtrip(tmp_path: Path) -> None:
    db_path, project_uid = _prepare_project(tmp_path)
    session_uid = ensure_default_project_session(
        project_uid=project_uid,
        uuid="local-user",
        db_name=str(db_path),
    )

    messages = [
        {"role": "assistant", "content": "欢迎来到项目会话"},
        {
            "role": "user",
            "content": "请总结这篇论文",
            "workflow_mode": "react",
        },
    ]
    save_project_session_messages(
        session_uid=session_uid,
        project_uid=project_uid,
        uuid="local-user",
        messages=messages,
        db_name=str(db_path),
    )

    loaded = list_project_session_messages(
        session_uid=session_uid,
        project_uid=project_uid,
        uuid="local-user",
        db_name=str(db_path),
    )
    assert loaded == messages

    sessions = list_project_sessions(
        project_uid=project_uid,
        uuid="local-user",
        db_name=str(db_path),
    )
    assert len(sessions) == 1
    assert sessions[0]["session_uid"] == session_uid
    assert sessions[0]["message_count"] == 2
    assert sessions[0]["last_message"] == "请总结这篇论文"


def test_project_session_update_and_delete(tmp_path: Path) -> None:
    db_path, project_uid = _prepare_project(tmp_path)
    session_a = create_project_session(
        project_uid=project_uid,
        uuid="local-user",
        session_name="会话 A",
        db_name=str(db_path),
    )
    session_b = create_project_session(
        project_uid=project_uid,
        uuid="local-user",
        session_name="会话 B",
        db_name=str(db_path),
    )

    updated = update_project_session(
        session_uid=str(session_b["session_uid"]),
        project_uid=project_uid,
        uuid="local-user",
        session_name="重点会话",
        is_pinned=1,
        db_name=str(db_path),
    )
    assert updated

    sessions = list_project_sessions(
        project_uid=project_uid,
        uuid="local-user",
        db_name=str(db_path),
    )
    assert sessions[0]["session_uid"] == str(session_a["session_uid"])
    assert sessions[0]["is_main"] is True
    assert sessions[1]["session_uid"] == str(session_b["session_uid"])
    assert sessions[1]["session_name"] == "重点会话"
    assert sessions[1]["is_pinned"] == 1

    save_project_session_messages(
        session_uid=str(session_b["session_uid"]),
        project_uid=project_uid,
        uuid="local-user",
        messages=[{"role": "assistant", "content": "to be deleted"}],
        db_name=str(db_path),
    )
    deleted = delete_project_session(
        session_uid=str(session_b["session_uid"]),
        project_uid=project_uid,
        uuid="local-user",
        db_name=str(db_path),
    )
    assert deleted

    remaining = list_project_sessions(
        project_uid=project_uid,
        uuid="local-user",
        db_name=str(db_path),
    )
    assert len(remaining) == 1
    assert remaining[0]["session_uid"] == str(session_a["session_uid"])

    removed_messages = list_project_session_messages(
        session_uid=str(session_b["session_uid"]),
        project_uid=project_uid,
        uuid="local-user",
        db_name=str(db_path),
    )
    assert removed_messages == []
def test_project_memory_item_upsert_and_search(monkeypatch, tmp_path: Path) -> None:
    class _Embeddings:
        def embed_query(self, _text: str) -> list[float]:
            return [1.0, 0.0]

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [
                [1.0, 0.0] if "方法A优于方法B" in text else [0.0, 1.0]
                for text in texts
            ]

    monkeypatch.setattr(
        "agent.memory.service.get_embedding_model", lambda: _Embeddings()
    )
    db_path, project_uid = _prepare_project(tmp_path)
    session_uid = ensure_default_project_session(
        project_uid=project_uid,
        uuid="local-user",
        db_name=str(db_path),
    )

    uid_first = upsert_project_memory_item(
        uuid="local-user",
        project_uid=project_uid,
        session_uid=session_uid,
        memory_type="episodic",
        title="实验结论",
        content="Q: 这篇论文的主要结论是什么 A: 结论是方法A优于方法B",
        source_prompt="主要结论是什么",
        source_answer="方法A优于方法B",
        db_name=str(db_path),
    )
    assert uid_first

    uid_second = upsert_project_memory_item(
        uuid="local-user",
        project_uid=project_uid,
        session_uid=session_uid,
        memory_type="episodic",
        title="实验结论重复",
        content="Q: 这篇论文的主要结论是什么 A: 结论是方法A优于方法B",
        source_prompt="主要结论是什么",
        source_answer="方法A优于方法B",
        db_name=str(db_path),
    )
    assert uid_second == uid_first

    upsert_project_memory_item(
        uuid="local-user",
        project_uid=project_uid,
        session_uid=session_uid,
        memory_type="semantic",
        title="数据集",
        content="该实验主要使用CIFAR-10与ImageNet数据集",
        db_name=str(db_path),
    )

    all_items = list_project_memory_items(
        uuid="local-user",
        project_uid=project_uid,
        limit=20,
        db_name=str(db_path),
    )
    assert len(all_items) == 2

    matched = search_project_memory_items(
        uuid="local-user",
        project_uid=project_uid,
        query="主要结论 方法A",
        limit=3,
        db_name=str(db_path),
    )
    assert matched
    assert "方法A优于方法B" in matched[0]["content"]


def test_project_memory_expired_items_are_filtered(tmp_path: Path) -> None:
    db_path, project_uid = _prepare_project(tmp_path)
    session_uid = ensure_default_project_session(
        project_uid=project_uid,
        uuid="local-user",
        db_name=str(db_path),
    )
    past = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    future = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

    upsert_project_memory_item(
        uuid="local-user",
        project_uid=project_uid,
        session_uid=session_uid,
        memory_type="episodic",
        title="过期记忆",
        content="这个记忆已过期",
        expires_at=past,
        db_name=str(db_path),
    )
    upsert_project_memory_item(
        uuid="local-user",
        project_uid=project_uid,
        session_uid=session_uid,
        memory_type="episodic",
        title="有效记忆",
        content="这个记忆有效",
        expires_at=future,
        db_name=str(db_path),
    )

    items = list_project_memory_items(
        uuid="local-user",
        project_uid=project_uid,
        limit=20,
        include_expired=False,
        db_name=str(db_path),
    )
    assert len(items) == 1
    assert items[0]["title"] == "有效记忆"
