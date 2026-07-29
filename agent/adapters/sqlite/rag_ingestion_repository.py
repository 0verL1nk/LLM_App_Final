"""SQLite persistence for asynchronous RAG document ingestion."""

import sqlite3
from datetime import datetime
from typing import Any


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_rag_ingestion_tables(db_name: str = "./database.sqlite") -> None:
    with sqlite3.connect(db_name, timeout=10) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_document_texts (
                doc_uid TEXT NOT NULL,
                uuid TEXT NOT NULL,
                file_path TEXT NOT NULL,
                text_content TEXT NOT NULL,
                text_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (doc_uid, uuid)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_ingestions (
                project_uid TEXT NOT NULL,
                doc_uid TEXT NOT NULL,
                uuid TEXT NOT NULL,
                doc_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                current_items INTEGER,
                total_items INTEGER,
                index_version TEXT,
                error_message TEXT,
                queue_job_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (project_uid, doc_uid, uuid)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rag_ingestions_project "
            "ON rag_ingestions(project_uid, uuid, status)"
        )


def queue_ingestion(
    *,
    project_uid: str,
    doc_uid: str,
    uuid: str,
    doc_name: str,
    file_path: str,
    db_name: str = "./database.sqlite",
) -> None:
    init_rag_ingestion_tables(db_name)
    now = _now()
    with sqlite3.connect(db_name, timeout=10) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            """
            INSERT INTO rag_ingestions (
                project_uid, doc_uid, uuid, doc_name, file_path,
                status, stage, current_items, total_items, index_version,
                error_message, queue_job_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'queued', 'queued', NULL, NULL, NULL, NULL, NULL, ?, ?)
            ON CONFLICT(project_uid, doc_uid, uuid) DO UPDATE SET
                doc_name = excluded.doc_name,
                file_path = excluded.file_path,
                status = 'queued',
                stage = 'queued',
                current_items = NULL,
                total_items = NULL,
                error_message = NULL,
                queue_job_id = NULL,
                updated_at = excluded.updated_at
            """,
            (project_uid, doc_uid, uuid, doc_name, file_path, now, now),
        )


def update_ingestion_progress(
    *,
    project_uid: str,
    doc_uid: str,
    uuid: str,
    status: str,
    stage: str,
    current_items: int | None = None,
    total_items: int | None = None,
    error_message: str | None = None,
    queue_job_id: str | None = None,
    index_version: str | None = None,
    db_name: str = "./database.sqlite",
) -> None:
    init_rag_ingestion_tables(db_name)
    with sqlite3.connect(db_name, timeout=10) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            """
            UPDATE rag_ingestions
            SET status = ?, stage = ?, current_items = ?, total_items = ?,
                error_message = ?, queue_job_id = COALESCE(?, queue_job_id),
                index_version = COALESCE(?, index_version), updated_at = ?
            WHERE project_uid = ? AND doc_uid = ? AND uuid = ?
            """,
            (
                status,
                stage,
                current_items,
                total_items,
                error_message,
                queue_job_id,
                index_version,
                _now(),
                project_uid,
                doc_uid,
                uuid,
            ),
        )


def set_ingestion_job_id(
    *,
    project_uid: str,
    doc_uid: str,
    uuid: str,
    queue_job_id: str,
    db_name: str = "./database.sqlite",
) -> None:
    init_rag_ingestion_tables(db_name)
    with sqlite3.connect(db_name, timeout=10) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            """
            UPDATE rag_ingestions
            SET queue_job_id = ?, updated_at = ?
            WHERE project_uid = ? AND doc_uid = ? AND uuid = ?
            """,
            (queue_job_id, _now(), project_uid, doc_uid, uuid),
        )


def save_document_text(
    *,
    doc_uid: str,
    uuid: str,
    file_path: str,
    text_content: str,
    text_hash: str,
    db_name: str = "./database.sqlite",
) -> None:
    init_rag_ingestion_tables(db_name)
    with sqlite3.connect(db_name, timeout=10) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            """
            INSERT INTO rag_document_texts (
                doc_uid, uuid, file_path, text_content, text_hash, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(doc_uid, uuid) DO UPDATE SET
                file_path = excluded.file_path,
                text_content = excluded.text_content,
                text_hash = excluded.text_hash,
                updated_at = excluded.updated_at
            """,
            (doc_uid, uuid, file_path, text_content, text_hash, _now()),
        )


def get_document_text(
    *,
    doc_uid: str,
    uuid: str,
    db_name: str = "./database.sqlite",
) -> dict[str, Any] | None:
    init_rag_ingestion_tables(db_name)
    with sqlite3.connect(db_name) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT doc_uid, uuid, file_path, text_content, text_hash, updated_at
            FROM rag_document_texts
            WHERE doc_uid = ? AND uuid = ?
            """,
            (doc_uid, uuid),
        ).fetchone()
    return dict(row) if row is not None else None


def get_ingestion(
    *,
    project_uid: str,
    doc_uid: str,
    uuid: str,
    db_name: str = "./database.sqlite",
) -> dict[str, Any] | None:
    init_rag_ingestion_tables(db_name)
    with sqlite3.connect(db_name) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT * FROM rag_ingestions
            WHERE project_uid = ? AND doc_uid = ? AND uuid = ?
            """,
            (project_uid, doc_uid, uuid),
        ).fetchone()
    return dict(row) if row is not None else None


def list_project_ingestions(
    *,
    project_uid: str,
    uuid: str,
    db_name: str = "./database.sqlite",
) -> list[dict[str, Any]]:
    init_rag_ingestion_tables(db_name)
    with sqlite3.connect(db_name) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT ri.*
            FROM rag_ingestions ri
            JOIN project_files pf
              ON pf.project_uid = ri.project_uid
             AND pf.file_uid = ri.doc_uid
             AND pf.uuid = ri.uuid
            WHERE ri.project_uid = ? AND ri.uuid = ? AND pf.is_active = 1
            ORDER BY ri.created_at, ri.doc_uid
            """,
            (project_uid, uuid),
        ).fetchall()
    return [dict(row) for row in rows]


def list_ready_project_documents(
    *,
    project_uid: str,
    uuid: str,
    doc_uids: list[str] | None = None,
    db_name: str = "./database.sqlite",
) -> list[dict[str, Any]]:
    init_rag_ingestion_tables(db_name)
    params: list[Any] = [project_uid, uuid]
    scope_clause = ""
    if doc_uids is not None:
        normalized = sorted({str(item).strip() for item in doc_uids if str(item).strip()})
        if not normalized:
            return []
        placeholders = ",".join("?" for _ in normalized)
        scope_clause = f" AND ri.doc_uid IN ({placeholders})"
        params.extend(normalized)
    with sqlite3.connect(db_name) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"""
            SELECT ri.doc_uid, ri.doc_name, ri.file_path, ri.index_version,
                   dt.text_content AS text
            FROM rag_ingestions ri
            JOIN rag_document_texts dt
              ON dt.doc_uid = ri.doc_uid AND dt.uuid = ri.uuid
            JOIN project_files pf
              ON pf.project_uid = ri.project_uid
             AND pf.file_uid = ri.doc_uid
             AND pf.uuid = ri.uuid
            WHERE ri.project_uid = ? AND ri.uuid = ?
              AND ri.status = 'ready' AND pf.is_active = 1
              {scope_clause}
            ORDER BY ri.doc_uid
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "get_document_text",
    "get_ingestion",
    "init_rag_ingestion_tables",
    "list_project_ingestions",
    "list_ready_project_documents",
    "queue_ingestion",
    "save_document_text",
    "set_ingestion_job_id",
    "update_ingestion_progress",
]
