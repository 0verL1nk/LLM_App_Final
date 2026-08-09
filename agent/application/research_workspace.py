"""Canonical Agent-turn use case for the web research workspace."""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..adapters.rag import DynamicProjectEvidenceService
from ..adapters.sqlite.project_repository import (
    list_project_files,
    list_project_session_messages,
    list_project_sessions,
    save_project_session_messages,
)
from ..adapters.sqlite.run_repository import (
    append_run_event,
    create_run,
    update_run_status,
)
from ..adapters.user_settings import (
    read_api_key_for_user,
    read_base_url_for_user,
    read_model_name_for_user,
)
from ..llm_provider import build_openai_compatible_chat_model
from ..memory.store import search_project_memory_items
from ..profiles import paper_leader_profile
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
from .contracts import EmptyModelOutputError, EventCallback
from .run_timeline import project_runtime_event
from .session_titles import enqueue_session_title_generation
from .workspace import require_project


@dataclass
class _RuntimeEntry:
    session: AgentSession
    evidence: DynamicProjectEvidenceService
    scope: tuple[str, ...]


class ResearchWorkspaceService:
    """Own cached Agent runtimes while persistence remains in domain adapters."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], _RuntimeEntry] = {}
        self._locks: dict[tuple[str, str, str], threading.Lock] = {}
        self._guard = threading.RLock()

    def _lock_for(self, key: tuple[str, str, str]) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())

    def _runtime(self, *, project_uid: str, session_uid: str, user_uuid: str) -> _RuntimeEntry:
        key = (user_uuid, project_uid, session_uid)
        project = require_project(project_uid=project_uid, user_uuid=user_uuid)
        if not any(
            str(item.get("session_uid") or "") == session_uid
            for item in list_project_sessions(project_uid=project_uid, uuid=user_uuid)
        ):
            raise LookupError("Session not found")
        documents = list_project_files(
            project_uid=project_uid,
            uuid=user_uuid,
            active_only=True,
        )
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
        # The document catalogue is intentionally tool-mediated.  Feeding file
        # names into the system prompt scales poorly and makes a stale static
        # list look authoritative; the agent can call list_document on demand.
        scope_summary = "项目资料库可用；需要查看文件目录时调用 list_document"
        session = create_agent_session(
            profile=paper_leader_profile,
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
        enqueue_background_fn: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        """Persist the user command and enqueue an independently observable run."""
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Prompt is required")
        require_project(project_uid=project_uid, user_uuid=user_uuid)
        if not any(
            str(item.get("session_uid") or "") == session_uid
            for item in list_project_sessions(project_uid=project_uid, uuid=user_uuid)
        ):
            raise LookupError("Session not found")
        run, created = create_run(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            client_request_id=client_request_id,
            prompt=normalized_prompt,
        )
        if not created:
            return run

        key = (user_uuid, project_uid, session_uid)
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
            enqueue_background_fn(
                execute_research_run,
                run_uid=str(run["run_uid"]),
                project_uid=project_uid,
                session_uid=session_uid,
                user_uuid=user_uuid,
                prompt=normalized_prompt,
            )
        except Exception as exc:
            update_run_status(run_uid=str(run["run_uid"]), status="failed", error_message=str(exc))
            append_run_event(
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
    ) -> dict[str, Any]:
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("Prompt is required")
        key = (user_uuid, project_uid, session_uid)
        with self._lock_for(key):
            entry = self._runtime(
                project_uid=project_uid,
                session_uid=session_uid,
                user_uuid=user_uuid,
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
                ),
                deps=AgentCenterRuntimeDeps(
                    leader_agent=entry.session.agent,
                    leader_runtime_config=entry.session.runtime_config,
                    search_document_evidence_fn=entry.evidence.search,
                    leader_tool_specs=entry.session.tool_specs,
                ),
                on_event=on_event,
            )
            public_result = {
                key: value for key, value in result.items() if key != "output_messages"
            }
            public_result["context_snapshot"] = {
                "memory_items": list(turn_context.get("memory_items") or []),
                "project_scope": {"ready_document_count": len(entry.evidence.list_documents())},
            }
            messages = list_project_session_messages(
                session_uid=session_uid,
                project_uid=project_uid,
                uuid=user_uuid,
            )
            if not user_message_persisted:
                messages.append({"role": "user", "content": normalized_prompt})
            messages.append(
                {
                    "role": "assistant",
                    "content": result["answer"],
                    "trace": result["trace_payload"],
                    "evidence": result["evidence_items"],
                    "retrieved_evidence": result["retrieved_evidence_items"],
                    "delegation": result["delegation_execution"],
                    "plan": result.get("agent_plan") or result.get("plan"),
                    "todos": result.get("todos", []),
                    "a2ui": result.get("a2ui_surfaces", []),
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
) -> None:
    """Queue worker entry point that persists every public runtime event."""
    update_run_status(run_uid=run_uid, status="running")
    append_run_event(run_uid=run_uid, event_type="run.started", payload={"status": "running"})

    def record_event(event: dict[str, Any]) -> None:
        if str(event.get("performative") or "") == "a2ui_surface_ready":
            metadata: dict[str, Any] = (
                dict(event["metadata"]) if isinstance(event.get("metadata"), dict) else {}
            )
            surface = metadata.get("surface") if isinstance(metadata.get("surface"), dict) else None
            part_id = str(metadata.get("part_id") or "")
            if surface is not None:
                _append_surface_events(run_uid=run_uid, surface=surface, part_id=part_id)
            return
        event_type, payload = project_runtime_event(event)
        append_run_event(
            run_uid=run_uid,
            event_type=event_type,
            payload=payload,
        )

    try:
        result = research_workspace_service.execute_turn(
            project_uid=project_uid,
            session_uid=session_uid,
            user_uuid=user_uuid,
            prompt=prompt,
            on_event=record_event,
            user_message_persisted=True,
        )
    except Exception as exc:
        update_run_status(run_uid=run_uid, status="failed", error_message=str(exc))
        public_message = (
            "模型未返回有效内容，自动重试后仍然失败，请重新发送"
            if isinstance(exc, EmptyModelOutputError)
            else "模型执行失败，请稍后重试"
        )
        append_run_event(
            run_uid=run_uid,
            event_type="run.failed",
            payload={"message": public_message},
        )
        raise
    a2ui_surfaces = result.get("a2ui_surfaces") if isinstance(result, dict) else None
    if not isinstance(a2ui_surfaces, list) and isinstance(result, dict):
        legacy_surface = result.get("a2ui_surface")
        a2ui_surfaces = [legacy_surface] if isinstance(legacy_surface, dict) else []
    if isinstance(a2ui_surfaces, list):
        for surface in a2ui_surfaces:
            if isinstance(surface, dict):
                _append_surface_events(
                    run_uid=run_uid,
                    surface=surface,
                    part_id=str(surface.get("partId") or ""),
                    data_only=True,
                )
    update_run_status(run_uid=run_uid, status="completed")
    append_run_event(
        run_uid=run_uid,
        event_type="run.completed",
        payload={"result": result},
    )


__all__ = ["ResearchWorkspaceService", "execute_research_run", "research_workspace_service"]


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
            append_run_event(
                run_uid=run_uid,
                event_type="ui.a2ui",
                payload={"envelope": envelope, "surface": metadata},
            )
