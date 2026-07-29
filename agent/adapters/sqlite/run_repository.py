"""Durable Agent run and canonical event log repository."""

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _connect(db_name: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_name, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def ensure_run_tables(db_name: str = "./database.sqlite") -> None:
    with _connect(db_name) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                run_uid TEXT PRIMARY KEY,
                project_uid TEXT NOT NULL,
                session_uid TEXT NOT NULL,
                uuid TEXT NOT NULL,
                client_request_id TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(uuid, client_request_id)
            );
            CREATE INDEX IF NOT EXISTS idx_agent_runs_session
                ON agent_runs(uuid, project_uid, session_uid, created_at DESC);
            CREATE TABLE IF NOT EXISTS agent_run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_uid TEXT NOT NULL UNIQUE,
                run_uid TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                UNIQUE(run_uid, sequence),
                FOREIGN KEY(run_uid) REFERENCES agent_runs(run_uid) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_agent_run_events_sequence
                ON agent_run_events(run_uid, sequence ASC);
            """
        )


def _run_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def create_run(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    client_request_id: str,
    prompt: str,
    db_name: str = "./database.sqlite",
) -> tuple[dict[str, Any], bool]:
    ensure_run_tables(db_name)
    now = _now()
    run_uid = f"run_{uuid.uuid4().hex}"
    with _connect(db_name) as connection:
        existing = connection.execute(
            "SELECT * FROM agent_runs WHERE uuid = ? AND client_request_id = ?",
            (user_uuid, client_request_id),
        ).fetchone()
        if existing is not None:
            return _run_from_row(existing), False
        inserted = connection.execute(
            """
            INSERT OR IGNORE INTO agent_runs (
                run_uid, project_uid, session_uid, uuid, client_request_id,
                prompt, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?)
            """,
            (run_uid, project_uid, session_uid, user_uuid, client_request_id, prompt, now, now),
        )
        if inserted.rowcount == 0:
            existing = connection.execute(
                "SELECT * FROM agent_runs WHERE uuid = ? AND client_request_id = ?",
                (user_uuid, client_request_id),
            ).fetchone()
            if existing is None:
                raise RuntimeError("Run idempotency check failed")
            return _run_from_row(existing), False
    run = get_run(run_uid=run_uid, user_uuid=user_uuid, db_name=db_name)
    if run is None:
        raise RuntimeError("Run creation failed")
    append_run_event(run_uid=run_uid, event_type="run.created", payload={"status": "queued"}, db_name=db_name)
    return run, True


def get_run(
    *, run_uid: str, user_uuid: str, db_name: str = "./database.sqlite"
) -> dict[str, Any] | None:
    ensure_run_tables(db_name)
    with _connect(db_name) as connection:
        row = connection.execute(
            "SELECT * FROM agent_runs WHERE run_uid = ? AND uuid = ?",
            (run_uid, user_uuid),
        ).fetchone()
    return _run_from_row(row) if row is not None else None


def list_session_runs(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    statuses: tuple[str, ...] = ("queued", "running"),
    db_name: str = "./database.sqlite",
) -> list[dict[str, Any]]:
    """List only runs that the current user may resume in this session."""
    ensure_run_tables(db_name)
    if not statuses:
        return []
    placeholders = ", ".join("?" for _ in statuses)
    with _connect(db_name) as connection:
        rows = connection.execute(
            f"""
            SELECT * FROM agent_runs
            WHERE uuid = ? AND project_uid = ? AND session_uid = ?
              AND status IN ({placeholders})
            ORDER BY created_at ASC
            """,
            (user_uuid, project_uid, session_uid, *statuses),
        ).fetchall()
    return [_run_from_row(row) for row in rows]


def append_run_event(
    *,
    run_uid: str,
    event_type: str,
    payload: dict[str, Any],
    db_name: str = "./database.sqlite",
) -> dict[str, Any]:
    ensure_run_tables(db_name)
    event_uid = f"evt_{uuid.uuid4().hex}"
    timestamp = _now()
    with _connect(db_name) as connection:
        connection.execute("BEGIN IMMEDIATE")
        run = connection.execute(
            "SELECT session_uid FROM agent_runs WHERE run_uid = ?",
            (run_uid,),
        ).fetchone()
        if run is None:
            raise LookupError("Run not found")
        sequence = int(
            connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM agent_run_events WHERE run_uid = ?",
                (run_uid,),
            ).fetchone()[0]
        )
        connection.execute(
            """
            INSERT INTO agent_run_events (
                event_uid, run_uid, sequence, event_type, timestamp, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_uid, run_uid, sequence, event_type, timestamp, json.dumps(payload, ensure_ascii=False, default=str)),
        )
        connection.execute("UPDATE agent_runs SET updated_at = ? WHERE run_uid = ?", (timestamp, run_uid))
    return {
        "version": 1,
        "eventId": event_uid,
        "eventType": event_type,
        "sequence": sequence,
        "timestamp": timestamp,
        "threadId": str(run["session_uid"]),
        "runId": run_uid,
        "traceId": f"trace_{run_uid.removeprefix('run_')}",
        "payload": payload,
    }


