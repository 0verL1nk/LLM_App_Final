"""Canonical Agent-turn use case for the web research workspace."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..adapters.orm.run_repository import (
    append_run_item_event,
    append_run_lifecycle_event,
    claim_run_execution,
    get_run,
    update_run_status,
)
from ..adapters.orm.task_dispatch_repository import create_leader_run
from ..adapters.rag import DynamicProjectEvidenceService
from ..adapters.sqlite.project_repository import (
    list_project_files,
    list_project_session_messages,
    list_project_sessions,
    save_project_session_messages,
)
from ..adapters.sqlite.rag_ingestion_repository import list_ready_project_documents
from ..adapters.user_settings import (
    read_api_key_for_user,
    read_base_url_for_user,
    read_model_name_for_user,
)
from ..context_governance import build_context_usage_snapshot
from ..llm_provider import build_openai_compatible_chat_model
from ..memory.store import search_project_memory_items
from ..profiles import profile_for_execution_mode
from ..session_factory import (
    AgentDependencies,
    AgentRuntimeOptions,
    AgentSession,
    create_agent_session,
)
from .agent_center.controller import build_turn_context
from .agent_center.facade import (
    AgentCenterRuntimeDeps,
    AgentCenterTurnRequest,
    execute_agent_center_turn,
)
from .agent_center.memory import enqueue_turn_memory_consolidation
from .continuation_messages import build_continuation_tool_message
from .contracts import EmptyModelOutputError, EventCallback
from .execution_routing import resolve_execution_route
from .run_timeline import project_presentation_item_event, project_runtime_item_event
from .session_titles import enqueue_session_title_generation
from .steering_inputs import (
    delivered_steering_inputs,
    move_unconfirmed_inputs_to_followup,
    queue_steering_input,
    unconfirmed_steering_inputs,
)
from .workspace import require_project


def _require_session(*, project_uid: str, session_uid: str, user_uuid: str) -> dict[str, Any]:
    """Validate the project exists and contains the given session; return the project."""
    project = require_project(project_uid=project_uid, user_uuid=user_uuid)
    if not any(
        str(item.get("session_uid") or "") == session_uid
        for item in list_project_sessions(project_uid=project_uid, uuid=user_uuid)
    ):
        raise LookupError("Session not found")
    return project


@dataclass
class _RuntimeEntry:
    session: AgentSession
    evidence: DynamicProjectEvidenceService
    scope: tuple[str, ...]
RuntimeKey = tuple[str, str, str, str]
class ResearchWorkspaceService:
    """Own cached Agent runtimes while persistence remains in domain adapters."""

    def __init__(self) -> None:
        self._entries: dict[RuntimeKey, _RuntimeEntry] = {}
        self._locks: dict[RuntimeKey, threading.Lock] = {}
        self._guard = threading.RLock()
    def _lock_for(self, key: RuntimeKey) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())
    def _runtime(
        self, *, project_uid: str, session_uid: str, user_uuid: str, resolved_mode: str = "agent_teams"
    ) -> _RuntimeEntry:
        key = (user_uuid, project_uid, session_uid, resolved_mode)
        project = _require_session(
            project_uid=project_uid, session_uid=session_uid, user_uuid=user_uuid
        )
        documents = list_project_files(project_uid=project_uid, uuid=user_uuid, active_only=True)
        scope = tuple(sorted(str(item.get("uid") or "") for item in documents))
        with self._guard:
            existing = self._entries.get(key)
            if existing is not None:
                existing.evidence.update_scope(list(scope))
                existing.scope = scope
                return existing
        api_key = read_api_key_for_user(uuid=user_uuid)
        model_name = read_model_name_for_user(uuid=user_uuid)
        if not api_key or not model_name:
            raise ValueError("Model provider is not configured")
        evidence = DynamicProjectEvidenceService(
            project_uid=project_uid,
            user_uuid=user_uuid,
            doc_uids=list(scope),
        )
        model = build_openai_compatible_chat_model(
            api_key=api_key,
            model_name=model_name,
            base_url=read_base_url_for_user(uuid=user_uuid),
        )
        scope_summary = "项目资料库可用；需要查看文件目录时调用 list_document"
        session = create_agent_session(
            profile=profile_for_execution_mode(resolved_mode),
            deps=AgentDependencies(
                search_document_fn=evidence.search_text,
                search_document_evidence_fn=evidence.search,
                list_documents_fn=evidence.list_documents,
                read_document_by_id_fn=evidence.read_document,
                project_uid=project_uid,
                session_uid=session_uid,
                user_uuid=user_uuid,
            ),
            options=AgentRuntimeOptions(
                llm=model,
                project_name=str(project.get("project_name") or "未命名项目"),
                document_name=None,
                scope_summary=scope_summary,
            ),
        )
        entry = _RuntimeEntry(session=session, evidence=evidence, scope=scope)
        with self._guard:
            prior = self._entries.get(key)
            if prior is not None:
                session.close()
                prior.evidence.update_scope(list(scope))
                prior.scope = scope
                return prior
            self._entries[key] = entry
        return entry
    def prepare_turn_run(
        self,
        *,
        project_uid: str,
        session_uid: str,
        user_uuid: str,
        prompt: str,
        client_request_id: str,
        enqueue_task_delivery_fn: Callable[[str], Any] | None,
        execution_mode: str = "auto",
    ) -> dict[str, Any]:
        """Persist the user command and enqueue an independently observable run."""
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Prompt is required")
        _require_session(
            project_uid=project_uid, session_uid=session_uid, user_uuid=user_uuid
        )
        ready_count = len(list_ready_project_documents(project_uid=project_uid, uuid=user_uuid))
        route = resolve_execution_route(
            prompt=normalized_prompt, requested_mode=execution_mode, document_count=ready_count
        )
        run, leader_task, created = create_leader_run(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            client_request_id=client_request_id,
            prompt=normalized_prompt,
            input_payload={
                "project_uid": project_uid,
                "session_uid": session_uid,
                "user_uuid": user_uuid,
                "prompt": normalized_prompt,
                "requested_mode": route.requested_mode,
                "resolved_mode": route.resolved_mode,
                "route_reason": route.reason,
            },
            requested_mode=route.requested_mode,
            resolved_mode=route.resolved_mode,
            route_reason=route.reason,
        )
        if not created:
            return run
        key = (user_uuid, project_uid, session_uid, "agent_teams")
        with self._lock_for(key):
            messages = list_project_session_messages(
                session_uid=session_uid,
                project_uid=project_uid,
                uuid=user_uuid,
            )
            messages.append({"role": "user", "content": normalized_prompt})
            save_project_session_messages(
                session_uid=session_uid,
                project_uid=project_uid,
                uuid=user_uuid,
                messages=messages,
            )
        try:
            if enqueue_task_delivery_fn is not None:
                enqueue_task_delivery_fn(str(leader_task["task_uid"]))
        except Exception as exc:
            update_run_status(run_uid=str(run["run_uid"]), status="failed", error_message=str(exc))
            append_run_lifecycle_event(
                run_uid=str(run["run_uid"]),
                event_type="run.failed",
                payload={"message": "Run could not be queued"},
            )
            raise
        return run
    def execute_turn(
        self,
        *,
        project_uid: str,
        session_uid: str,
        user_uuid: str,
        prompt: str,
        on_event: EventCallback | None = None,
        user_message_persisted: bool = False,
        run_uid: str | None = None,
        steering_initial_delivery: bool = False,
        leader_task_uid: str | None = None,
        input_messages: list[Any] | None = None,
        resolved_mode: str = "agent_teams",
    ) -> dict[str, Any]:
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Prompt is required")
        key = (user_uuid, project_uid, session_uid, resolved_mode)
        with self._lock_for(key):
            entry = self._runtime(
                project_uid=project_uid,
                session_uid=session_uid,
                user_uuid=user_uuid,
                resolved_mode=resolved_mode,
            )
            turn_context = build_turn_context(
                prompt=normalized_prompt,
                user_uuid=user_uuid,
                project_uid=project_uid,
                search_project_memory_items_fn=search_project_memory_items,
            )
            result = execute_agent_center_turn(
                request=AgentCenterTurnRequest(
                    prompt=normalized_prompt,
                    turn_context=turn_context,
                    input_messages=input_messages,
                ),
                deps=AgentCenterRuntimeDeps(
                    leader_agent=entry.session.agent,
                    leader_runtime_config={
                        "configurable": {
                            **entry.session.runtime_config["configurable"],
                            **({"run_uid": run_uid} if run_uid else {}),
                            **({"task_uid": leader_task_uid} if leader_task_uid else {}),
                            "task_db_name": "./database.sqlite",
                            "steering_db_name": "./database.sqlite",
                            "steering_initial_delivery": steering_initial_delivery,
                        }
                    },
                    search_document_evidence_fn=entry.evidence.search,
                    leader_tool_specs=entry.session.tool_specs,
                ),
                on_event=on_event,
            )
            public_result = {
                key: value for key, value in result.items() if key != "output_messages"
            }
            messages = list_project_session_messages(
                session_uid=session_uid,
                project_uid=project_uid,
                uuid=user_uuid,
            )
            delivered_inputs = (
                delivered_steering_inputs(run_uid=run_uid) if run_uid else []
            )
            context_messages = list(messages)
            if not user_message_persisted and input_messages is None:
                context_messages.append({"role": "user", "content": normalized_prompt})
            context_messages.extend(
                {"role": "user", "content": str(item["text"])}
                for item in delivered_inputs
            )
            public_result["context_snapshot"] = {
                "memory_items": list(turn_context.get("memory_items") or []),
                "project_scope": {"ready_document_count": len(entry.evidence.list_documents())},
                "session_context": build_context_usage_snapshot(
                    messages=context_messages,
                    tool_specs=entry.session.tool_specs,
                ),
            }
            if not user_message_persisted and input_messages is None:
                messages.append({"role": "user", "content": normalized_prompt})
            messages.extend(
                {"role": "user", "content": str(item["text"])}
                for item in delivered_inputs
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": result["answer"],
                    "trace": result["trace_payload"],
                    "evidence": result["evidence_items"],
                    "retrieved_evidence": result["retrieved_evidence_items"],
                    "plan": result.get("plan"),
                    "a2ui": [],
                    "parts": result.get("response_parts", []),
                    "context_snapshot": public_result["context_snapshot"],
                }
            )
            save_project_session_messages(
                session_uid=session_uid,
                project_uid=project_uid,
                uuid=user_uuid,
                messages=messages,
            )
            if input_messages is None:
                enqueue_turn_memory_consolidation(
                    user_uuid=user_uuid,
                    project_uid=project_uid,
                    session_uid=session_uid,
                    prompt=normalized_prompt,
                    answer=result["answer"],
                )
                enqueue_session_title_generation(
                    user_uuid=user_uuid,
                    project_uid=project_uid,
                    session_uid=session_uid,
                    prompt=normalized_prompt,
                    answer=result["answer"],
                )
        return public_result
    def execute_continuation_turn(
        self,
        *,
        project_uid: str,
        session_uid: str,
        user_uuid: str,
        parent_task_uid: str,
        tool_results: list[dict[str, Any]], evidence_merge: dict[str, Any] | None = None,
        on_event: EventCallback | None = None,
        run_uid: str | None = None,
        resolved_mode: str = "agent_teams",
    ) -> dict[str, Any]:
        """Resume the original Leader thread with validated child ToolMessages."""
        messages = [
            build_continuation_tool_message(item, evidence_merge=evidence_merge if index == 0 else None)
            for index, item in enumerate(tool_results)
        ]
        return self.execute_turn(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            prompt="请整合已完成的子研究任务结果并继续回答用户。",
            on_event=on_event,
            user_message_persisted=True,
            run_uid=run_uid,
            leader_task_uid=parent_task_uid,
            input_messages=messages,
            resolved_mode=resolved_mode,
        )

    def queue_steering_input(
        self,
        *,
        project_uid: str,
        session_uid: str,
        user_uuid: str,
        prompt: str,
        client_request_id: str,
    ) -> dict[str, Any]:
        """Persist a running-turn follow-up after validating workspace ownership."""
        _require_session(
            project_uid=project_uid, session_uid=session_uid, user_uuid=user_uuid
        )
        input_item, _created = queue_steering_input(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            client_request_id=client_request_id,
            text=prompt,
        )
        return input_item

    def prepare_steering_followup_run(
        self,
        *,
        source_run_uid: str,
        project_uid: str,
        session_uid: str,
        user_uuid: str,
    ) -> dict[str, Any] | None:
        """Create one idempotent successor Run for inputs not consumed before final text."""
        if not unconfirmed_steering_inputs(run_uid=source_run_uid):
            return None
        run, leader_task, _created = create_leader_run(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            client_request_id=f"steering-followup:{source_run_uid}",
            prompt="请继续处理用户在上一轮研究结束前补充的要求。",
            input_payload={
                "project_uid": project_uid,
                "session_uid": session_uid,
                "user_uuid": user_uuid,
                "prompt": "请继续处理用户在上一轮研究结束前补充的要求。",
                "steering_initial_delivery": True,
            },
        )
        moved = move_unconfirmed_inputs_to_followup(
            source_run_uid=source_run_uid,
            target_run_uid=str(run["run_uid"]),
        )
        if not moved:
            return None
        run["leader_task_uid"] = str(leader_task["task_uid"])
        return run

    def close(self) -> None:
        with self._guard:
            entries = list(self._entries.values())
            self._entries.clear()
        for entry in entries:
            entry.session.close()

    def invalidate_user(self, user_uuid: str) -> None:
        with self._guard:
            keys = [key for key in self._entries if key[0] == user_uuid]
            entries = [self._entries.pop(key) for key in keys]
        for entry in entries:
            entry.session.close()


research_workspace_service = ResearchWorkspaceService()


def _event_type_for_trace(event: dict[str, Any]) -> str:
    performative = str(event.get("performative") or "")
    return {
        "tool_call": "tool.execution.started",
        "tool_result": "tool.execution.completed",
        "delegate_task": "agent.spawned",
        "delegate_result": "agent.completed",
    }.get(performative, "step.progress")


def execute_research_run(
    *,
    run_uid: str,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    prompt: str,
    leader_task_uid: str | None = None,
    steering_initial_delivery: bool = False,
    resolved_mode: str = "agent_teams",
) -> dict[str, Any]:
    """Queue worker entry point that persists every public runtime event."""
    if not claim_run_execution(run_uid=run_uid):
        return {"waiting_children": False}
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.started", payload={"status": "running"})

    def record_event(event: dict[str, Any]) -> None:
        if str(event.get("performative") or "") == "a2ui_surface_ready":
            metadata: dict[str, Any] = (
                dict(event["metadata"]) if isinstance(event.get("metadata"), dict) else {}
            )
            surface = metadata.get("surface")
            if isinstance(surface, dict):
                _append_surface_events(run_uid=run_uid, surface=surface, part_id=str(metadata.get("part_id") or ""))
            return
        item_event = project_runtime_item_event(event)
        if item_event is not None:
            append_run_item_event(
                run_uid=run_uid,
                item_uid=str(item_event["item_uid"]),
                item_type=str(item_event["item_type"]),
                status=str(item_event["status"]),
                event_type=str(item_event["event_type"]),
                payload=dict(item_event["payload"]),
                task_uid=item_event.get("task_uid"),
            )

    try:
        result = research_workspace_service.execute_turn(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            prompt=prompt,
            on_event=record_event,
            user_message_persisted=True,
            run_uid=run_uid,
            leader_task_uid=leader_task_uid,
            steering_initial_delivery=steering_initial_delivery,
            resolved_mode=resolved_mode,
        )
    except Exception as exc:
        update_run_status(run_uid=run_uid, status="failed", error_message=str(exc))
        public_message = (
            "模型未返回有效内容，自动重试后仍然失败，请重新发送"
            if isinstance(exc, EmptyModelOutputError)
            else "模型执行失败，请稍后重试"
        )
        append_run_lifecycle_event(
            run_uid=run_uid,
            event_type="run.failed",
            payload={"message": public_message},
        )
        raise
    _complete_response_part_items(run_uid=run_uid, result=result)
    from ..adapters.orm.task_parent_repository import has_nonterminal_child_tasks

    waiting_children = bool(
        leader_task_uid
        and has_nonterminal_child_tasks(parent_task_uid=leader_task_uid)
    )
    update_run_status(
        run_uid=run_uid,
        status="waiting_children" if waiting_children else "completed",
    )
    append_run_lifecycle_event(
        run_uid=run_uid,
        event_type="run.waiting_children" if waiting_children else "run.completed",
        payload={"result": result} if not waiting_children else {"status": "waiting_children"},
    )
    followup = research_workspace_service.prepare_steering_followup_run(
        source_run_uid=run_uid,
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid=user_uuid,
    )
    if followup is not None:
        from .task_delivery import dispatch_task

        dispatch_task(task_uid=str(followup["leader_task_uid"]))
    return {"waiting_children": waiting_children}


def execute_research_continuation(
    *,
    continuation_task_uid: str,
    run_uid: str,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    parent_task_uid: str,
    tool_results: list[dict[str, Any]],
    evidence_merge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resume a waiting Run after all child packets are durably available."""
    update_run_status(run_uid=run_uid, status="running")
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.resumed", payload={"task_uid": continuation_task_uid})

    def record_event(event: dict[str, Any]) -> None:
        item_event = project_runtime_item_event(event)
        if item_event is None:
            return
        append_run_item_event(
            run_uid=run_uid,
            item_uid=str(item_event["item_uid"]),
            item_type=str(item_event["item_type"]),
            status=str(item_event["status"]),
            event_type=str(item_event["event_type"]),
            payload=dict(item_event["payload"]),
            task_uid=item_event.get("task_uid"),
        )

    run = get_run(run_uid=run_uid, user_uuid=user_uuid)
    resolved_mode = str((run or {}).get("resolved_mode") or "react")
    try:
        result = research_workspace_service.execute_continuation_turn(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            parent_task_uid=parent_task_uid,
            tool_results=tool_results,
            evidence_merge=evidence_merge,
            on_event=record_event,
            run_uid=run_uid,
            resolved_mode=resolved_mode,
        )
    except Exception as exc:
        update_run_status(run_uid=run_uid, status="failed", error_message=str(exc))
        append_run_lifecycle_event(
            run_uid=run_uid,
            event_type="run.failed",
            payload={"message": "子研究结果整合失败，请重试。"},
        )
        raise
    _complete_response_part_items(run_uid=run_uid, result=result)
    update_run_status(run_uid=run_uid, status="completed")
    append_run_lifecycle_event(run_uid=run_uid, event_type="run.completed", payload={"result": result})
    return {"summary": str(result.get("answer") or "研究结果已整合"), "parent_task_uid": parent_task_uid}


