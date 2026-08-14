import pytest
from pydantic import ValidationError

from agent.application.subagent_task_executor import _sanitize_result
from agent.domain.agent_task import EvidencePacket


def test_subagent_packet_keeps_only_authorized_project_evidence() -> None:
    packet = _sanitize_result(
        {
            "answer": "该方法在对照实验中表现更稳定。",
            "run_latency_ms": 42,
            "evidence_items": [
                {
                    "project_uid": "project-a",
                    "doc_uid": "doc-a",
                    "chunk_id": "chunk-a",
                    "page_no": 3,
                },
                {
                    "project_uid": "project-b",
                    "doc_uid": "doc-a",
                    "chunk_id": "fabricated-project",
                },
                {
                    "project_uid": "project-a",
                    "doc_uid": "deleted-doc",
                    "chunk_id": "fabricated-document",
                },
            ],
        },
        project_uid="project-a",
        allowed_doc_uids={"doc-a"},
    )

    assert packet["evidence_refs"] == ["chunk-a"]
    assert packet["evidence"] == [{"chunk_id": "chunk-a", "doc_uid": "doc-a", "page_no": 3, "offset_start": None, "offset_end": None}]


def test_evidence_packet_rejects_unstructured_claims() -> None:
    with pytest.raises(ValidationError):
        EvidencePacket.model_validate({"summary": "结论", "claims": [{"statement": ""}]})
