import json
import threading
from collections.abc import Callable
from typing import Any

from ..embedding_provider import get_embedding_model
from ..rag.hybrid import (
    build_local_evidence_retriever_with_settings,
    build_project_evidence_retriever_with_settings,
)
from ..settings import load_agent_settings
from .lancedb.rag_index import search_published_chunks
from .sqlite.rag_ingestion_repository import list_ready_project_documents

EvidenceRetriever = Callable[[str], dict[str, Any]]
_PROJECT_RETRIEVER_LOCKS: dict[str, threading.Lock] = {}
_PROJECT_RETRIEVER_LOCK_GUARD = threading.Lock()


def _project_lock(project_uid: str) -> threading.Lock:
    normalized = str(project_uid or "").strip() or "__default__"
    with _PROJECT_RETRIEVER_LOCK_GUARD:
        lock = _PROJECT_RETRIEVER_LOCKS.get(normalized)
        if lock is None:
            lock = threading.Lock()
            _PROJECT_RETRIEVER_LOCKS[normalized] = lock
        return lock


def create_project_evidence_retriever(
    *,
    documents: list[dict[str, str]],
    project_uid: str,
) -> EvidenceRetriever:
    with _project_lock(project_uid):
        if len(documents) == 1:
            only = documents[0]
            return build_local_evidence_retriever_with_settings(
                document_text=only["text"],
                doc_uid=only["doc_uid"],
                doc_name=only["doc_name"],
                project_uid=project_uid,
            )
        return build_project_evidence_retriever_with_settings(
            documents=documents,
            project_uid=project_uid,
        )


class DynamicProjectEvidenceService:
    """Search the latest ready project manifest through LanceDB hybrid retrieval."""

    def __init__(
        self,
        *,
        project_uid: str,
        user_uuid: str,
        doc_uids: list[str] | None = None,
        db_name: str = "./database.sqlite",
        list_ready_documents_fn: Callable[..., list[dict[str, Any]]] = list_ready_project_documents,
        search_chunks_fn: Callable[..., list[dict[str, Any]]] = search_published_chunks,
        embed_query_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self.project_uid = project_uid
        self.user_uuid = user_uuid
        self.db_name = db_name
        self._doc_uids = tuple(sorted(set(doc_uids or [])))
        self._list_ready_documents_fn = list_ready_documents_fn
        self._search_chunks_fn = search_chunks_fn
        self._embed_query_fn = embed_query_fn
        self._manifest: tuple[tuple[str, str], ...] = ()
        self._lock = threading.RLock()

    def update_scope(self, doc_uids: list[str]) -> None:
        normalized = tuple(sorted({str(item).strip() for item in doc_uids if str(item).strip()}))
        with self._lock:
            if normalized != self._doc_uids:
                self._doc_uids = normalized
                self._manifest = ()

    def _ready_documents(self) -> list[dict[str, Any]]:
        with self._lock:
            scope = list(self._doc_uids)
        return self._list_ready_documents_fn(
            project_uid=self.project_uid,
            uuid=self.user_uuid,
            doc_uids=scope,
            db_name=self.db_name,
        )

    @staticmethod
    def _manifest_for(documents: list[dict[str, Any]]) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted(
                (
                    str(item.get("doc_uid") or ""),
                    str(item.get("index_version") or ""),
                )
                for item in documents
                if item.get("doc_uid") and item.get("index_version")
            )
        )

    def search(self, query: str) -> dict[str, Any]:
        documents = self._ready_documents()
        manifest = self._manifest_for(documents)
        if not manifest:
            return {
                "evidences": [],
                "trace": {
                    "mode": "dynamic_project",
                    "project_uid": self.project_uid,
                    "ready_doc_count": 0,
                    "reason": "no_ready_documents",
                },
            }
        embed_query = self._embed_query_fn
        query_vector = (
            embed_query(query)
            if callable(embed_query)
            else get_embedding_model().embed_query(query)
        )
        settings = load_agent_settings()
        candidate_limit = max(
            int(settings.rag_dense_candidate_k),
            int(settings.rag_sparse_candidate_k),
            int(settings.rag_top_k),
        )
        rows = self._search_chunks_fn(
            project_uid=self.project_uid,
            ready_versions=list(manifest),
            query=query,
            query_vector=[float(value) for value in query_vector],
            limit=candidate_limit,
        )
        with self._lock:
            self._manifest = manifest
        evidences: list[dict[str, Any]] = []
        for rank, row in enumerate(rows[: max(1, int(settings.rag_top_k))]):
            start_index = row.get("start_index")
            text = str(row.get("text") or "")
            chunk_id = str(row.get("chunk_id") or f"chunk_{rank}")
            offset_start = start_index if isinstance(start_index, int) else None
            offset_end = (
                start_index + len(text) if isinstance(start_index, int) else None
            )
            page_no = row.get("page_no") if isinstance(row.get("page_no"), int) else None
            locations: list[dict[str, Any]] = []
            raw_locations = row.get("ocr_locations_json")
            if isinstance(raw_locations, str):
                try:
                    decoded = json.loads(raw_locations)
                except json.JSONDecodeError:
                    decoded = []
                if isinstance(decoded, list):
                    locations = [item for item in decoded if isinstance(item, dict)]
            evidences.append(
                {
                    "project_uid": self.project_uid,
                    "doc_uid": str(row.get("doc_uid") or ""),
                    "doc_name": str(row.get("doc_name") or ""),
                    "chunk_id": chunk_id,
                    "text": text,
                    "score": float(row.get("_relevance_score", 0.0) or 0.0),
                    "rank": rank + 1,
                    "page_no": page_no,
                    "ocr_locations": locations,
                    "offset_start": offset_start,
                    "offset_end": offset_end,
                    "citation": (
                        f"{chunk_id}|p{page_no}|o{offset_start}-{offset_end}"
                        if offset_start is not None and offset_end is not None
                        else f"{chunk_id}|p{page_no}|onull-null"
                    ),
                }
            )
        return {
            "evidences": evidences,
            "trace": {
                "mode": "lancedb_hybrid",
                "project_uid": self.project_uid,
                "ready_doc_count": len(documents),
                "candidate_count": len(rows),
                "top_k": settings.rag_top_k,
                "dynamic_manifest": [list(item) for item in manifest],
                "reason": "no_candidates" if not rows else None,
            },
        }

    def search_text(self, query: str) -> str:
        payload = self.search(query)
        evidences = payload.get("evidences") if isinstance(payload, dict) else []
        if not isinstance(evidences, list):
            return ""
        return "\n".join(
            str(item.get("text") or "")
            for item in evidences
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        )

    def list_documents(self) -> list[dict[str, Any]]:
        return [
            {
                "doc_uid": str(item.get("doc_uid") or ""),
                "doc_name": str(item.get("doc_name") or ""),
                "char_length": len(str(item.get("text") or "")),
                "index_version": str(item.get("index_version") or ""),
            }
            for item in self._ready_documents()
        ]

    def read_document(self, doc_id: str, offset: int, limit: int) -> tuple[str, int]:
        documents = self._ready_documents()
        if not documents:
            return "", 0
        normalized_id = str(doc_id or "").strip()
        if not normalized_id and len(documents) == 1:
            normalized_id = str(documents[0].get("doc_uid") or "")
        selected = next(
            (item for item in documents if str(item.get("doc_uid") or "") == normalized_id),
            None,
        )
        if selected is None:
            return "", 0
        text = str(selected.get("text") or "")
        safe_offset = max(0, int(offset))
        safe_limit = max(1, int(limit))
        return text[safe_offset : safe_offset + safe_limit], len(text)


def create_dynamic_project_evidence_service(
    *,
    project_uid: str,
    user_uuid: str,
    doc_uids: list[str],
) -> DynamicProjectEvidenceService:
    return DynamicProjectEvidenceService(
        project_uid=project_uid,
        user_uuid=user_uuid,
        doc_uids=doc_uids,
    )


__all__ = [
    "DynamicProjectEvidenceService",
    "EvidenceRetriever",
    "create_dynamic_project_evidence_service",
    "create_project_evidence_retriever",
]
