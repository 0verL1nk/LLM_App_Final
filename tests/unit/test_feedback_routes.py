"""Feedback-loop HTTP contract: findings listing, case export, click telemetry."""

from fastapi.testclient import TestClient

from api.main import app


def test_findings_route_lists_operator_findings(monkeypatch) -> None:
    from api import feedback_routes

    finding = {
        "finding_id": "fb_abc123",
        "project_uid": "project-1",
        "signal_type": "evidence_gap",
        "doc_uid": "doc-1",
        "repeat_count": 3,
        "first_seen_at": "2026-09-01T00:00:00+00:00",
        "last_seen_at": "2026-09-01T01:00:00+00:00",
        "latest_prompt_preview": "帮我总结方法",
        "latest_prompt_digest": "digest",
        "latest_run_uid": "run-1",
        "related_doc_uids": ["doc-1"],
    }
    monkeypatch.setattr(feedback_routes, "list_feedback_findings", lambda **_kwargs: [finding])
    client = TestClient(app)

    response = client.get("/api/v1/evals/feedback-findings")

    assert response.status_code == 200
    assert response.json()["data"] == [finding]


def test_export_case_route_returns_draft_or_404(monkeypatch) -> None:
    from api import feedback_routes

    draft = {
        "finding_id": "fb_abc123",
        "signal_type": "evidence_gap",
        "repeat_count": 2,
        "suggested_fixture_path": "tests/evals/fixtures/agent_task_eval_set_v1.jsonl",
        "prompt_truncated": False,
        "case": {"id": "prod_evidence_gap_abc12345", "origin": "production-finding"},
        "jsonl_line": "{\"id\": \"prod_evidence_gap_abc12345\"}",
    }

    def _draft(*, finding_id: str, **_kwargs):
        if finding_id != "fb_abc123":
            raise KeyError(f"Unknown feedback finding: {finding_id}")
        return draft

    monkeypatch.setattr(feedback_routes, "build_feedback_case_draft", _draft)
    client = TestClient(app)

    ok = client.post("/api/v1/evals/feedback-findings/fb_abc123/export-case")
    missing = client.post("/api/v1/evals/feedback-findings/fb_unknown/export-case")

    assert ok.status_code == 200
    assert ok.json()["data"] == draft
    assert missing.status_code == 404


def test_evidence_click_route_records_owned_run_clicks(monkeypatch) -> None:
    from api import feedback_routes

    calls: list[dict] = []

    def _record(**kwargs):
        calls.append(dict(kwargs))
        if kwargs["user_uuid"] != "user-1":
            raise LookupError("Run not found for this user")
        return 7

    monkeypatch.setattr(feedback_routes, "record_evidence_click", _record)
    client = TestClient(app)

    ok = client.post(
        "/api/v1/runs/run-1/evidence-clicks",
        headers={"X-User-Id": "user-1"},
        json={"evidence_ref": "doc-1:chunk_2", "item_uid": "item_1"},
    )
    missing = client.post(
        "/api/v1/runs/run-1/evidence-clicks",
        headers={"X-User-Id": "user-2"},
        json={"evidence_ref": "doc-1:chunk_2"},
    )

    assert ok.status_code == 202
    assert ok.json()["data"] == {"click_id": 7, "recorded": True}
    assert calls[0]["run_uid"] == "run-1" and calls[0]["item_uid"] == "item_1"
    assert missing.status_code == 404
