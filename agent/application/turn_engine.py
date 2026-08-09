import json
import logging
import re
import time
from typing import Any, cast

from ..domain.human_request import extract_human_requests
from ..domain.trace import TraceEvent, phase_label_from_performative, phase_summary
from ..method_compare_parser import parse_method_compare_payload
from ..stream import extract_stream_text
from .a2ui_fragments import A2UIFragmentStreamParser, PresentationDecision
from .a2ui_mindmap import build_mindmap_surface_from_request
from .contracts import EventCallback, SearchDocumentFn, TurnCoreResult
from .delegation import build_delegation_execution
from .ports import AgentInvoker, EvidenceRetriever

logger = logging.getLogger(__name__)

_EVIDENCE_OPEN_TAG_VARIANTS = re.compile(
    r"(?:<|【|［|＜)\s*evidence\s*(?:>|】|］|＞)",
    flags=re.IGNORECASE,
)
_EVIDENCE_CLOSE_TAG_VARIANTS = re.compile(
    r"(?:<|【|［|＜)\s*/\s*evidence\s*(?:>|】|］|＞)",
    flags=re.IGNORECASE,
)
_INLINE_EVIDENCE_CHUNK_PATTERN = re.compile(
    r"(?<![\w/])([A-Za-z0-9_.-]+:[^|\s<>\]]*:chunk_[^|\s<>\]]+)(?=\|p(?:\d+|null)\b)",
    flags=re.IGNORECASE,
)
_INLINE_EVIDENCE_DOC_PATTERN = re.compile(
    r"(?<![\w/])([A-Za-z0-9_.-]+:[^|\s<>\]]+)(?=\|p(?:\d+|null)\b)",
    flags=re.IGNORECASE,
)


def _execute_agent_with_streaming(
    *,
    leader_agent: AgentInvoker,
    prompt: str,
    config: dict[str, Any],
    on_delta: EventCallback | None,
) -> dict[str, Any]:
    """Run once while forwarding final-answer chunks and retaining final state."""
    stream = getattr(leader_agent, "stream", None)
    if not callable(stream):
        return leader_agent.invoke({"messages": [{"role": "user", "content": prompt}]}, config=config)

    final_state: dict[str, Any] | None = None
    received_stream_part = False
    try:
        for part in stream(
            {"messages": [{"role": "user", "content": prompt}]},
            config=config,
            stream_mode=["messages", "values"],
            version="v2",
        ):
            received_stream_part = True
            if not isinstance(part, dict):
                continue
            if part.get("type") == "messages":
                delta = extract_stream_text(part.get("data"))
                if delta and on_delta is not None:
                    on_delta({"performative": "answer_delta", "content": delta})
            elif part.get("type") == "values" and isinstance(part.get("data"), dict):
                final_state = part["data"]
    except (TypeError, NotImplementedError):
        # Lightweight test doubles and legacy invokers can expose an unusable
        # ``stream`` attribute. They still retain the canonical invoke contract.
        final_state = None

    if final_state is not None:
        return final_state
    if received_stream_part:
        raise RuntimeError("Agent stream ended without a final state")
    return leader_agent.invoke({"messages": [{"role": "user", "content": prompt}]}, config=config)


def normalize_evidence_items(raw_payload: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_payload, dict):
        return []
    evidences = raw_payload.get("evidences")
    if not isinstance(evidences, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in evidences:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        normalized.append(item)
    return normalized


def _message_content(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")


def _message_name(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("name") or "").strip()
    return str(getattr(message, "name", "") or "").strip()


def _message_role(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or message.get("type") or "").strip().lower()
    return str(getattr(message, "type", getattr(message, "role", "")) or "").strip().lower()


def _message_tool_calls(message: Any) -> list[dict[str, Any]]:
    if isinstance(message, dict):
        tool_calls = message.get("tool_calls")
    else:
        tool_calls = getattr(message, "tool_calls", None)
    if not isinstance(tool_calls, list):
        return []
    return [item for item in tool_calls if isinstance(item, dict)]


def normalize_evidence_tag_variants(answer: str) -> str:
    """Normalize malformed evidence tags into canonical <evidence> tags."""
    if not isinstance(answer, str) or not answer:
        return "" if answer is None else str(answer)
    normalized = _EVIDENCE_OPEN_TAG_VARIANTS.sub("<evidence>", answer)
    normalized = _EVIDENCE_CLOSE_TAG_VARIANTS.sub("</evidence>", normalized)
    return normalized


def _parse_tool_json_payload(content: str) -> dict[str, Any] | None:
    text = str(content or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _collect_document_evidence_items(messages: list[Any]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for message in messages:
        if _message_role(message) != "tool" or _message_name(message) not in {
            "search_document",
            "read_document",
        }:
            continue
        payload = _parse_tool_json_payload(_message_content(message))
        if payload is None:
            continue
        collected.extend(normalize_evidence_items(payload))
    seen_chunk_ids: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in collected:
        chunk_id = str(item.get("chunk_id", "")).strip()
        if chunk_id and chunk_id in seen_chunk_ids:
            continue
        if chunk_id:
            seen_chunk_ids.add(chunk_id)
        unique.append(item)
    return unique


def _select_referenced_evidence_items(
    evidence_items: list[dict[str, Any]],
    *,
    referenced_chunk_ids: list[str],
    referenced_doc_uids: list[str],
) -> list[dict[str, Any]]:
    referenced_chunks = {item.strip() for item in referenced_chunk_ids if item.strip()}
    referenced_docs = {item.strip() for item in referenced_doc_uids if item.strip()}
    if not referenced_chunks and not referenced_docs:
        return []
    matched: list[dict[str, Any]] = []
    for item in evidence_items:
        chunk_id = str(item.get("chunk_id", "")).strip()
        doc_uid = str(item.get("doc_uid", "")).strip()
        chunk_doc_uid = (
            chunk_id.split(":chunk_", 1)[0].strip()
            if chunk_id and ":chunk_" in chunk_id
            else ""
        )
        if (
            chunk_id in referenced_chunks
            or (doc_uid and doc_uid in referenced_docs)
            or (chunk_doc_uid and chunk_doc_uid in referenced_docs)
        ):
            matched.append(item)
    return matched


def build_search_document_fn(
    search_document_evidence_fn: EvidenceRetriever | None,
) -> SearchDocumentFn:
    if not callable(search_document_evidence_fn):
        return lambda _query: ""

    def _search(query: str) -> str:
        payload = search_document_evidence_fn(query)
        evidence_items = normalize_evidence_items(payload)
        return "\n".join(str(item.get("text", "")) for item in evidence_items)

    return _search


def _maybe_to_dict(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        return dict(payload)
    to_dict = getattr(payload, "to_dict", None)
    if not callable(to_dict):
        return None
    result = to_dict()
    if not isinstance(result, dict):
        return None
    return result


def _stable_phase_path(*, phase_labels: list[str], answer: str, messages: list[Any]) -> str:
    normalized_labels = list(phase_labels)
    if (answer.strip() or messages) and (
        not normalized_labels or normalized_labels[-1] != "输出最终答案"
    ):
        normalized_labels.append("输出最终答案")
    return phase_summary(normalized_labels)


def extract_evidence_chunk_ids(answer: str) -> list[str]:
    """从 answer 中提取所有 <evidence> 标签中的 chunk_id。

    格式: <evidence>chunk_id|p页码|o起止偏移</evidence>
    返回: ['chunk_id1', 'chunk_id2', ...]
    """
    if not isinstance(answer, str):
        return []
    answer = normalize_evidence_tag_variants(answer)
    pattern = re.compile(
        r"<evidence>([^<|]+)(?:\|[^<]*)?</evidence>",
        flags=re.IGNORECASE,
    )
    matches = [chunk_id.strip() for chunk_id in pattern.findall(answer) if chunk_id.strip()]
    matches.extend(
        chunk_id.strip()
        for chunk_id in _INLINE_EVIDENCE_CHUNK_PATTERN.findall(answer)
        if chunk_id.strip()
    )
    seen: set[str] = set()
    ordered: list[str] = []
    for chunk_id in matches:
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        ordered.append(chunk_id)
    return ordered



def extract_evidence_doc_uids(answer: str) -> list[str]:
    """从 answer 中提取文档级引用，如 arxiv:2310.11511|p1|o0-10。"""
    if not isinstance(answer, str):
        return []
    answer = normalize_evidence_tag_variants(answer)

    references: set[str] = set()
    for raw_ref in _INLINE_EVIDENCE_DOC_PATTERN.findall(answer):
        ref = raw_ref.strip()
        if not ref:
            continue
        if ":chunk_" in ref:
            ref = ref.split(":chunk_", 1)[0].strip()
        if ref:
            references.add(ref)

    for chunk_id in extract_evidence_chunk_ids(answer):
        ref = chunk_id.split(":chunk_", 1)[0].strip() if ":chunk_" in chunk_id else chunk_id.strip()
        if ref:
            references.add(ref)
    return sorted(references)


def execute_turn_core(
    *,
    prompt: str,
    turn_context: dict[str, Any] | None = None,
    leader_agent: AgentInvoker,
    leader_runtime_config: dict[str, Any] | None,
    search_document_evidence_fn: EvidenceRetriever | None = None,
    leader_tool_specs: list[dict[str, Any]] | None = None,
    on_event: EventCallback | None = None,
) -> TurnCoreResult:
    if leader_agent is None:
        raise ValueError("Leader agent is not initialized")

    event_logs: list[TraceEvent] = []
    phase_labels: list[str] = []

    def _collect_event(item: TraceEvent) -> None:
        if str(item.get("performative") or "") in {
            "answer_part_delta",
            "answer_part_insert",
            "a2ui_surface_ready",
        }:
            if on_event is not None:
                on_event(item)
            return
        logger.info(f"_collect_event called: performative={item.get('performative')}, content={item.get('content')}")
        phase = phase_label_from_performative(str(item.get("performative", "")))
        phase_labels.append(phase)
        event: TraceEvent = dict(item)
        event["sender"] = str(item.get("sender", "unknown"))
        event["receiver"] = str(item.get("receiver", "unknown"))
        event["performative"] = str(item.get("performative", "message"))
        event["content"] = str(item.get("content", ""))
        event["phase"] = phase
        event_logs.append(event)
        if on_event is not None:
            on_event(event)

    registered_tool_names: list[str] = []
    if isinstance(leader_tool_specs, list):
        for item in leader_tool_specs:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            registered_tool_names.append(name)

    run_started = time.perf_counter()

    # 构建 config,传递必要参数给 middleware
    config = dict(leader_runtime_config) if isinstance(leader_runtime_config, dict) else {}
    configurable = dict(config.get("configurable", {})) if isinstance(config.get("configurable"), dict) else {}
    config["configurable"] = configurable

    # 传递 on_event 回调给 middleware
    configurable["on_event"] = _collect_event
    if isinstance(turn_context, dict) and turn_context:
        configurable["turn_context"] = dict(turn_context)
    # 确保有 thread_id 用于 session 隔离
    if "thread_id" not in configurable:
        configurable["thread_id"] = "default"

    visible_deltas: list[str] = []
    fragments: list[tuple[str, PresentationDecision]] = []
    response_parts: list[dict[str, str]] = []
    streamed_text_seen = False
    text_part_id = "text-0"
    pending_surface_part_id = ""

    def emit_visible_text(text: str) -> None:
        if not text:
            return
        visible_deltas.append(text)
        if response_parts and response_parts[-1].get("id") == text_part_id:
            response_parts[-1]["text"] += text
        else:
            response_parts.append({"id": text_part_id, "type": "markdown", "text": text})
        _collect_event(
            {
                "performative": "answer_part_delta",
                "content": text,
                "metadata": {"part_id": text_part_id},
            }
        )

    def insert_surface_part(_fragment_type: str) -> None:
        nonlocal pending_surface_part_id, text_part_id
        pending_surface_part_id = f"surface-{len(fragments)}"
        response_parts.append({"id": pending_surface_part_id, "type": "a2ui"})
        _collect_event(
            {
                "performative": "answer_part_insert",
                "metadata": {"part_id": pending_surface_part_id, "part_type": "a2ui"},
            }
        )
        text_part_id = f"text-{len(fragments) + 1}"

    def emit_surface(fragment: PresentationDecision) -> None:
        if not pending_surface_part_id:
            logger.warning("Discarded inline UI fragment without an insertion anchor")
            return
        surface = build_mindmap_surface_from_request(
            fragment.payload,
            allowed_citation_ids=set(),
        )
        if surface is None:
            report_surface_failure("可视化内容未通过安全校验，已保留正文。")
            return
        fragments.append((pending_surface_part_id, fragment))
        _collect_event(
            {
                "performative": "a2ui_surface_ready",
                "metadata": {"part_id": pending_surface_part_id, "surface": surface},
            }
        )

    def report_surface_failure(message: str) -> None:
        if not pending_surface_part_id:
            logger.warning("Discarded inline UI fragment: %s", message)
            return
        _collect_event(
            {
                "performative": "presentation_failed",
                "metadata": {"part_id": pending_surface_part_id, "message": message},
            }
        )

    parser = A2UIFragmentStreamParser(
        on_text=emit_visible_text,
        on_fragment_start=insert_surface_part,
        on_fragment=emit_surface,
        on_error=report_surface_failure,
    )
    def ingest_delta(event: TraceEvent) -> None:
        nonlocal streamed_text_seen
        streamed_text_seen = True
        parser.feed(str(event.get("content") or ""))

    result = _execute_agent_with_streaming(
        leader_agent=leader_agent,
        prompt=prompt,
        config=config,
        on_delta=ingest_delta,
    )

    # 提取 answer
    answer = ""
    messages: list[Any] = []
    if isinstance(result, dict):
        raw_messages = result.get("messages", [])
        messages = raw_messages if isinstance(raw_messages, list) else []
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, "content"):
                answer = str(last_msg.content)
            elif isinstance(last_msg, dict):
                answer = str(last_msg.get("content", ""))

    if not streamed_text_seen and answer:
        parser.feed(answer)
    parser.finish()
    answer = "".join(visible_deltas)
    if not answer:
        raise RuntimeError("Agent execution completed without a final answer")
    answer = normalize_evidence_tag_variants(answer)
    logger.info("TURN_FINAL_ANSWER: %s", answer)

    # 从result中提取信息（如果有的话）
    trace_payload = event_logs
    plan_payload = result.get("plan") if isinstance(result, dict) else None
    runtime_state_payload = result.get("runtime_state") if isinstance(result, dict) else None
    todo_scheduler_hint = result.get("todo_scheduler_hint") if isinstance(result, dict) else None

    # 检测是否使用了document RAG
    used_document_rag = False
    for msg in messages:
        for call in _message_tool_calls(msg):
            if call.get("name") == "search_document":
                used_document_rag = True
                break
        if used_document_rag:
            break

    # 从 answer 中提取 agent 引用的 chunk_id
    referenced_chunk_ids = extract_evidence_chunk_ids(answer)
    referenced_doc_uids = extract_evidence_doc_uids(answer)

    retrieved_evidence_items = _collect_document_evidence_items(messages)
    evidence_items = _select_referenced_evidence_items(
        retrieved_evidence_items,
        referenced_chunk_ids=referenced_chunk_ids,
        referenced_doc_uids=referenced_doc_uids,
    )
    delegation_execution = build_delegation_execution(messages, event_logs)
    delegated_research = any(
        task["subagent_type"] == "researcher"
        for task in delegation_execution["tasks"]
    )
    if (
        not evidence_items
        and (referenced_chunk_ids or referenced_doc_uids)
        and (used_document_rag or delegated_research)
        and callable(search_document_evidence_fn)
    ):
        try:
            # 获取所有相关证据
            evidence_payload = search_document_evidence_fn(prompt)
            all_evidence = normalize_evidence_items(evidence_payload)
            known_chunk_ids = {
                str(item.get("chunk_id") or "") for item in retrieved_evidence_items
            }
            retrieved_evidence_items.extend(
                item
                for item in all_evidence
                if str(item.get("chunk_id") or "") not in known_chunk_ids
            )

            # 筛选出 agent 实际引用的证据
            referenced_chunk_set = {item.strip() for item in referenced_chunk_ids if item.strip()}
            referenced_doc_set = {item.strip() for item in referenced_doc_uids if item.strip()}
            for item in all_evidence:
                chunk_id = str(item.get("chunk_id", "")).strip()
                doc_uid = str(item.get("doc_uid", "")).strip()
                chunk_doc_uid = chunk_id.split(":chunk_", 1)[0].strip() if ":chunk_" in chunk_id else ""
                if (
                    chunk_id in referenced_chunk_set
                    or (doc_uid and doc_uid in referenced_doc_set)
                    or (chunk_doc_uid and chunk_doc_uid in referenced_doc_set)
                ):
                    evidence_items.append(item)
        except Exception as exc:
            logger.warning("Evidence fallback retrieval failed: %s", exc)
            evidence_items = []
    method_compare_data = parse_method_compare_payload(answer)
    allowed_citation_ids = {
            str(item.get("chunk_id") or "").strip()
            for item in retrieved_evidence_items
            if str(item.get("chunk_id") or "").strip()
    }
    a2ui_surfaces = [
        {
            **surface,
            "partId": part_id,
        }
        for part_id, fragment in fragments
        if fragment.type == "research-map"
        for surface in [
            build_mindmap_surface_from_request(
                fragment.payload,
                allowed_citation_ids=allowed_citation_ids,
            )
        ]
        if surface is not None
    ]
    a2ui_surface = a2ui_surfaces[-1] if a2ui_surfaces else None
    surface_ids_by_part = {
        str(surface["partId"]): str(surface["surfaceId"])
        for surface in a2ui_surfaces
    }
    for part in response_parts:
        if part.get("type") == "a2ui" and part.get("id") in surface_ids_by_part:
            part["surfaceId"] = surface_ids_by_part[part["id"]]
    mindmap_data = (
        cast(dict[str, Any], a2ui_surface["mindmap"])
        if isinstance(a2ui_surface, dict) and isinstance(a2ui_surface.get("mindmap"), dict)
        else None
    )
    # 从 result 中提取 middleware 添加的 state
    todos = result.get("todos", []) if isinstance(result, dict) else []
    agent_plan = result.get("agent_plan") if isinstance(result, dict) else None
    for task in delegation_execution["tasks"]:
        _collect_event(
            {
                "sender": "leader",
                "receiver": task["subagent_type"],
                "performative": "delegate_task",
                "content": task["description"],
            }
        )
        if task["status"] in {"completed", "failed"}:
            _collect_event(
                {
                    "sender": task["subagent_type"],
                    "receiver": "leader",
                    "performative": "delegate_result",
                    "content": task["status"],
                }
            )

    run_latency_ms = (time.perf_counter() - run_started) * 1000.0
    phase_path = _stable_phase_path(phase_labels=phase_labels, answer=answer, messages=messages)

    return {
        "answer": answer,
        "policy_decision": {
            "plan_enabled": bool(agent_plan or plan_payload),
            "delegation_enabled": delegation_execution["enabled"],
            "reason": "runtime-observed",
            "source": "runtime",
        },
        "delegation_execution": delegation_execution,
        "trace_payload": trace_payload,
        "plan": _maybe_to_dict(plan_payload),
        "runtime_state": _maybe_to_dict(runtime_state_payload),
        "evidence_items": evidence_items,
        "retrieved_evidence_items": retrieved_evidence_items,
        "mindmap_data": mindmap_data,
        "a2ui_surface": a2ui_surface,
        "a2ui_surfaces": a2ui_surfaces,
        "response_parts": response_parts,
        "method_compare_data": method_compare_data,
        "run_latency_ms": run_latency_ms,
        "delegation_rounds": delegation_execution["rounds"],
        "phase_path": phase_path,
        "used_document_rag": used_document_rag,
        "ask_human_requests": extract_human_requests(messages),
        "todos": todos,
        "agent_plan": agent_plan,
        "leader_tool_names": registered_tool_names,
        "output_messages": messages if isinstance(messages, list) else [],
        "todo_scheduler_hint": (
            todo_scheduler_hint if isinstance(todo_scheduler_hint, dict) else None
        ),
    }
