import datetime
import hashlib
import sqlite3
from typing import Any
from uuid import uuid4


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_memory_tables(db_name: str = "./database.sqlite") -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_events (
            event_uid TEXT PRIMARY KEY,
            uuid TEXT NOT NULL,
            project_uid TEXT NOT NULL,
            session_uid TEXT NOT NULL,
            prompt TEXT NOT NULL,
            answer TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_events_scope ON memory_events(uuid, project_uid, status, created_at)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_uid TEXT UNIQUE NOT NULL,
            uuid TEXT NOT NULL,
            project_uid TEXT NOT NULL,
            session_uid TEXT,
            memory_type TEXT NOT NULL,
            title TEXT DEFAULT '',
            content TEXT NOT NULL,
            source_prompt TEXT DEFAULT '',
            source_answer TEXT DEFAULT '',
            access_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_accessed_at TEXT,
            expires_at TEXT DEFAULT ''
        )
    """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_items_scope ON memory_items(uuid, project_uid, memory_type, updated_at DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_items_session ON memory_items(session_uid, updated_at DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_items_expire ON memory_items(expires_at)"
    )
    cursor.execute("PRAGMA table_info(memory_items)")
    memory_columns = {row[1] for row in cursor.fetchall()}
    if "expires_at" not in memory_columns:
        cursor.execute("ALTER TABLE memory_items ADD COLUMN expires_at TEXT DEFAULT ''")
    conn.commit()
    conn.close()


def upsert_project_memory_item(
    *,
    uuid: str,
    project_uid: str,
    session_uid: str | None,
    memory_type: str,
    content: str,
    title: str = "",
    source_prompt: str = "",
    source_answer: str = "",
    expires_at: str = "",
    db_name: str = "./database.sqlite",
) -> str:
    ensure_memory_tables(db_name)
    normalized_content = str(content or "").strip()
    if not normalized_content:
        return ""
    normalized_type = str(memory_type or "episodic").strip().lower() or "episodic"
    now = _now_str()
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT memory_uid
        FROM memory_items
        WHERE uuid = ? AND project_uid = ? AND memory_type = ? AND content = ?
        LIMIT 1
    """,
        (uuid, project_uid, normalized_type, normalized_content),
    )
    row = cursor.fetchone()
    if row:
        memory_uid = str(row[0] or "")
        cursor.execute(
            """
            UPDATE memory_items
            SET session_uid = ?, title = ?, source_prompt = ?, source_answer = ?, updated_at = ?, expires_at = ?
            WHERE memory_uid = ?
        """,
            (
                str(session_uid or ""),
                str(title or ""),
                str(source_prompt or ""),
                str(source_answer or ""),
                now,
                str(expires_at or ""),
                memory_uid,
            ),
        )
        conn.commit()
        conn.close()
        return memory_uid

    memory_uid = uuid4().hex
    cursor.execute(
        """
        INSERT INTO memory_items (
            memory_uid, uuid, project_uid, session_uid, memory_type, title, content,
            source_prompt, source_answer, access_count, created_at, updated_at, last_accessed_at, expires_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, '', ?)
    """,
        (
            memory_uid,
            uuid,
            project_uid,
            str(session_uid or ""),
            normalized_type,
            str(title or ""),
            normalized_content,
            str(source_prompt or ""),
            str(source_answer or ""),
            now,
            now,
            str(expires_at or ""),
        ),
    )
    conn.commit()
    conn.close()
    return memory_uid


