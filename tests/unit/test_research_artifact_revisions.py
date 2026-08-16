from pathlib import Path

from agent.adapters.orm.database import build_database_url, run_migrations
from agent.adapters.orm.research_artifact_repository import (
    add_research_artifact_revision,
    create_research_artifact,
    create_scoped_research_artifact,
    decide_research_artifact_revision,
    get_research_artifact,
    list_research_artifact_revisions,
    list_research_artifacts,
)
from agent.adapters.orm.run_repository import create_run
from agent.adapters.orm.task_dispatch_repository import create_agent_task
from agent.domain.agent_task import AgentTaskKind


def _setup_run_and_task(database: str) -> tuple[str, str]:
    run, _created = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="revisions-run",
        prompt="研究问题",
        db_name=database,
    )
    task, _created = create_agent_task(
        run_uid=str(run["run_uid"]),
        kind=AgentTaskKind.SUBAGENT,
        agent_role="researcher",
        idempotency_key="revisions-task",
        input_payload={"objective": "检索"},
        db_name=database,
    )
    return str(run["run_uid"]), str(task["task_uid"])


def test_task_artifact_persists_accepted_first_revision_with_provenance(tmp_path: Path) -> None:
    database = str(tmp_path / "revisions.sqlite")
    run_uid, task_uid = _setup_run_and_task(database)

    artifact, created = create_research_artifact(
        task_uid=task_uid,
        artifact_type="evidence_packet",
        content={"summary": "结论", "evidence_refs": ["chunk-a"]},
        evidence_refs=["chunk-a"],
        db_name=database,
    )
    assert created
    assert artifact["uuid"] == "user-1"
    revisions = list_research_artifact_revisions(artifact_uid=artifact["artifact_uid"], db_name=database)
    assert len(revisions) == 1
    assert revisions[0]["revision"] == 1
    assert revisions[0]["status"] == "accepted"
    assert revisions[0]["source_run_uid"] == run_uid
    assert revisions[0]["source_task_uid"] == task_uid
    assert revisions[0]["evidence_refs"] == ["chunk-a"]


def test_accepting_a_revision_supersedes_without_overwriting(tmp_path: Path) -> None:
    database = str(tmp_path / "decide.sqlite")
    artifact = create_scoped_research_artifact(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        artifact_type="writing_draft",
        content={"revision": {"text": "初稿"}},
        evidence_refs=["chunk-a"],
        db_name=database,
    )
    artifact_uid = artifact["artifact_uid"]

    second = add_research_artifact_revision(
        artifact_uid=artifact_uid,
        content={"revision": {"text": "第二稿"}},
        evidence_refs=["chunk-a", "chunk-b"],
        db_name=database,
    )
    decided, changed = decide_research_artifact_revision(
        artifact_uid=artifact_uid,
        revision_uid=second["revision_uid"],
        decision="accepted",
        note="采用第二稿",
        db_name=database,
    )
    assert changed is True
    assert decided["status"] == "accepted"
    assert decided["decision_note"] == "采用第二稿"

    revisions = list_research_artifact_revisions(artifact_uid=artifact_uid, db_name=database)
    assert [revision["status"] for revision in revisions] == ["proposed", "accepted"]
    assert [revision["revision"] for revision in revisions] == [1, 2]
    # The original first revision keeps its exact content.
    assert revisions[0]["content"] == {"revision": {"text": "初稿"}}
    assert revisions[1]["content"] == {"revision": {"text": "第二稿"}}

    third = add_research_artifact_revision(
        artifact_uid=artifact_uid,
        content={"revision": {"text": "第三稿"}},
        evidence_refs=[],
        based_on_revision_uid=second["revision_uid"],
        db_name=database,
    )
    rejected, changed = decide_research_artifact_revision(
        artifact_uid=artifact_uid,
        revision_uid=third["revision_uid"],
        decision="rejected",
        db_name=database,
    )
    assert changed is True
    assert rejected["status"] == "rejected"
    statuses = [revision["status"] for revision in list_research_artifact_revisions(artifact_uid=artifact_uid, db_name=database)]
    assert statuses == ["proposed", "accepted", "rejected"]

    _same, changed_again = decide_research_artifact_revision(
        artifact_uid=artifact_uid,
        revision_uid=second["revision_uid"],
        decision="accepted",
        db_name=database,
    )
    assert changed_again is False


