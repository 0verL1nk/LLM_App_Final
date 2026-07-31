"""SQLite persistence for the document library."""

import sqlite3
from datetime import datetime
from typing import Any


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_document_table(db_name: str = "./database.sqlite") -> None:
    with sqlite3.connect(db_name, timeout=10) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_filename TEXT NOT NULL,
                uid TEXT NOT NULL,
                md5 TEXT NOT NULL,
                file_path TEXT NOT NULL,
                uuid TEXT NOT NULL,
                created_at TEXT
            )
            """
        )
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(files)")}
        if "uuid" not in columns:
            conn.execute("ALTER TABLE files ADD COLUMN uuid TEXT DEFAULT 'local-user'")
        if "created_at" not in columns:
            conn.execute("ALTER TABLE files ADD COLUMN created_at TEXT DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_owner ON files(uuid, uid)")


def find_document_by_hash(
    *, md5: str, uuid: str, db_name: str = "./database.sqlite"
) -> dict[str, Any] | None:
    init_document_table(db_name)
    with sqlite3.connect(db_name) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT uid, original_filename AS file_name, file_path, created_at
            FROM files WHERE md5 = ? AND uuid = ? ORDER BY id DESC LIMIT 1
            """,
            (md5, uuid),
        ).fetchone()
    return dict(row) if row is not None else None


def insert_document(
    *,
    doc_uid: str,
    uuid: str,
    file_name: str,
    file_path: str,
    md5: str,
    db_name: str = "./database.sqlite",
) -> dict[str, Any]:
    init_document_table(db_name)
    created_at = _now()
    with sqlite3.connect(db_name, timeout=10) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            """
            INSERT INTO files (original_filename, uid, md5, file_path, uuid, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file_name, doc_uid, md5, file_path, uuid, created_at),
        )
    return {
        "uid": doc_uid,
        "file_name": file_name,
        "file_path": file_path,
        "created_at": created_at,
    }


__all__ = ["find_document_by_hash", "init_document_table", "insert_document"]
