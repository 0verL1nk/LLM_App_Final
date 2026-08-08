from agent.adapters.archive import save_output
from agent.adapters.document import extract_document_payload
from agent.adapters.llm import create_chat_model
from agent.adapters.project_store import (
    create_session_for_project,
    delete_session_for_project,
    ensure_default_session_for_project,
    list_project_files_for_user,
    list_session_messages_for_project,
    list_sessions_for_project,
    list_user_projects,
    save_session_messages_for_project,
    update_session_for_project,
)
from agent.adapters.rag import create_project_evidence_retriever
from agent.adapters.user_settings import (
    apply_runtime_tuning_env_for_user,
    list_user_files,
    read_api_key_for_user,
    read_base_url_for_user,
    read_model_name_for_user,
    read_runtime_tuning_settings_for_user,
    read_user_api_key,
    read_user_base_url,
    read_user_model_name,
    save_api_key_for_user,
    save_base_url_for_user,
    save_model_name_for_user,
    save_runtime_tuning_settings_for_user,
)


def test_create_chat_model_delegates(monkeypatch):
    captured = {}

    def _fake_builder(**kwargs):
        captured.update(kwargs)
        return "llm"

    monkeypatch.setattr("agent.adapters.llm.build_openai_compatible_chat_model", _fake_builder)
    model = create_chat_model(api_key="k", model_name="m", base_url="u", temperature=0.2)
    assert model == "llm"
    assert captured["api_key"] == "k"
    assert captured["model_name"] == "m"
    assert captured["base_url"] == "u"
    assert captured["temperature"] == 0.2


def test_create_project_evidence_retriever_routes_single_or_multi(monkeypatch):
    monkeypatch.setattr(
        "agent.adapters.rag.build_local_evidence_retriever_with_settings",
        lambda **_kwargs: "local",
    )
    monkeypatch.setattr(
        "agent.adapters.rag.build_project_evidence_retriever_with_settings",
        lambda **_kwargs: "project",
    )
    assert (
        create_project_evidence_retriever(
            documents=[{"doc_uid": "d1", "doc_name": "n", "text": "t"}],
            project_uid="p1",
        )
        == "local"
    )
    assert (
        create_project_evidence_retriever(
            documents=[
                {"doc_uid": "d1", "doc_name": "n1", "text": "t1"},
                {"doc_uid": "d2", "doc_name": "n2", "text": "t2"},
            ],
            project_uid="p1",
        )
        == "project"
    )


def test_extract_document_payload_delegates_to_local_paddle_ocr(monkeypatch):
    monkeypatch.setattr(
        "agent.adapters.document.extract_document_with_paddle_ocr",
        lambda _path, progress_callback: {
            "text": "识别后的正文",
            "parser": "paddleocr-v6",
            "ocr_profile": "balanced",
            "source_spans": [{"page_no": 1, "start": 0, "end": 6}],
        },
    )

    payload = extract_document_payload("/tmp/paper.pdf", user_uuid="u1")

    assert payload["text"] == "识别后的正文"
    assert payload["parser"] == "paddleocr-v6"
    assert payload["ocr_profile"] == "balanced"
    assert payload["source_spans"] == [{"page_no": 1, "start": 0, "end": 6}]


def test_save_output_delegates(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "agent.adapters.archive.save_agent_output", lambda **kwargs: captured.update(kwargs)
    )
    save_output(uuid="u1", project_uid="p1", session_uid="s1", output_type="text", content="c")
    assert captured["uuid"] == "u1"