def test_scoped_artifacts_are_visible_only_to_their_owner(tmp_path: Path) -> None:
    database = str(tmp_path / "scoped.sqlite")
    create_scoped_research_artifact(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        artifact_type="writing_draft",
        content={"revision": {"text": "草稿"}},
        evidence_refs=["chunk-a"],
        validity_scope="project:project-1/session:session-1",
        db_name=database,
    )
    artifact = create_scoped_research_artifact(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-2",
        artifact_type="writing_draft",
        content={"revision": {"text": "他人草稿"}},
        evidence_refs=[],
        db_name=database,
    )

    visible = list_research_artifacts(
        project_uid="project-1", session_uid="session-1", user_uuid="user-1", db_name=database
    )
    assert [item["uuid"] for item in visible] == ["user-1"]
    assert visible[0]["run_uid"] is None
    assert visible[0]["task_uid"] is None
    fetched = get_research_artifact(artifact_uid=artifact["artifact_uid"], db_name=database)
    assert fetched is not None and fetched["uuid"] == "user-2"


def test_migration_backfills_owner_and_relaxes_task_binding(tmp_path: Path) -> None:
    from alembic import command
    from alembic.config import Config

    database = str(tmp_path / "legacy.sqlite")
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", build_database_url(database))
    command.upgrade(config, "20260815_10")

    from sqlalchemy import text

    from agent.adapters.orm.database import create_engine

    with create_engine(database).connect() as connection:
        connection.execute(
            text(
                """
                INSERT INTO agent_runs (run_uid, project_uid, session_uid, uuid, client_request_id,
                    prompt, status, error_message, requested_mode, resolved_mode, route_reason,
                    created_at, updated_at)
                VALUES ('run-legacy', 'project-1', 'session-1', 'user-legacy', 'req-1',
                    '问题', 'completed', '', 'auto', 'react', 'test', '2026-08-15T00:00:00', '2026-08-15T00:00:00')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO agent_tasks (task_uid, run_uid, kind, status, idempotency_key, created_at, updated_at)
                VALUES ('task-legacy', 'run-legacy', 'subagent', 'completed', 'legacy', '2026-08-15T00:00:00', '2026-08-15T00:00:00')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO research_artifacts (artifact_uid, project_uid, session_uid, run_uid, task_uid,
                    artifact_type, content_json, evidence_refs_json, created_at, updated_at)
                VALUES ('artifact-legacy', 'project-1', 'session-1', 'run-legacy', 'task-legacy',
                    'evidence_packet', '{}', '[]', '2026-08-15T00:00:00', '2026-08-15T00:00:00')
                """
            )
        )
        connection.commit()

    run_migrations(database)

    with create_engine(database).connect() as connection:
        owner = connection.execute(
            text("SELECT uuid FROM research_artifacts WHERE artifact_uid = 'artifact-legacy'")
        ).scalar_one()
        revision_rows = connection.execute(
            text("SELECT COUNT(*) FROM research_artifact_revisions")
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO research_artifacts (artifact_uid, project_uid, session_uid, uuid, run_uid, task_uid,
                    artifact_type, content_json, evidence_refs_json, validity_scope, update_policy,
                    created_at, updated_at)
                VALUES ('artifact-free', 'project-1', 'session-1', 'user-legacy', NULL, NULL,
                    'writing_draft', '{}', '[]', '', '', '2026-08-15T00:01:00', '2026-08-15T00:01:00')
                """
            )
        )
        connection.commit()
    assert owner == "user-legacy"
    assert revision_rows == 0
