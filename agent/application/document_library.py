"""Document library use cases independent of the HTTP transport."""

import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..adapters.document_storage import store_document_bytes
from ..adapters.sqlite.document_repository import find_document_by_hash, insert_document
from ..adapters.sqlite.project_repository import add_file_to_project
from ..adapters.sqlite.rag_ingestion_repository import get_ingestion
from .rag_ingestion import enqueue_document_ingestion
from .workspace import require_project

ALLOWED_DOCUMENT_EXTENSIONS = {
    ".txt", ".doc", ".docx", ".pdf", ".ppt", ".pptx", ".xls", ".xlsx",
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
}


def upload_project_document(
    *,
    project_uid: str,
    user_uuid: str,
    file_name: str,
    content: bytes,
    enqueue_background_fn: Callable[..., dict[str, Any]],
    upload_dir: str = "./uploads",
    db_name: str = "./database.sqlite",
    store_document_bytes_fn: Callable[..., str] = store_document_bytes,
) -> dict[str, Any]:
    normalized_name = Path(file_name).name.strip()
    extension = Path(normalized_name).suffix.lower()
    if not normalized_name or extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValueError("Unsupported document type")
    max_bytes = max(1, int(os.getenv("DOCUMENT_UPLOAD_MAX_MB", "100"))) * 1024 * 1024
    if not content or len(content) > max_bytes:
        raise ValueError("Document is empty or exceeds the upload limit")
    require_project(project_uid=project_uid, user_uuid=user_uuid, db_name=db_name)

    content_hash = hashlib.md5(content).hexdigest()
    existing = find_document_by_hash(md5=content_hash, uuid=user_uuid, db_name=db_name)
    if existing is not None:
        document = existing
    else:
        doc_uid = str(uuid4())
        destination = store_document_bytes_fn(
            doc_uid=doc_uid,
            extension=extension,
            content=content,
            upload_dir=upload_dir,
        )
        document = insert_document(
            doc_uid=doc_uid,
            uuid=user_uuid,
            file_name=normalized_name,
            file_path=destination,
            md5=content_hash,
            db_name=db_name,
        )

    add_file_to_project(
        project_uid=project_uid,
        file_uid=str(document["uid"]),
        uuid=user_uuid,
        is_active=1,
        db_name=db_name,
    )
    queued = enqueue_document_ingestion(
        project_uid=project_uid,
        doc_uid=str(document["uid"]),
        user_uuid=user_uuid,
        doc_name=str(document["file_name"]),
        file_path=str(document["file_path"]),
        enqueue_background_fn=enqueue_background_fn,
        db_name=db_name,
    )
    ingestion = get_ingestion(project_uid=project_uid, doc_uid=str(document["uid"]), uuid=user_uuid, db_name=db_name)
    return {**document, "ingestion": ingestion or queued}


__all__ = ["ALLOWED_DOCUMENT_EXTENSIONS", "upload_project_document"]