__all__ = [
    "ResearchWorkspaceService",
    "execute_research_continuation",
    "execute_research_run",
    "research_workspace_service",
]


def _append_surface_events(
    *,
    run_uid: str,
    surface: dict[str, Any],
    part_id: str,
    data_only: bool = False,
) -> None:
    """Persist catalog messages for one anchored UI surface in stream order."""
    messages = surface.get("messages")
    if not isinstance(messages, list):
        return
    metadata: dict[str, Any] = {
        "catalogId": surface.get("catalogId"),
        "surfaceId": surface.get("surfaceId"),
        "title": surface.get("title"),
    }
    if part_id:
        metadata["partId"] = part_id
    selected_messages = messages[-1:] if data_only else messages
    for envelope in selected_messages:
        if isinstance(envelope, dict):
            item_event = project_presentation_item_event(
                part_id=part_id,
                envelope=envelope,
                surface=metadata,
            )
            append_run_item_event(
                run_uid=run_uid,
                item_uid=str(item_event["item_uid"]),
                item_type=str(item_event["item_type"]),
                status=str(item_event["status"]),
                event_type=str(item_event["event_type"]),
                payload=dict(item_event["payload"]),
            )


def _complete_response_part_items(*, run_uid: str, result: dict[str, Any]) -> None:
    """Mark persisted text/reasoning parts terminal once the Run completed safely."""
    response_parts = result.get("response_parts")
    if not isinstance(response_parts, list):
        return
    for part in response_parts:
        if not isinstance(part, dict):
            continue
        part_id = str(part.get("id") or "").strip()
        part_type = str(part.get("type") or "")
        text = part.get("text")
        if not part_id:
            continue
        if part_type == "component":
            append_run_item_event(
                run_uid=run_uid,
                item_uid=f"item_component_{part_id}",
                item_type="component",
                status="completed",
                event_type="item.completed",
                payload={
                    "partId": part_id,
                    "component": str(part.get("component") or "research-map"),
                    "state": str(part.get("state") or "ready"),
                    "xml": str(part.get("xml") or ""),
                },
            )
            continue
        if not isinstance(text, str) or part_type not in {"markdown", "reasoning"}:
            continue
        item_type = "assistant_message" if part_type == "markdown" else "reasoning_summary"
        append_run_item_event(
            run_uid=run_uid,
            item_uid=f"item_{item_type}_{part_id}",
            item_type=item_type,
            status="completed",
            event_type="item.completed",
            payload={"partId": part_id, "text": text},
        )
