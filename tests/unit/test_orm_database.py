from pathlib import Path

from sqlalchemy import inspect, text

from agent.adapters.orm.database import build_database_url, create_engine, run_migrations


def test_database_url_resolves_desktop_path_and_preserves_explicit_url(tmp_path: Path) -> None:
    database = tmp_path / "runtime.sqlite"

    resolved = build_database_url(str(database))

    assert resolved.startswith("sqlite:///")
    assert str(database.resolve()).replace("\\", "/") in resolved
    assert build_database_url("postgresql+psycopg://user:pass@localhost/papersage").startswith(
        "postgresql+psycopg://"
    )


def test_baseline_migration_records_alembic_revision(tmp_path: Path) -> None:
    database = str(tmp_path / "migrated.sqlite")

    run_migrations(database)

    with create_engine(database).connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        tables = inspect(connection).get_table_names()
    assert revision == "20260815_11"
    assert {
        "agent_runs",
        "research_artifacts",
        "research_plans",
        "research_plan_steps",
        "agent_run_events",
        "agent_run_items",
        "agent_tasks",
        "agent_task_attempts",
        "agent_task_outbox",
        "agent_steering_inputs",
        "context_memory_items",
        "session_context_summaries",
        "agent_feature_flags",
    }.issubset(tables)


def test_run_migrations_resolves_script_location_independent_of_cwd(tmp_path: Path, monkeypatch) -> None:
    database = str(tmp_path / "runtime.sqlite")
    monkeypatch.chdir(tmp_path)

    run_migrations(database)

    with create_engine(database).connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def test_migrations_upgrade_an_existing_database_in_place(tmp_path: Path) -> None:
    from alembic import command
    from alembic.config import Config

    database = str(tmp_path / "existing.sqlite")
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", build_database_url(database))
    command.upgrade(config, "20260809_01")

    run_migrations(database)

    with create_engine(database).connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        tables = inspect(connection).get_table_names()
    assert revision == "20260815_11"
    assert "agent_tasks" in tables


def _build_drifted_database(
    tmp_path: Path,
    stamp: str = "20260814_07",
    drop_last_sequence: bool = False,
) -> str:
    """Reproduce a database whose events table predates the reconciled column set."""
    from alembic import command
    from alembic.config import Config

    database = str(tmp_path / "drifted.sqlite")
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", build_database_url(database))

    run_migrations(database)
    with create_engine(database).connect() as connection:
        for column in ("schema_version", "item_uid", "task_uid"):
            connection.exec_driver_sql(f"ALTER TABLE agent_run_events DROP COLUMN {column}")
        if drop_last_sequence:
            connection.exec_driver_sql(
                "ALTER TABLE agent_run_items DROP COLUMN last_sequence"
            )
        connection.commit()
    command.stamp(config, stamp)
    return database


def _agent_run_events_columns(database: str) -> set[str]:
    with create_engine(database).connect() as connection:
        return {column["name"] for column in inspect(connection).get_columns("agent_run_events")}


def test_migrations_reconcile_drifted_run_events_columns(tmp_path: Path) -> None:
    database = _build_drifted_database(tmp_path)

    run_migrations(database)

    assert _agent_run_events_columns(database) >= {"schema_version", "item_uid", "task_uid"}
    with create_engine(database).connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "20260815_11"
        )


def test_ensure_runtime_schema_reconciles_drifted_events(tmp_path: Path) -> None:
    from agent.adapters.orm.runtime_schema import ensure_runtime_schema

    database = _build_drifted_database(tmp_path)

    ensure_runtime_schema(database)

    assert _agent_run_events_columns(database) >= {"schema_version", "item_uid", "task_uid"}


def test_migrations_heal_legacy_events_before_backfill(tmp_path: Path) -> None:
    """A legacy database reaching migration 09 must not crash on the backfill join.

    Reproduces the packaged-desktop first launch: the events table predates the
    reconciled columns and last_sequence has never been added, so the backfill
    references events.item_uid before migration 10 could add it.
    """
    database = _build_drifted_database(tmp_path, stamp="20260815_08", drop_last_sequence=True)
    with create_engine(database).connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
        connection.exec_driver_sql(
            "INSERT INTO agent_runs "
            "(run_uid, project_uid, session_uid, uuid, client_request_id, prompt, status, created_at, updated_at) "
            "VALUES ('run-1', 'project-1', 'session-1', 'uuid-1', 'cr-1', 'test', 'completed', "
            "'2026-08-15T00:00:00Z', '2026-08-15T00:00:00Z')"
        )
        connection.exec_driver_sql(
            "INSERT INTO agent_run_items "
            "(item_uid, run_uid, item_type, status, payload_json, created_at, updated_at) "
            "VALUES ('item-1', 'run-1', 'assistant_text', 'completed', '{}', "
            "'2026-08-15T00:00:00Z', '2026-08-15T00:00:00Z')"
        )
        connection.commit()

    run_migrations(database)

    assert _agent_run_events_columns(database) >= {"schema_version", "item_uid", "task_uid"}
    with create_engine(database).connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "20260815_10"
        )
        assert (
            connection.execute(
                text("SELECT last_sequence FROM agent_run_items WHERE item_uid = 'item-1'")
            ).scalar_one()
            == 0
        )


def test_migration_09_backfills_last_sequence_from_events(tmp_path: Path) -> None:
    from alembic import command
    from alembic.config import Config

    database = str(tmp_path / "backfill.sqlite")
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", build_database_url(database))
    command.upgrade(config, "20260815_08")

    with create_engine(database).connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
        connection.exec_driver_sql(
            "INSERT INTO agent_runs "
            "(run_uid, project_uid, session_uid, uuid, client_request_id, prompt, status, created_at, updated_at) "
            "VALUES ('run-1', 'project-1', 'session-1', 'uuid-1', 'cr-1', 'test', 'completed', "
            "'2026-08-15T00:00:00Z', '2026-08-15T00:00:00Z')"
        )
        connection.exec_driver_sql(
            "INSERT INTO agent_run_items "
            "(item_uid, run_uid, item_type, status, payload_json, created_at, updated_at) "
            "VALUES ('item-1', 'run-1', 'assistant_text', 'completed', '{}', "
            "'2026-08-15T00:00:00Z', '2026-08-15T00:00:00Z')"
        )
        for event_uid, sequence, item_uid in (
            ("evt-1", 3, "item-1"),
            ("evt-2", 9, "item-1"),
            ("evt-3", 5, "item-other"),
        ):
            connection.exec_driver_sql(
                "INSERT INTO agent_run_events "
                "(event_uid, run_uid, sequence, event_type, timestamp, payload_json, schema_version, item_uid) "
                f"VALUES ('{event_uid}', 'run-1', {sequence}, 'item.completed', "
                f"'2026-08-15T00:00:00Z', '{{}}', 2, '{item_uid}')"
            )
        connection.commit()

    run_migrations(database)

    with create_engine(database).connect() as connection:
        assert (
            connection.execute(
                text("SELECT last_sequence FROM agent_run_items WHERE item_uid = 'item-1'")
            ).scalar_one()
            == 9
        )