def list_project_memory_items(
    *,
    uuid: str,
    project_uid: str,
    memory_type: str | None = None,
    limit: int = 100,
    include_expired: bool = False,
    db_name: str = "./database.sqlite",
) -> list[dict[str, Any]]:
    ensure_memory_tables(db_name)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    resolved_limit = max(1, int(limit))
    now = _now_str()
    expire_condition = ""
    params: list[Any] = [uuid, project_uid]
    if not include_expired:
        expire_condition = "AND (expires_at = '' OR expires_at > ?)"
        params.append(now)
    if isinstance(memory_type, str) and memory_type.strip():
        params.append(memory_type.strip().lower())
        params.append(resolved_limit)
        cursor.execute(
            """
            SELECT memory_uid, session_uid, memory_type, title, content, source_prompt,
                   source_answer, access_count, created_at, updated_at, last_accessed_at, expires_at
            FROM memory_items
            WHERE uuid = ? AND project_uid = ? AND memory_type = ?
            {expire_condition}
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
        """.format(expire_condition=expire_condition),
            tuple(params),
        )
    else:
        params.append(resolved_limit)
        cursor.execute(
            """
            SELECT memory_uid, session_uid, memory_type, title, content, source_prompt,
                   source_answer, access_count, created_at, updated_at, last_accessed_at, expires_at
            FROM memory_items
            WHERE uuid = ? AND project_uid = ?
            {expire_condition}
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
        """.format(expire_condition=expire_condition),
            tuple(params),
        )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "memory_uid": str(row[0] or ""),
            "session_uid": str(row[1] or ""),
            "memory_type": str(row[2] or ""),
            "title": str(row[3] or ""),
            "content": str(row[4] or ""),
            "source_prompt": str(row[5] or ""),
            "source_answer": str(row[6] or ""),
            "access_count": int(row[7] or 0),
            "created_at": str(row[8] or ""),
            "updated_at": str(row[9] or ""),
            "last_accessed_at": str(row[10] or ""),
            "expires_at": str(row[11] or ""),
        }
        for row in rows
    ]


def touch_memory_items(
    *,
    memory_uids: list[str],
    db_name: str = "./database.sqlite",
) -> None:
    if not memory_uids:
        return
    ensure_memory_tables(db_name)
    now = _now_str()
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    for memory_uid in memory_uids:
        normalized_uid = str(memory_uid or "").strip()
        if not normalized_uid:
            continue
        cursor.execute(
            """
            UPDATE memory_items
            SET access_count = access_count + 1, last_accessed_at = ?
            WHERE memory_uid = ?
        """,
            (now, normalized_uid),
        )
    conn.commit()
    conn.close()


