import json
import logging
import re
import time
from typing import Any

from ..domain.human_request import extract_human_requests
from ..domain.trace import TraceEvent, phase_label_from_performative
from ..method_compare_parser import parse_method_compare_payload
from .a2ui_fragments import A2UIFragmentStreamParser, PresentationDecision
from .contracts import EventCallback, SearchDocumentFn, TurnCoreResult
from .ports import AgentInvoker, EvidenceRetriever
from .response_stream import ResponseStreamPartRouter
from .turn_runtime import build_phase_path, execute_agent_with_streaming

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
    input_messages: list[Any] | None = None,
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
    reasoning_part_id = "reasoning-0"
    reasoning_part_inserted = False
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
        pending_surface_part_id = f"component-{len(fragments)}"
        response_parts.append(
            {
                "id": pending_surface_part_id,
                "type": "component",
                "component": "research-map",
                "state": "streaming",
            }
        )
        _collect_event(
            {
                "performative": "answer_part_insert",
                "metadata": {
                    "part_id": pending_surface_part_id,
                    "part_type": "component",
                    "component": "research-map",
                },
            }
        )
        text_part_id = f"text-{len(fragments) + 1}"

    def emit_reasoning_text(text: str) -> None:
        nonlocal reasoning_part_inserted
        if not text:
            return
        if not reasoning_part_inserted:
            reasoning_part_inserted = True
            response_parts.append({"id": reasoning_part_id, "type": "reasoning", "text": ""})
            _collect_event(
                {
                    "performative": "answer_part_insert",
                    "metadata": {"part_id": reasoning_part_id, "part_type": "reasoning"},
                }
            )
        for part in response_parts:
            if part.get("id") == reasoning_part_id:
                part["text"] += text
                break
        _collect_event(
            {
                "performative": "answer_part_delta",
                "content": text,
                "metadata": {"part_id": reasoning_part_id},
            }
        )

    def emit_surface(fragment: PresentationDecision) -> None:
        if not pending_surface_part_id:
            logger.warning("Discarded inline UI fragment without an insertion anchor")
            return
        # Content-only contract: persist the fragment exactly as authored and
        # let the frontend renderer own parsing, validation, and drawing.
        fragments.append((pending_surface_part_id, fragment))
        for part in response_parts:
            if part.get("id") == pending_surface_part_id:
                part["state"] = "ready"
                part["xml"] = fragment.raw_xml
                break
        _collect_event(
            {
                "performative": "answer_part_delta",
                "content": fragment.raw_xml,
                "metadata": {
                    "part_id": pending_surface_part_id,
                    "part_type": "component",
                    "part_state": "ready",
                },
            }
        )

    def report_surface_failure(message: str) -> None:
        if not pending_surface_part_id:
            logger.warning("Discarded inline UI fragment: %s", message)
            return
        # The part stays in storage with an error state instead of being
        # dropped: the renderer shows a note and the raw text survives.
        for part in response_parts:
            if part.get("id") == pending_surface_part_id and part.get("state") == "streaming":
                part["state"] = "error"
                part["error"] = message
                break
        _collect_event(
            {
                "performative": "answer_part_delta",
                "content": "",
                "metadata": {
                    "part_id": pending_surface_part_id,
                    "part_type": "component",
                    "part_state": "error",
                    "error": message,
                },
            }
        )

    parser = A2UIFragmentStreamParser(
        on_text=emit_visible_text,
        on_fragment_start=insert_surface_part,
        on_fragment=emit_surface,
        on_error=report_surface_failure,
    )
    response_router = ResponseStreamPartRouter(
        on_text=parser.feed,
        on_reasoning=emit_reasoning_text,
    )

    def ingest_delta(event: TraceEvent) -> None:
        nonlocal streamed_text_seen
        content = str(event.get("content") or "")
        if content:
            streamed_text_seen = True
            response_router.feed(content)

    initial_messages = input_messages or [{"role": "user", "content": prompt}]
    result = execute_agent_with_streaming(
        leader_agent=leader_agent,
        input_messages=initial_messages,
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
        response_router.feed(answer)
    response_router.finish()
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
    if (
        not evidence_items
        and (referenced_chunk_ids or referenced_doc_uids)
        and used_document_rag
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
    run_latency_ms = (time.perf_counter() - run_started) * 1000.0
    phase_path = build_phase_path(phase_labels=phase_labels, answer=answer, messages=messages)

    # P3-lite deterministic citation audit: evidence was retrieved but the
    # answer cites none of it. Annotation only (streamed deltas already left
    # the building); regeneration belongs to the durable-runtime reviewer
    # pass. Feeds the feedback-loop evidence_gap signal.
    citation_audit = "not_applicable"
    if retrieved_evidence_items:
        cited = bool(referenced_chunk_ids or referenced_doc_uids)
        citation_audit = "passed" if cited else "failed"
        if citation_audit == "failed":
            logger.warning(
                "TURN_CITATION_AUDIT failed: %s evidence items retrieved, answer cites none",
                len(retrieved_evidence_items),
            )

    return {
        "answer": answer,
        "citation_audit": citation_audit,
        "policy_decision": {
            "plan_enabled": bool(plan_payload),
            "reason": "runtime-observed",
            "source": "runtime",
        },
        "trace_payload": trace_payload,
        "plan": _maybe_to_dict(plan_payload),
        "runtime_state": _maybe_to_dict(runtime_state_payload),
        "evidence_items": evidence_items,
        "retrieved_evidence_items": retrieved_evidence_items,
        "response_parts": response_parts,
        "method_compare_data": method_compare_data,
        "run_latency_ms": run_latency_ms,
        "phase_path": phase_path,
        "used_document_rag": used_document_rag,
        "ask_human_requests": extract_human_requests(messages),
        "leader_tool_names": registered_tool_names,
        "output_messages": messages if isinstance(messages, list) else [],
    }
