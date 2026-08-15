from pathlib import Path

from fastapi.testclient import TestClient

from agent.adapters.orm.research_artifact_repository import (
    create_scoped_research_artifact,
)
from agent.adapters.orm.run_repository import create_run
from agent.adapters.sqlite.project_repository import create_project, create_project_session
from api import writing_routes
from api.main import app


def _revision_payload(text: str, refs: list[str], span_refs: list[str]) -> dict:
    return {
        "section": "结果",
        "text": text,
        "claim_ids": ["claim-1"],
        "evidence_refs": refs,
        "claim_spans": [
            {"claim_id": "claim-1", "start": 0, "end": min(6, len(text)), "evidence_refs": span_refs}
        ],
        "rationale": "改写",
        "unsupported_claims": [],
        "citation_gaps": [],
        "review_findings": [],
    }


def _setup(monkeypatch, tmp_path: Path) -> tuple[str, str, str]:
    database = str(tmp_path / "writing-routes.sqlite")
    project = create_project(uuid="user-1", project_name="研究", description="", db_name=database)
    project_uid = project["project_uid"]
    session = create_project_session(project_uid, "user-1", db_name=database)
    session_uid = session["session_uid"]
    run, _created = create_run(
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid="user-1",
        client_request_id="writing-run",
        prompt="写作请求",
        db_name=database,
    )
    create_scoped_research_artifact(
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid="user-1",
        artifact_type="evidence_packet",
        content={"summary": "证据包"},
        evidence_refs=["chunk-a"],
        db_name=database,
    )

    original_get = writing_routes.get_research_artifact
    original_list = writing_routes.list_research_artifacts
    original_scoped = writing_routes.create_scoped_research_artifact
    original_add = writing_routes.add_research_artifact_revision
    original_decide = writing_routes.decide_research_artifact_revision
    original_revisions = writing_routes.list_research_artifact_revisions

    monkeypatch.setattr(writing_routes, "require_project", lambda **_kwargs: {})
    monkeypatch.setattr(
        writing_routes,
        "list_project_sessions",
        lambda project_uid, uuid: (
            [{"session_uid": session_uid}] if uuid == "user-1" else []
        ),
    )
    monkeypatch.setattr(
        writing_routes,
        "get_research_artifact",
        lambda **kwargs: original_get(**kwargs, db_name=database),
    )
    monkeypatch.setattr(
        writing_routes,
        "list_research_artifacts",
        lambda **kwargs: original_list(**kwargs, db_name=database),
    )
    monkeypatch.setattr(
        writing_routes,
        "create_scoped_research_artifact",
        lambda **kwargs: original_scoped(**kwargs, db_name=database),
    )
    monkeypatch.setattr(
        writing_routes,
        "add_research_artifact_revision",
        lambda **kwargs: original_add(**kwargs, db_name=database),
    )
    monkeypatch.setattr(
        writing_routes,
        "decide_research_artifact_revision",
        lambda **kwargs: original_decide(**kwargs, db_name=database),
    )
    monkeypatch.setattr(
        writing_routes,
        "list_research_artifact_revisions",
        lambda **kwargs: original_revisions(**kwargs, db_name=database),
    )
    return project_uid, session_uid, str(run["run_uid"])


def test_writing_draft_flow_keeps_revisions_non_destructive(monkeypatch, tmp_path: Path) -> None:
    project_uid, session_uid, run_uid = _setup(monkeypatch, tmp_path)
    client = TestClient(app)

    created = client.post(
        f"/api/v1/projects/{project_uid}/sessions/{session_uid}/research-artifacts/writing-drafts",
        json={
            "brief": {
                "audience": "研究生",
                "purpose": "解释方法",
                "target_section": "方法",
                "claim_budget": 3,
                "style_constraints": ["简洁"],
            },
            "revision": _revision_payload("该方法降低了错误率。", ["chunk-a"], ["chunk-a"]),
            "source_run_uid": run_uid,
        },
        headers={"X-User-Id": "user-1"},
    )
    assert created.status_code == 201, created.text
    artifact = created.json()["data"]
    assert artifact["artifact_type"] == "writing_draft"
    assert artifact["run_uid"] == run_uid
    assert artifact["content"]["brief"]["audience"] == "研究生"
    assert artifact["content"]["revision"]["claim_spans"][0]["evidence_refs"] == ["chunk-a"]
    artifact_uid = artifact["artifact_uid"]

    rewrite = client.post(
        f"/api/v1/research-artifacts/{artifact_uid}/revisions",
        json={
            "revision": _revision_payload("该方法在两个数据集上降低了错误率。", ["chunk-a", "chunk-fake"], ["chunk-a", "chunk-fake"]),
        },
        headers={"X-User-Id": "user-1"},
    )
    assert rewrite.status_code == 201, rewrite.text
    revision = rewrite.json()["data"]
    assert revision["revision"] == 2
    assert revision["status"] == "proposed"
    assert revision["evidence_refs"] == ["chunk-a"]
    assert revision["content"]["revision"]["claim_spans"][0]["evidence_refs"] == ["chunk-a"]
    assert "chunk-fake" in revision["content"]["validation"]["dropped_evidence_refs"]
    assert any("chunk-fake" in gap for gap in revision["content"]["revision"]["citation_gaps"])
    revision_uid = revision["revision_uid"]

    accepted = client.post(
        f"/api/v1/research-artifacts/{artifact_uid}/revisions/{revision_uid}/decision",
        json={"decision": "accepted", "note": "采用"},
        headers={"X-User-Id": "user-1"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["data"]["status"] == "accepted"
    assert accepted.json()["data"]["changed"] is True

    listed = client.get(f"/api/v1/research-artifacts/{artifact_uid}/revisions", headers={"X-User-Id": "user-1"})
    assert listed.status_code == 200
    revisions = listed.json()["data"]
    assert [item["status"] for item in revisions] == ["proposed", "accepted"]
    assert revisions[0]["content"]["revision"]["text"] == "该方法降低了错误率。"
    assert revisions[1]["content"]["revision"]["text"] == "该方法在两个数据集上降低了错误率。"


def test_writing_routes_enforce_ownership_and_session_scope(monkeypatch, tmp_path: Path) -> None:
    project_uid, session_uid, _database = _setup(monkeypatch, tmp_path)
    client = TestClient(app)

    created = client.post(
        f"/api/v1/projects/{project_uid}/sessions/{session_uid}/research-artifacts/writing-drafts",
        json={
            "brief": {"audience": "读者", "purpose": "综述"},
            "revision": _revision_payload("草稿文本。", [], []),
        },
        headers={"X-User-Id": "user-1"},
    )
    assert created.status_code == 201
    artifact_uid = created.json()["data"]["artifact_uid"]

    forbidden = client.get(
        f"/api/v1/research-artifacts/{artifact_uid}/revisions", headers={"X-User-Id": "user-2"}
    )
    assert forbidden.status_code == 404

    unknown_session = client.post(
        f"/api/v1/projects/{project_uid}/sessions/missing-session/research-artifacts/writing-drafts",
        json={
            "brief": {"audience": "读者", "purpose": "综述"},
            "revision": _revision_payload("草稿文本。", [], []),
        },
        headers={"X-User-Id": "user-1"},
    )
    assert unknown_session.status_code == 404

    decided_twice = client.post(
        f"/api/v1/research-artifacts/{artifact_uid}/revisions/revision-missing/decision",
        json={"decision": "accepted"},
        headers={"X-User-Id": "user-1"},
    )
    assert decided_twice.status_code == 404
