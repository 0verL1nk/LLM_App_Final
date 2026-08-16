import pytest
from pydantic import ValidationError

from agent.domain.agent_task import AtomicClaim, EvidencePacket, OpenQuestion, PacketLimitation
from agent.domain.writing import ClaimSpan, DraftRevision, ReviewFinding, WritingBrief


def test_unevidenced_claim_cannot_pose_as_paper_fact() -> None:
    with pytest.raises(ValidationError):
        AtomicClaim(statement="The method scales linearly.")

    hypothesis = AtomicClaim(statement="The method may scale linearly.", claim_type="hypothesis")
    assert hypothesis.claim_type.value == "hypothesis"
    assert hypothesis.evidence_refs == []


def test_cross_paper_synthesis_claim_keeps_its_label() -> None:
    claim = AtomicClaim(
        statement="Both papers report comparable error reductions.",
        evidence_refs=["chunk-a", "chunk-b"],
        claim_type="cross_paper_synthesis",
    )
    assert claim.claim_type.value == "cross_paper_synthesis"


def test_packet_accepts_structured_limitations_and_open_questions() -> None:
    packet = EvidencePacket.model_validate(
        {
            "summary": "方法核验完成",
            "evidence_refs": ["chunk-a"],
            "evidence": [{"chunk_id": "chunk-a", "doc_uid": "doc-a", "page_no": 3}],
            "limitations": [
                "样本量小",
                {"kind": "conflict", "statement": "两篇论文报告相反趋势", "evidence_refs": ["chunk-a"]},
            ],
            "open_questions": [
                "能否泛化？",
                {"question": "表格数据是否 OCR 可靠？", "suggested_action": "read_figure"},
            ],
        }
    )

    assert packet.limitations[0] == "样本量小"
    assert isinstance(packet.limitations[1], PacketLimitation)
    assert packet.limitations[1].kind == "conflict"
    assert isinstance(packet.open_questions[1], OpenQuestion)
    assert packet.open_questions[1].suggested_action == "read_figure"


def test_evidence_reference_carries_coordinate_and_url_provenance() -> None:
    reference = EvidencePacket.model_validate(
        {
            "summary": "图 3 数据",
            "evidence": [{"chunk_id": "chunk-a", "doc_uid": "doc-a", "page_no": 4, "bbox": [0.1, 0.2, 0.5, 0.8]}],
        }
    ).evidence[0]
    assert reference.bbox == [0.1, 0.2, 0.5, 0.8]
    assert reference.source_url == ""

    with pytest.raises(ValidationError):
        EvidencePacket.model_validate(
            {
                "summary": "坏坐标",
                "evidence": [{"chunk_id": "chunk-b", "doc_uid": "doc-b", "bbox": [0.1, 0.2]}],
            }
        )


def test_confidence_is_bounded_evidence_coverage() -> None:
    assert EvidencePacket.model_validate({"summary": "s", "confidence": 0.5}).confidence == 0.5
    with pytest.raises(ValidationError):
        EvidencePacket.model_validate({"summary": "s", "confidence": 1.5})


def test_writing_brief_requires_audience_and_purpose() -> None:
    brief = WritingBrief(audience="研究生读者", purpose="解释方法", target_section="方法", claim_budget=5)
    assert brief.style_constraints == []
    with pytest.raises(ValidationError):
        WritingBrief(audience="", purpose="解释方法")


def test_draft_revision_spans_stay_inside_the_text_and_evidence() -> None:
    text = "该方法在两个数据集上均降低了错误率。"
    revision = DraftRevision(
        section="结果",
        text=text,
        claim_ids=["claim-1"],
        evidence_refs=["chunk-a"],
        claim_spans=[ClaimSpan(claim_id="claim-1", start=0, end=12, evidence_refs=["chunk-a"])],
    )
    assert revision.claim_spans[0].start == 0

    with pytest.raises(ValidationError, match="outside the revision text"):
        DraftRevision(
            section="结果",
            text=text,
            claim_ids=["claim-1"],
            evidence_refs=["chunk-a"],
            claim_spans=[ClaimSpan(claim_id="claim-1", start=0, end=999, evidence_refs=["chunk-a"])],
        )
    with pytest.raises(ValidationError, match="absent from the revision"):
        DraftRevision(
            section="结果",
            text=text,
            claim_ids=["claim-1"],
            evidence_refs=["chunk-a"],
            claim_spans=[ClaimSpan(claim_id="claim-1", start=0, end=6, evidence_refs=["chunk-fabricated"])],
        )
    with pytest.raises(ValidationError, match="unknown claim ids"):
        DraftRevision(
            section="结果",
            text=text,
            claim_ids=["claim-1"],
            evidence_refs=["chunk-a"],
            claim_spans=[ClaimSpan(claim_id="claim-orphan", start=0, end=6, evidence_refs=["chunk-a"])],
        )


def test_review_findings_are_locatable_categories() -> None:
    finding = ReviewFinding(kind="over_claim", location="结果段第二句", note="超出样本范围")
    assert finding.kind.value == "over_claim"
    with pytest.raises(ValidationError):
        ReviewFinding(kind="vague_polish", location="全文")
