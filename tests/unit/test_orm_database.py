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
    assert revision == "20260814_07"
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
    assert revision == "20260814_07"
    assert "agent_tasks" in tables