def create_memory_event(
    *,
    uuid: str,
    project_uid: str,
    session_uid: str,
    prompt: str,
    answer: str,
    db_name: str = "./database.sqlite",
) -> str:
    prompt_text = str(prompt or "").strip()
    answer_text = str(answer or "").strip()
    if not prompt_text or not answer_text:
        return ""
    event_uid = hashlib.sha256(
        f"{uuid}\0{project_uid}\0{session_uid}\0{prompt_text}\0{answer_text}".encode("utf-8")
    ).hexdigest()
    ensure_memory_tables(db_name)
    now = _now_str()
    conn = sqlite3.connect(db_name, timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO memory_events (
            event_uid, uuid, project_uid, session_uid, prompt, answer,
            status, error_message, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', '', ?, ?)
        """,
        (event_uid, uuid, project_uid, session_uid, prompt_text, answer_text, now, now),
    )
    conn.commit()
    conn.close()
    return event_uid


def get_memory_event(
    *, event_uid: str, db_name: str = "./database.sqlite"
) -> dict[str, Any] | None:
    ensure_memory_tables(db_name)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT event_uid, uuid, project_uid, session_uid, prompt, answer,
               status, error_message, created_at, updated_at
        FROM memory_events WHERE event_uid = ? LIMIT 1
        """,
        (event_uid,),
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    keys = (
        "event_uid", "uuid", "project_uid", "session_uid", "prompt", "answer",
        "status", "error_message", "created_at", "updated_at",
    )
    return {key: str(value or "") for key, value in zip(keys, row, strict=True)}


def claim_memory_event(
    *, event_uid: str, db_name: str = "./database.sqlite"
) -> dict[str, Any] | None:
    """Atomically claim a pending or failed event for idempotent background processing."""
    ensure_memory_tables(db_name)
    conn = sqlite3.connect(db_name, timeout=10, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        stale_before = (
            datetime.datetime.now() - datetime.timedelta(minutes=15)
        ).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            UPDATE memory_events
            SET status = 'processing', error_message = '', updated_at = ?
            WHERE event_uid = ? AND (
                status IN ('pending', 'failed')
                OR (status = 'processing' AND updated_at < ?)
            )
            """,
            (_now_str(), event_uid, stale_before),
        )
        if cursor.rowcount != 1:
            conn.commit()
            return None
        cursor.execute(
            """
            SELECT event_uid, uuid, project_uid, session_uid, prompt, answer,
                   status, error_message, created_at, updated_at
            FROM memory_events WHERE event_uid = ? LIMIT 1
            """,
            (event_uid,),
        )
        row = cursor.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if row is None:
        return None
    keys = (
        "event_uid", "uuid", "project_uid", "session_uid", "prompt", "answer",
        "status", "error_message", "created_at", "updated_at",
    )
    return {key: str(value or "") for key, value in zip(keys, row, strict=True)}


def mark_memory_event(
    *,
    event_uid: str,
    status: str,
    error_message: str = "",
    clear_payload: bool = False,
    db_name: str = "./database.sqlite",
) -> None:
    ensure_memory_tables(db_name)
    conn = sqlite3.connect(db_name, timeout=10)
    cursor = conn.cursor()
    if clear_payload:
        cursor.execute(
            """
            UPDATE memory_events
            SET status = ?, error_message = ?, prompt = '', answer = '', updated_at = ?
            WHERE event_uid = ?
            """,
            (status, str(error_message or "")[:1000], _now_str(), event_uid),
        )
    else:
        cursor.execute(
            """
            UPDATE memory_events
            SET status = ?, error_message = ?, updated_at = ?
            WHERE event_uid = ?
            """,
            (status, str(error_message or "")[:1000], _now_str(), event_uid),
        )
    conn.commit()
    conn.close()


def apply_memory_consolidation(
    *,
    event: dict[str, Any],
    operations: list[dict[str, Any]],
    db_name: str = "./database.sqlite",
) -> None:
    """Apply model-proposed operations under deterministic scope and schema constraints."""
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        action = str(operation.get("action") or "")
        memory_uid = str(operation.get("memory_uid") or "").strip()
        if action == "delete" and memory_uid:
            _delete_scoped_memory(
                memory_uid=memory_uid,
                uuid=event["uuid"],
                project_uid=event["project_uid"],
                db_name=db_name,
            )
            continue
        content = str(operation.get("content") or "").strip()
        if action == "update" and memory_uid and content:
            if _update_scoped_memory(
                memory_uid=memory_uid,
                uuid=event["uuid"],
                project_uid=event["project_uid"],
                memory_type=str(operation.get("memory_type") or "semantic"),
                title=str(operation.get("title") or ""),
                content=content,
                source_prompt=f"memory_event:{event['event_uid']}",
                source_answer="",
                db_name=db_name,
            ):
                continue
        if action == "create" and content:
            upsert_project_memory_item(
                uuid=event["uuid"],
                project_uid=event["project_uid"],
                session_uid=event["session_uid"],
                memory_type=str(operation.get("memory_type") or "semantic"),
                title=str(operation.get("title") or ""),
                content=content,
                source_prompt=f"memory_event:{event['event_uid']}",
                source_answer="",
                db_name=db_name,
            )


def _delete_scoped_memory(
    *, memory_uid: str, uuid: str, project_uid: str, db_name: str
) -> None:
    conn = sqlite3.connect(db_name, timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM memory_items WHERE memory_uid = ? AND uuid = ? AND project_uid = ?",
        (memory_uid, uuid, project_uid),
    )
    conn.commit()
    conn.close()


def _update_scoped_memory(
    *,
    memory_uid: str,
    uuid: str,
    project_uid: str,
    memory_type: str,
    title: str,
    content: str,
    source_prompt: str,
    source_answer: str,
    db_name: str,
) -> bool:
    conn = sqlite3.connect(db_name, timeout=10)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE memory_items
        SET memory_type = ?, title = ?, content = ?, source_prompt = ?,
            source_answer = ?, updated_at = ?
        WHERE memory_uid = ? AND uuid = ? AND project_uid = ?
        """,
        (
            memory_type, title, content, source_prompt, source_answer, _now_str(),
            memory_uid, uuid, project_uid,
        ),
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated
