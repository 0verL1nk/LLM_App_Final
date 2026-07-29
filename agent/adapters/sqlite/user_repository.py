"""SQLite user bootstrap for local API deployments."""

import sqlite3


def ensure_local_api_user(
    user_uuid: str = "local-user", db_name: str = "./database.sqlite"
) -> None:
    with sqlite3.connect(db_name, timeout=10) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                uuid TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                api_key TEXT DEFAULT NULL,
                model_name TEXT DEFAULT NULL,
                base_url TEXT DEFAULT NULL
            )
            """
        )
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(users)")}
        if "base_url" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN base_url TEXT DEFAULT NULL")
        conn.execute(
            """
            INSERT OR IGNORE INTO users (uuid, username, password)
            VALUES (?, ?, ?)
            """,
            (user_uuid, user_uuid, "local-api-user"),
        )


__all__ = ["ensure_local_api_user"]
