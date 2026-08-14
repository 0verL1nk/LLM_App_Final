from agent.domain.evidence_merge import merge_evidence_packets


def test_merge_keeps_opposed_claims_with_their_separate_sources() -> None:
    merged = merge_evidence_packets(
        [
            {
                "task_uid": "task-a",
                "role": "researcher",
                "status": "completed",
                "packet": {
                    "summary": "Paper A result",
                    "evidence_refs": ["chunk-a"],
                    "evidence": [{"chunk_id": "chunk-a", "doc_uid": "doc-a", "page_no": 2}],
                    "claims": [{"statement": "The intervention does reduce errors.", "evidence_refs": ["chunk-a"]}],
                    "limitations": ["Small sample"],
                    "open_questions": ["Does it generalize?"],
                },
            },
            {
                "task_uid": "task-b",
                "role": "reviewer",
                "status": "completed",
                "packet": {
                    "summary": "Paper B result",
                    "evidence_refs": ["chunk-b", "chunk-a"],
                    "evidence": [
                        {"chunk_id": "chunk-b", "doc_uid": "doc-b", "page_no": 5},
                        {"chunk_id": "chunk-a", "doc_uid": "doc-a", "page_no": 2},
                    ],
                    "claims": [{"statement": "The intervention does not reduce errors.", "evidence_refs": ["chunk-b"]}],
                    "limitations": ["Small sample"],
                    "open_questions": ["Does it generalize?"],
                },
            },
        ]
    )

    assert merged["evidence_refs"] == ["chunk-a", "chunk-b"]
    assert len(merged["claims"]) == 2
    assert {claim["task_uid"] for claim in merged["claims"]} == {"task-a", "task-b"}
    assert merged["conflicts"] == [{
        "claim_ids": ["task-a:claim:0", "task-b:claim:0"],
        "reason": "Claims make opposite explicit-negation assertions and require Leader evidence review.",
    }]
    assert merged["limitations"] == ["Small sample"]
    assert merged["open_questions"] == ["Does it generalize?"]


def test_merge_reports_failed_child_without_promoting_its_packet() -> None:
    merged = merge_evidence_packets(
        [{"task_uid": "task-failed", "role": "reviewer", "status": "failed", "error_message": "Provider timeout"}]
    )

    assert merged["claims"] == []
    assert merged["evidence_refs"] == []
    assert merged["failed_tasks"] == [{
        "task_uid": "task-failed",
        "role": "reviewer",
        "status": "failed",
        "message": "Provider timeout",
    }]
