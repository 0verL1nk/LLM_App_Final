from typing import Any


def validate_runtime_prerequisites(*, api_key: str, model_name: str) -> str | None:
    if not api_key:
        return "missing_api_key"
    if not model_name:
        return "missing_model_name"
    return None


def build_turn_context(
    *,
    prompt: str,
    user_uuid: str,
    project_uid: str,
    search_project_memory_items_fn,
    memory_limit: int = 4,
) -> dict[str, Any]:
    base_prompt = str(prompt or "").strip()
    if not base_prompt:
        return {}

    long_term_memories = search_project_memory_items_fn(
        uuid=user_uuid,
        project_uid=project_uid,
        query=base_prompt,
        limit=memory_limit,
    )
    context: dict[str, Any] = {}

    memory_items = _normalize_memory_items(long_term_memories, max_chars=1600)
    if memory_items:
        context["memory_items"] = memory_items
    return context


def _collapse_inline_text(text: Any, *, limit: int) -> str:
    compact = " ".join(str(text or "").split()).strip()
    if not compact:
        return ""
    if len(compact) <= max(1, int(limit)):
        return compact
    clipped = max(1, int(limit)) - 3
    return f"{compact[:clipped]}..."


def _normalize_memory_items(
    memory_items: list[dict[str, Any]],
    *,
    max_chars: int,
) -> list[dict[str, str]]:
    if not isinstance(memory_items, list) or not memory_items:
        return []
    normalized_items: list[dict[str, str]] = []
    current_len = 0
    for item in memory_items:
        if not isinstance(item, dict):
            continue
        memory_type = str(item.get("memory_type") or "episodic").strip().lower() or "episodic"
        content = _collapse_inline_text(item.get("content"), limit=220)
        if not content:
            continue
        candidate = f"{memory_type}:{content}"
        added_len = len(candidate) if not normalized_items else len(candidate) + 1
        if current_len + added_len > max_chars:
            break
        normalized_items.append({"memory_type": memory_type, "content": content})
        current_len += added_len
    return normalized_items


def resolve_runtime_session_id(runtime_config: dict[str, Any] | Any) -> str:
    if isinstance(runtime_config, dict):
        return str(runtime_config.get("configurable", {}).get("thread_id") or "-")
    return "-"


def resolve_selected_doc_uid_for_logging(scope_docs_with_text: list[dict[str, Any]]) -> str:
    if not scope_docs_with_text:
        return ""
    return str(scope_docs_with_text[0].get("uid") or "")


def resolve_archive_target(
    *,
    scope_docs_with_text: list[dict[str, Any]],
    project_name: str,
) -> tuple[str | None, str]:
    if len(scope_docs_with_text) == 1:
        doc = scope_docs_with_text[0]
        return str(doc.get("uid") or ""), str(doc.get("file_name") or project_name)
    return None, project_name


def serialize_output_content(
    *,
    answer: str,
    mindmap_data: dict[str, Any] | None,
    json_dumps_fn,
) -> str:
    if mindmap_data:
        return str(json_dumps_fn(mindmap_data, ensure_ascii=False))
    return answer
