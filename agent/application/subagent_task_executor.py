"""Execution of one durable, first-level research subagent task."""

from __future__ import annotations

from typing import Any

from ..adapters.orm.task_query_repository import get_agent_task_run_context
from ..adapters.rag import DynamicProjectEvidenceService
from ..adapters.sqlite.project_repository import list_project_files
from ..adapters.user_settings import (
    read_api_key_for_user,
    read_base_url_for_user,
    read_model_name_for_user,
)
from ..domain.agent_task import EvidencePacket
from ..llm_provider import build_openai_compatible_chat_model
from ..profiles import AgentProfile
from ..session_factory import AgentDependencies, AgentRuntimeOptions, create_agent_session
from ..subagent.loader import SubAgentDefinition
from .agent_center.facade import (
    AgentCenterRuntimeDeps,
    AgentCenterTurnRequest,
    execute_agent_center_turn,
)
from .workspace import require_project


def execute_subagent_task_payload(
    task: dict[str, Any],
    *,
    definition: SubAgentDefinition,
    db_name: str = "./database.sqlite",
) -> dict[str, Any]:
    """Execute a leased child task in its own scoped Agent session.

    The task's Run is the source of truth for ownership. Child definitions only
    contribute a bounded capability manifest and prompt; they cannot recursively
    delegate work because their profile omits the delegation middleware.
    """
    task_uid = str(task.get("task_uid") or "").strip()
    if not task_uid:
        raise ValueError("Subagent task UID is required")
    context = get_agent_task_run_context(task_uid=task_uid, db_name=db_name)
    if context is None:
        raise LookupError("Subagent task not found")
    if str(context.get("kind") or "") != "subagent":
        raise ValueError("Task is not a subagent task")
    if str(context.get("agent_role") or "") != definition.name:
        raise ValueError("Subagent role does not match task")
    task_input = context.get("input") if isinstance(context.get("input"), dict) else {}
    objective = str(task_input.get("objective") or "").strip()
    if not objective:
        raise ValueError("Subagent task objective is required")

    project_uid = str(context["project_uid"])
    session_uid = str(context["session_uid"])
    user_uuid = str(context["user_uuid"])
    project = require_project(project_uid=project_uid, user_uuid=user_uuid, db_name=db_name)
    documents = list_project_files(project_uid=project_uid, uuid=user_uuid, active_only=True, db_name=db_name)
    evidence = DynamicProjectEvidenceService(
        project_uid=project_uid,
        user_uuid=user_uuid,
        doc_uids=[str(item.get("uid") or "") for item in documents if str(item.get("uid") or "")],
    )
    session = create_agent_session(
        profile=_profile_for(definition),
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
            llm=_model_for_user(user_uuid),
            project_name=str(project.get("project_name") or "未命名项目"),
            scope_summary="项目资料库可用；需要查看文件目录时调用 list_document",
            thread_id=f"subagent:{task_uid}",
        ),
    )
    try:
        result = execute_agent_center_turn(
            request=AgentCenterTurnRequest(prompt=objective),
            deps=AgentCenterRuntimeDeps(
                leader_agent=session.agent,
                leader_runtime_config={"configurable": {**session.runtime_config["configurable"], "task_uid": task_uid}},
                search_document_evidence_fn=evidence.search,
                leader_tool_specs=session.tool_specs,
            ),
        )
    finally:
        session.close()
    return _sanitize_result(
        result,
        project_uid=project_uid,
        allowed_doc_uids={str(item.get("uid") or "") for item in documents},
    )


def _profile_for(definition: SubAgentDefinition) -> AgentProfile:
    """Build a bounded child profile without inheriting Leader-only middleware."""
    return AgentProfile(
        name=definition.name,
        description=definition.description,
        prompt_builder=lambda **_kwargs: definition.system_prompt,
        capability_ids=definition.capability_ids,
        middleware_ids=("trace", "llm_logger"),
    )


def _model_for_user(user_uuid: str) -> Any:
    """Build the user-configured provider model without persisting credentials."""
    api_key = read_api_key_for_user(uuid=user_uuid)
    model_name = read_model_name_for_user(uuid=user_uuid)
    if not api_key or not model_name:
        raise ValueError("Model provider is not configured")
    return build_openai_compatible_chat_model(
        api_key=api_key,
        model_name=model_name,
        base_url=read_base_url_for_user(uuid=user_uuid),
    )


def _sanitize_result(
    result: dict[str, Any],
    *,
    project_uid: str,
    allowed_doc_uids: set[str],
) -> dict[str, Any]:
    """Persist only the result contract needed by a future parent continuation."""
    answer = str(result.get("answer") or "").strip()
    if not answer:
        raise RuntimeError("Subagent execution completed without a final answer")
    evidence_refs: list[str] = []
    evidence: list[dict[str, Any]] = []
    for item in result.get("evidence_items") or []:
        if not isinstance(item, dict):
            continue
        doc_uid = str(item.get("doc_uid") or "").strip()
        chunk_id = str(item.get("chunk_id") or "").strip()
        if (
            str(item.get("project_uid") or "").strip() != project_uid
            or not doc_uid
            or doc_uid not in allowed_doc_uids
            or not chunk_id
        ):
            continue
        if chunk_id in evidence_refs:
            continue
        evidence_refs.append(chunk_id)
        evidence.append(
            {
                "chunk_id": chunk_id,
                "doc_uid": doc_uid,
                "page_no": item.get("page_no"),
                "offset_start": item.get("offset_start"),
                "offset_end": item.get("offset_end"),
            }
        )
    EvidencePacket.model_validate({
        "summary": answer[:6000],
        "evidence_refs": evidence_refs,
        "claims": [],
        "evidence": evidence,
        "limitations": [],
        "open_questions": [],
    })
    return {
        "summary": answer[:6000],
        "research_question": str(result.get("research_question") or ""),
        "evidence_refs": evidence_refs,
        "evidence": evidence,
        "claims": [],
        "limitations": [],
        "open_questions": [],
        "metrics": {"run_latency_ms": float(result.get("run_latency_ms") or 0.0)},
    }


__all__ = ["execute_subagent_task_payload"]