def list_run_events(
    *, run_uid: str, after_sequence: int = 0, db_name: str = "./database.sqlite"
) -> list[dict[str, Any]]:
    ensure_run_tables(db_name)
    with _connect(db_name) as connection:
        rows = connection.execute(
            """
            SELECT e.event_uid, e.sequence, e.event_type, e.timestamp, e.payload_json,
                   r.session_uid
            FROM agent_run_events e
            JOIN agent_runs r ON r.run_uid = e.run_uid
            WHERE e.run_uid = ? AND e.sequence > ?
            ORDER BY e.sequence ASC
            """,
            (run_uid, after_sequence),
        ).fetchall()
    return [
        {
            "version": 1,
            "eventId": row["event_uid"],
            "eventType": row["event_type"],
            "sequence": row["sequence"],
            "timestamp": row["timestamp"],
            "threadId": row["session_uid"],
            "runId": run_uid,
            "traceId": f"trace_{run_uid.removeprefix('run_')}",
            "payload": json.loads(row["payload_json"]),
        }
        for row in rows
    ]


def update_run_status(
    *,
    run_uid: str,
    status: str,
    error_message: str = "",
    db_name: str = "./database.sqlite",
) -> bool:
    ensure_run_tables(db_name)
    with _connect(db_name) as connection:
        updated = connection.execute(
            """
            UPDATE agent_runs SET status = ?, error_message = ?, updated_at = ?
            WHERE run_uid = ? AND status IN ('queued', 'running')
            """,
            (status, error_message[:1000], _now(), run_uid),
        )
    return updated.rowcount > 0


def expire_stalled_runs(
    *, project_uid: str, session_uid: str, user_uuid: str, max_idle_seconds: float, db_name: str = "./database.sqlite"
) -> list[str]:
    """Fail abandoned active runs so a disconnected worker cannot leave the UI loading forever."""
    ensure_run_tables(db_name)
    cutoff = datetime.now(UTC).timestamp() - max(1.0, max_idle_seconds)
    with _connect(db_name) as connection:
        rows = connection.execute(
            "SELECT run_uid, updated_at FROM agent_runs WHERE project_uid = ? AND session_uid = ? AND uuid = ? AND status IN ('queued', 'running')",
            (project_uid, session_uid, user_uuid),
        ).fetchall()
    expired: list[str] = []
    for row in rows:
        try:
            updated_at = datetime.fromisoformat(str(row["updated_at"]).replace("Z", "+00:00")).timestamp()
        except ValueError:
            updated_at = 0.0
        if updated_at >= cutoff:
            continue
        run_uid = str(row["run_uid"])
        if update_run_status(run_uid=run_uid, status="failed", error_message="Run stalled", db_name=db_name):
            append_run_event(run_uid=run_uid, event_type="run.failed", payload={"message": "研究运行超时，未收到新的进展。请重试。"}, db_name=db_name)
            expired.append(run_uid)
    return expired


__all__ = [
    "append_run_event",
    "create_run",
    "ensure_run_tables",
    "expire_stalled_runs",
    "get_run",
    "list_session_runs",
    "list_run_events",
    "update_run_status",
]
