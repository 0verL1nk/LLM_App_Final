"""Asynchronous document ingestion use cases for project RAG."""

import hashlib
import logging
from collections.abc import Callable
from typing import Any

from ..adapters.document import extract_document_payload
from ..adapters.lancedb.rag_index import (
    document_index_exists,
    publish_document_index,
)
from ..adapters.sqlite.rag_ingestion_repository import (
    get_document_text,
    get_ingestion,
    queue_ingestion,
    save_document_text,
    set_ingestion_job_id,
    update_ingestion_progress,
)
from ..rag.hybrid import build_project_document_index_with_settings

logger = logging.getLogger(__name__)


def should_requeue_ingestion(
    ingestion: dict[str, Any],
    *,
    get_job_status_fn: Callable[[str], str | None],
    document_index_exists_fn: Callable[..., bool] = document_index_exists,
) -> bool:
    """Recover legacy empty-text failures and local jobs lost on process restart."""
    status = str(ingestion.get("status") or "")
    error_message = str(ingestion.get("error_message") or "")
    if status == "failed" and error_message == "Document extraction returned empty text":
        return True
    if status == "ready":
        index_version = str(ingestion.get("index_version") or "")
        return bool(index_version) and not document_index_exists_fn(
            project_uid=str(ingestion.get("project_uid") or ""),
            doc_uid=str(ingestion.get("doc_uid") or ""),
            index_version=index_version,
        )
    job_id = str(ingestion.get("queue_job_id") or "")
    return (
        status in {"queued", "running"}
        and job_id.startswith("local-")
        and get_job_status_fn(job_id) is None
    )


def process_document_ingestion(
    project_uid: str,
    doc_uid: str,
    user_uuid: str,
    doc_name: str,
    file_path: str,
    db_name: str = "./database.sqlite",
) -> dict[str, Any]:
    """Extract, embed, and atomically publish one project document."""
    try:
        update_ingestion_progress(
            project_uid=project_uid,
            doc_uid=doc_uid,
            uuid=user_uuid,
            status="running",
            stage="extracting",
            db_name=db_name,
        )

        def _report(stage: str, current: int | None, total: int | None) -> None:
            update_ingestion_progress(
                project_uid=project_uid,
                doc_uid=doc_uid,
                uuid=user_uuid,
                status="running",
                stage=stage,
                current_items=current,
                total_items=total,
                db_name=db_name,
            )

        stored_text = get_document_text(doc_uid=doc_uid, uuid=user_uuid, db_name=db_name)
        if stored_text and str(stored_text.get("file_path") or "") == file_path:
            normalized_text = str(stored_text.get("text_content") or "").strip()
            extraction: dict[str, Any] = {"parser": "stored_text"}
        else:
            extraction = extract_document_payload(
                file_path,
                user_uuid=user_uuid,
                progress_callback=_report,
            )
            text = extraction.get("text")
            if not isinstance(text, str):
                raise TypeError("Document adapter returned a non-text payload")
            normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Document extraction returned empty text")
        text_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
        if not stored_text or str(stored_text.get("text_hash") or "") != text_hash:
            save_document_text(
                doc_uid=doc_uid,
                uuid=user_uuid,
                file_path=file_path,
                text_content=normalized_text,
                text_hash=text_hash,
                db_name=db_name,
            )

        index_payload = build_project_document_index_with_settings(
            project_uid=project_uid,
            doc_uid=doc_uid,
            doc_name=doc_name,
            document_text=normalized_text,
            progress_callback=_report,
        )
        chunk_count = int(index_payload.get("chunk_count", 0) or 0)
        _report("publishing", chunk_count, chunk_count)
        publish_document_index(
            project_uid=project_uid,
            doc_uid=doc_uid,
            doc_name=doc_name,
            index_version=str(index_payload.get("index_version") or ""),
            chunks=list(index_payload.get("chunks") or []),
            metadatas=list(index_payload.get("metadatas") or []),
            embeddings=list(index_payload.get("embeddings") or []),
        )
        result = {
            key: value
            for key, value in index_payload.items()
            if key not in {"chunks", "metadatas", "embeddings"}
        }
        update_ingestion_progress(
            project_uid=project_uid,
            doc_uid=doc_uid,
            uuid=user_uuid,
            status="ready",
            stage="ready",
            current_items=chunk_count,
            total_items=chunk_count,
            index_version=str(result.get("index_version") or ""),
            db_name=db_name,
        )
        logger.info(
            "RAG ingestion ready: project=%s doc=%s parser=%s chunks=%s "
            "indexed_chars=%s source_chars=%s reused=%s",
            project_uid,
            doc_uid,
            extraction.get("parser"),
            chunk_count,
            result.get("indexed_char_count"),
            result.get("source_char_count"),
            bool(result.get("reused")),
        )
        return result
    except Exception as exc:
        update_ingestion_progress(
            project_uid=project_uid,
            doc_uid=doc_uid,
            uuid=user_uuid,
            status="failed",
            stage="failed",
            error_message=str(exc),
            db_name=db_name,
        )
        logger.exception("RAG ingestion failed: project=%s doc=%s", project_uid, doc_uid)
        raise


def enqueue_document_ingestion(
    *,
    project_uid: str,
    doc_uid: str,
    user_uuid: str,
    doc_name: str,
    file_path: str,
    enqueue_background_fn: Callable[..., dict[str, Any]],
    db_name: str = "./database.sqlite",
    force: bool = False,
) -> dict[str, Any]:
    """Persist the job before dispatch so UI polling never loses its state."""
    current = get_ingestion(
        project_uid=project_uid,
        doc_uid=doc_uid,
        uuid=user_uuid,
        db_name=db_name,
    )
    if not force and current and current.get("status") in {"queued", "running", "ready"}:
        return {
            "mode": "existing",
            "job_id": current.get("queue_job_id"),
            "status": current.get("status"),
        }

    queue_ingestion(
        project_uid=project_uid,
        doc_uid=doc_uid,
        uuid=user_uuid,
        doc_name=doc_name,
        file_path=file_path,
        db_name=db_name,
    )
    try:
        queued = enqueue_background_fn(
            process_document_ingestion,
            project_uid,
            doc_uid,
            user_uuid,
            doc_name,
            file_path,
            db_name,
        )
    except Exception as exc:
        update_ingestion_progress(
            project_uid=project_uid,
            doc_uid=doc_uid,
            uuid=user_uuid,
            status="failed",
            stage="failed",
            error_message=f"Failed to enqueue ingestion: {exc}",
            db_name=db_name,
        )
        raise
    job_id = queued.get("job_id") if isinstance(queued, dict) else None
    if job_id:
        set_ingestion_job_id(
            project_uid=project_uid,
            doc_uid=doc_uid,
            uuid=user_uuid,
            queue_job_id=str(job_id),
            db_name=db_name,
        )
    return dict(queued) if isinstance(queued, dict) else {"mode": "queued"}


def reconcile_project_ingestions(
    *,
    project_uid: str,
    user_uuid: str,
    documents: list[dict[str, Any]],
    ingestions: list[dict[str, Any]],
    get_job_status_fn: Callable[[str], str | None],
    enqueue_background_fn: Callable[..., dict[str, Any]],
    db_name: str = "./database.sqlite",
) -> int:
    """Idempotently recover missing or interrupted project ingestion jobs."""
    by_doc = {str(item.get("doc_uid") or ""): item for item in ingestions}
    recovered = 0
    for document in documents:
        doc_uid = str(document.get("uid") or "")
        current = by_doc.get(doc_uid)
        if current is not None and not should_requeue_ingestion(
            current,
            get_job_status_fn=get_job_status_fn,
        ):
            continue
        enqueue_document_ingestion(
            project_uid=project_uid,
            doc_uid=doc_uid,
            user_uuid=user_uuid,
            doc_name=str(document.get("file_name") or doc_uid),
            file_path=str(document.get("file_path") or ""),
            enqueue_background_fn=enqueue_background_fn,
            db_name=db_name,
            force=current is not None,
        )
        recovered += 1
    return recovered


__all__ = [
    "enqueue_document_ingestion",
    "process_document_ingestion",
    "reconcile_project_ingestions",
    "should_requeue_ingestion",
]
