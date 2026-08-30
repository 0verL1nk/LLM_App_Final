"""Reusable live-model harness for task-completion evals.

Shared by the CLI smoke runner (tests/evals) and the in-app eval service so
both drive the exact same canonical turn path.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.adapters.llm import create_chat_model
from agent.adapters.rag import create_project_evidence_retriever
from agent.application.turn_engine import execute_turn_core
from agent.profiles import paper_leader_profile
from agent.prompts.paper_domain import build_external_research_prompt
from agent.session_factory import AgentDependencies, AgentRuntimeOptions, create_agent_session

from .contracts import AgentEvalCase

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "papers" / "rag_agentic_reasoning"

DEFAULT_MAX_CHARS_PER_DOC = 30000


def _paper_uid_from_fixture_name(name: str) -> str:
    stem = Path(name).stem
    paper_id = stem.split("-", 1)[0].strip() if "-" in stem else stem.strip()
    return f"arxiv:{paper_id}"


def _paper_title_from_fixture_name(name: str) -> str:
    stem = Path(name).stem
    if "-" not in stem:
        return stem
    return stem.split("-", 1)[1].replace("-", " ").strip()


def load_project_documents(max_chars_per_doc: int = DEFAULT_MAX_CHARS_PER_DOC) -> list[dict[str, str]]:
    cache_dir = FIXTURE_DIR / "_extracted"
    docs: list[dict[str, str]] = []
    for text_path in sorted(cache_dir.glob("*.txt")):
        extracted = text_path.read_text(encoding="utf-8", errors="replace").strip()
        if not extracted:
            continue
        paper_id = _paper_uid_from_fixture_name(text_path.name)
        title = _paper_title_from_fixture_name(text_path.name)
        docs.append(
            {
                "doc_uid": paper_id,
                "doc_name": title,
                "text": (
                    f"[paper_id] {paper_id}\n"
                    f"[title] {title}\n"
                    f"[source_file] {text_path.name}\n\n"
                    f"{extracted[:max_chars_per_doc]}"
                ),
            }
        )
    if not docs:
        raise ValueError("No local paper fixture texts found for live eval run.")
    return docs


def _normalized_document_access(case: AgentEvalCase) -> str:
    raw_access = case.metadata.get("document_access", "scoped")
    normalized = str(raw_access or "scoped").strip().lower()
    return "none" if normalized == "none" else "scoped"


def _normalized_document_scope(case: AgentEvalCase) -> list[str]:
    raw_scope = case.metadata.get("document_scope")
    if not isinstance(raw_scope, list):
        return []
    scope: list[str] = []
    for item in raw_scope:
        value = str(item or "").strip()
        if value:
            scope.append(value)
    return scope


def build_case_document_context(
    case: AgentEvalCase,
    documents: list[dict[str, str]],
) -> dict[str, Any]:
    access_mode = _normalized_document_access(case)
    if access_mode == "none":
        return {
            "document_access": "none",
            "documents": [],
            "document_name": None,
            "scope_summary": "当前会话不提供项目文档，仅允许外部检索。",
            "search_document_fn": None,
            "search_document_evidence_fn": None,
            "list_documents_fn": None,
        }

    requested_scope = _normalized_document_scope(case)
    documents_by_uid = {
        str(item.get("doc_uid") or "").strip(): item
        for item in documents
        if isinstance(item, dict) and str(item.get("doc_uid") or "").strip()
    }
    if requested_scope:
        missing = [doc_uid for doc_uid in requested_scope if doc_uid not in documents_by_uid]
        if missing:
            raise ValueError(
                f"Eval case '{case.case_id}' requested unknown document_scope entries: {missing}"
            )
        scoped_documents = [documents_by_uid[doc_uid] for doc_uid in requested_scope]
    else:
        scoped_documents = list(documents)

    retriever = create_project_evidence_retriever(
        documents=scoped_documents,
        project_uid=f"task-completion-live-smoke:{case.case_id}",
    )

    def _search_document(query: str) -> str:
        payload = retriever(query)
        evidences = payload.get("evidences") if isinstance(payload, dict) else []
        if not isinstance(evidences, list):
            return ""
        return "\n".join(
            str(item.get("text") or "")
            for item in evidences
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        )

    doc_names = [str(item.get("doc_name") or item.get("doc_uid") or "").strip() for item in scoped_documents]
    preview_names = [item for item in doc_names if item][:3]
    preview = ", ".join(preview_names)
    if len(doc_names) > 3:
        preview = f"{preview} 等 {len(doc_names)} 篇文档"
    scope_summary = preview or f"仅限项目内 {len(scoped_documents)} 篇文档"
    document_name = scoped_documents[0]["doc_name"] if len(scoped_documents) == 1 else None

    def _list_documents() -> list[dict[str, str]]:
        return [
            {
                "doc_uid": str(item.get("doc_uid") or ""),
                "doc_name": str(item.get("doc_name") or ""),
            }
            for item in scoped_documents
        ]

    return {
        "document_access": "scoped",
        "documents": scoped_documents,
        "document_name": document_name,
        "scope_summary": scope_summary,
        "search_document_fn": _search_document,
        "search_document_evidence_fn": retriever,
        "list_documents_fn": _list_documents,
    }


def build_live_llm_from_env() -> Any:
    api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    model_name = str(os.getenv("OPENAI_MODEL_NAME") or "").strip()
    base_url = str(os.getenv("OPENAI_BASE_URL") or "").strip()
    missing = [
        key
        for key, value in {
            "OPENAI_API_KEY": api_key,
            "OPENAI_MODEL_NAME": model_name,
            "OPENAI_BASE_URL": base_url,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing live eval config: {', '.join(missing)}")
    return create_chat_model(
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
        temperature=0.0,
    )


@dataclass(frozen=True)
class LivePaperSageEvalRunner:
    llm: Any
    documents: list[dict[str, str]]
    project_name: str
    on_activity: Callable[[str, dict[str, Any]], None] | None = None
    """Optional (case_id, event) sink receiving turn events for live progress."""

    def __call__(self, case: AgentEvalCase) -> dict[str, Any]:
        context = build_case_document_context(case, self.documents)
        document_access = str(context["document_access"])
        system_prompt = None
        if document_access == "none":
            system_prompt = build_external_research_prompt(
                project_name=self.project_name,
                scope_summary=str(context["scope_summary"]),
            )
        session = create_agent_session(
            profile=paper_leader_profile,
            deps=AgentDependencies(
                search_document_fn=context["search_document_fn"],
                search_document_evidence_fn=context["search_document_evidence_fn"],
                list_documents_fn=context["list_documents_fn"],
                document_access=document_access,
            ),
            options=AgentRuntimeOptions(
                llm=self.llm,
                project_name=self.project_name,
                scope_summary=str(context["scope_summary"]),
                document_name=context["document_name"],
                system_prompt=system_prompt,
            ),
        )
        runtime_config = dict(session.runtime_config)
        if self.on_activity is not None:
            configurable = dict(runtime_config.get("configurable") or {})
            configurable["on_event"] = lambda event: self.on_activity(case.case_id, event)
            runtime_config["configurable"] = configurable
        return execute_turn_core(
            prompt=case.prompt,
            leader_agent=session.agent,
            leader_runtime_config=runtime_config,
            search_document_evidence_fn=context["search_document_evidence_fn"],
            leader_tool_specs=session.tool_specs,
        )