def test_project_store_adapters_delegate(monkeypatch):
    monkeypatch.setattr(
        "agent.adapters.project_store.list_projects",
        lambda uuid, include_archived=False: [
            {"project_uid": "p1", "uuid": uuid, "archived": include_archived}
        ],
    )
    monkeypatch.setattr(
        "agent.adapters.project_store.list_project_files",
        lambda **kwargs: [kwargs],
    )
    monkeypatch.setattr(
        "agent.adapters.project_store.list_project_sessions",
        lambda **kwargs: [kwargs],
    )
    monkeypatch.setattr(
        "agent.adapters.project_store.list_project_session_messages",
        lambda **kwargs: [{"role": "user", "content": "q", **kwargs}],
    )
    default_calls = {}
    create_calls = {}
    update_calls = {}
    delete_calls = {}
    save_calls = {}
    monkeypatch.setattr(
        "agent.adapters.project_store.ensure_default_project_session",
        lambda **kwargs: default_calls.update(kwargs),
    )
    monkeypatch.setattr(
        "agent.adapters.project_store.create_project_session",
        lambda **kwargs: create_calls.update(kwargs) or {"session_uid": "s2"},
    )
    monkeypatch.setattr(
        "agent.adapters.project_store.update_project_session",
        lambda **kwargs: update_calls.update(kwargs),
    )
    monkeypatch.setattr(
        "agent.adapters.project_store.delete_project_session",
        lambda **kwargs: delete_calls.update(kwargs),
    )
    monkeypatch.setattr(
        "agent.adapters.project_store.save_project_session_messages",
        lambda **kwargs: save_calls.update(kwargs),
    )

    assert list_user_projects(uuid="u1") == [{"project_uid": "p1", "uuid": "u1", "archived": False}]
    assert list_project_files_for_user(project_uid="p1", uuid="u1")[0]["project_uid"] == "p1"
    assert list_sessions_for_project(project_uid="p1", uuid="u1")[0]["project_uid"] == "p1"
    assert (
        list_session_messages_for_project(session_uid="s1", project_uid="p1", uuid="u1")[0][
            "session_uid"
        ]
        == "s1"
    )
    ensure_default_session_for_project(project_uid="p1", uuid="u1")
    create_session_for_project(project_uid="p1", uuid="u1", session_name="会话")
    update_session_for_project(
        session_uid="s1",
        project_uid="p1",
        uuid="u1",
        session_name="new",
        is_pinned=1,
    )
    delete_session_for_project(session_uid="s1", project_uid="p1", uuid="u1")
    save_session_messages_for_project(
        session_uid="s1",
        project_uid="p1",
        uuid="u1",
        messages=[{"role": "assistant", "content": "a"}],
    )

    assert default_calls["project_uid"] == "p1"
    assert create_calls["session_name"] == "会话"
    assert update_calls["is_pinned"] == 1
    assert delete_calls["session_uid"] == "s1"
    assert isinstance(save_calls["messages"], list)


def test_user_settings_adapters_delegate(monkeypatch):
    monkeypatch.setattr("agent.adapters.user_settings.get_user_api_key", lambda: "k")
    monkeypatch.setattr("agent.adapters.user_settings.get_user_model_name", lambda: "m")
    monkeypatch.setattr("agent.adapters.user_settings.get_user_base_url", lambda: "u")
    monkeypatch.setattr(
        "agent.adapters.user_settings.get_user_files", lambda uuid: [{"uuid": uuid}]
    )
    monkeypatch.setattr("agent.adapters.user_settings.get_api_key", lambda uuid: f"k:{uuid}")
    monkeypatch.setattr("agent.adapters.user_settings.get_model_name", lambda uuid: f"m:{uuid}")
    monkeypatch.setattr("agent.adapters.user_settings.get_base_url", lambda uuid: f"b:{uuid}")
    monkeypatch.setattr(
        "agent.adapters.user_settings.get_runtime_tuning_settings",
        lambda uuid: {
            "rag_index_batch_size": 64,
            "local_rag_project_max_chars": None,
            "local_rag_project_max_chunks": None,
        },
    )
    save_calls = {}
    monkeypatch.setattr(
        "agent.adapters.user_settings.save_api_key",
        lambda uuid, value: save_calls.__setitem__("api_key", (uuid, value)),
    )
    monkeypatch.setattr(
        "agent.adapters.user_settings.save_model_name",
        lambda uuid, value: save_calls.__setitem__("model_name", (uuid, value)),
    )
    monkeypatch.setattr(
        "agent.adapters.user_settings.save_base_url",
        lambda uuid, value: save_calls.__setitem__("base_url", (uuid, value)),
    )
    monkeypatch.setattr(
        "agent.adapters.user_settings.save_runtime_tuning_settings",
        lambda uuid, **kwargs: save_calls.__setitem__("runtime", (uuid, kwargs)),
    )

    assert read_user_api_key() == "k"
    assert read_user_model_name() == "m"
    assert read_user_base_url() == "u"
    assert list_user_files(uuid="u1")[0]["uuid"] == "u1"
    assert read_api_key_for_user(uuid="u1") == "k:u1"
    assert read_model_name_for_user(uuid="u1") == "m:u1"
    assert read_base_url_for_user(uuid="u1") == "b:u1"
    assert read_runtime_tuning_settings_for_user(uuid="u1")["rag_index_batch_size"] == 64

    save_api_key_for_user(uuid="u1", api_key="a")
    save_model_name_for_user(uuid="u1", model_name="m1")
    save_base_url_for_user(uuid="u1", base_url="https://x")
    save_runtime_tuning_settings_for_user(
        "u1",
        rag_index_batch_size=64,
        local_rag_project_max_chars=5000,
        local_rag_project_max_chunks=200,
    )
    apply_runtime_tuning_env_for_user(uuid="u1")
    assert save_calls["api_key"] == ("u1", "a")
    assert save_calls["model_name"] == ("u1", "m1")
    assert save_calls["base_url"] == ("u1", "https://x")
    assert save_calls["runtime"][0] == "u1"
