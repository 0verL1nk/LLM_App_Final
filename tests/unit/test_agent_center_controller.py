from agent.application.agent_center.controller import (
    build_turn_context,
    resolve_archive_target,
    resolve_runtime_session_id,
    resolve_selected_doc_uid_for_logging,
    serialize_output_content,
    validate_runtime_prerequisites,
)


def test_validate_runtime_prerequisites():
    assert validate_runtime_prerequisites(api_key="", model_name="m") == "missing_api_key"
    assert validate_runtime_prerequisites(api_key="k", model_name="") == "missing_model_name"
    assert validate_runtime_prerequisites(api_key="k", model_name="m") is None


def test_build_turn_context_and_runtime_helpers():
    memories = [{"memory_type": "semantic", "content": "m1"}]
    context = build_turn_context(
        prompt="hello",
        user_uuid="u1",
        project_uid="p1",
        search_project_memory_items_fn=lambda **_kwargs: memories,
        memory_limit=4,
    )
    assert context == {"memory_items": [{"memory_type": "semantic", "content": "m1"}]}
    assert resolve_runtime_session_id({"configurable": {"thread_id": "tid"}}) == "tid"
    assert resolve_runtime_session_id({}) == "-"
    assert resolve_selected_doc_uid_for_logging([{"uid": "d1"}]) == "d1"
    assert resolve_selected_doc_uid_for_logging([]) == ""


def test_build_turn_context_omits_empty_memories():
    context = build_turn_context(
        prompt="hello",
        user_uuid="u1",
        project_uid="p1",
        search_project_memory_items_fn=lambda **_kwargs: [],
        memory_limit=4,
    )
    assert context == {}


def test_archive_target_and_serialization():
    uid, name = resolve_archive_target(
        scope_docs_with_text=[{"uid": "d1", "file_name": "docA"}],
        project_name="P",
    )
    assert uid == "d1"
    assert name == "docA"
    uid, name = resolve_archive_target(
        scope_docs_with_text=[{"uid": "d1"}, {"uid": "d2"}],
        project_name="P",
    )
    assert uid is None
    assert name == "P"
    assert serialize_output_content(answer="a", mindmap_data=None, json_dumps_fn=lambda payload, **_kwargs: payload) == "a"
    payload = serialize_output_content(
        answer="a",
        mindmap_data={"name": "root"},
        json_dumps_fn=lambda body, **_kwargs: f"json:{body['name']}",
    )
    assert payload == "json:root"
