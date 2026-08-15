import pytest

from agent.application.packet_emission import (
    EvidenceScope,
    build_validated_packet,
    parse_structured_sections,
)
from agent.application.subagent_task_executor import _sanitize_result


def _scope() -> EvidenceScope:
    return EvidenceScope(project_uid="project-a", allowed_doc_uids=frozenset({"doc-a"}))


def test_profiles_emit_packets_with_claim_evidence_rejected_outside_scope() -> None:
    packet, report = build_validated_packet(
        {
            "answer": "方法核验完成",
            "evidence_items": [
                {
                    "project_uid": "project-a",
                    "doc_uid": "doc-a",
                    "chunk_id": "chunk-a",
                    "page_no": 2,
                }
            ],
            "claims": [
                {"statement": "实验使用成对比较。", "evidence_refs": ["chunk-a"], "claim_type": "paper_fact"},
                {
                    "statement": "该方法优于所有基线。",
                    "evidence_refs": ["chunk-fabricated"],
                    "claim_type": "paper_fact",
                },
                {"statement": "该方法可能泛化到图表任务。", "claim_type": "hypothesis"},
            ],
        },
        scope=_scope(),
    )

    assert packet.summary == "方法核验完成"
    assert packet.evidence_refs == ["chunk-a"]
    assert [claim.statement for claim in packet.claims] == [
        "实验使用成对比较。",
        "该方法可能泛化到图表任务。",
    ]
    assert report["rejected_claims"] == [
        {
            "statement": "该方法优于所有基线。",
            "reason": "cited_only_out_of_scope_evidence",
        }
    ]
    assert report["dropped_claim_refs"] == [
        {"claim": "该方法优于所有基线。", "refs": ["chunk-fabricated"]}
    ]
    assert any(
        "证据范围校验" in item.statement for item in packet.limitations if hasattr(item, "statement")
    )


def test_web_url_evidence_stays_citable_while_malformed_urls_drop() -> None:
    packet, report = build_validated_packet(
        {
            "answer": "外部检索完成",
            "evidence_items": [
                {"url": "https://example.com/paper", "text": "web source"},
                {"url": "not-a-url"},
                {"project_uid": "project-b", "doc_uid": "doc-a", "chunk_id": "other-project-chunk"},
            ],
        },
        scope=_scope(),
    )

    assert packet.evidence_refs == ["https://example.com/paper"]
    assert packet.evidence[0].doc_uid == "example.com"
    assert packet.evidence[0].source_url == "https://example.com/paper"
    assert report["dropped_evidence_items"] == 2


def test_bracketed_profile_sections_become_structured_packet_fields() -> None:
    parsed = parse_structured_sections(
        "[结论]\n检索完成，共 6 条资料\n\n[主张]\n- 方法 A 有效 [证据: chunk-a, chunk-b]\n- 可能适用于图表\n\n"
        "[局限]\n未覆盖消融实验\n\n[待验证点]\n需要读取图 3"
    )
    assert parsed["narrative"] == "检索完成，共 6 条资料"
    assert parsed["claims"] == [
        {"statement": "方法 A 有效", "evidence_refs": ["chunk-a", "chunk-b"], "claim_type": "paper_fact"},
        {"statement": "可能适用于图表", "evidence_refs": [], "claim_type": "hypothesis"},
    ]
    assert parsed["limitations"] == ["未覆盖消融实验"]
    assert parsed["open_questions"] == ["需要读取图 3"]


def test_narrative_summary_survives_without_sections() -> None:
    packet, _report = build_validated_packet({"answer": "纯文本结论"}, scope=_scope())
    assert packet.summary == "纯文本结论"
    assert packet.claims == []


def test_missing_narrative_fails_hard() -> None:
    with pytest.raises(RuntimeError):
        build_validated_packet({"answer": "  "}, scope=_scope())


def test_sanitize_result_keeps_project_and_document_scope_enforcement() -> None:
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
    assert packet["evidence"][0]["chunk_id"] == "chunk-a"
    assert packet["evidence"][0]["doc_uid"] == "doc-a"
    assert packet["evidence"][0]["page_no"] == 3
    assert packet["research_question"] == ""
