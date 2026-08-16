"""Conservative, conflict-preserving merge for completed child evidence packets."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .agent_task import EvidencePacket, OpenQuestion, PacketLimitation


def merge_evidence_packets(child_results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Merge validated packets without selecting a winner or scheduling more work."""
    evidence: dict[str, dict[str, Any]] = {}
    claims: list[dict[str, Any]] = []
    limitations: list[str] = []
    open_questions: list[str] = []
    failed_tasks: list[dict[str, str]] = []
    summaries: list[dict[str, str]] = []
    for child in child_results:
        task_uid = str(child.get("task_uid") or "").strip()
        role = str(child.get("role") or "unknown").strip() or "unknown"
        status = str(child.get("status") or "failed")
        packet_data = child.get("packet") if isinstance(child.get("packet"), dict) else {}
        if status != "completed":
            failed_tasks.append({"task_uid": task_uid, "role": role, "status": status, "message": str(child.get("error_message") or "")[:600]})
            continue
        try:
            packet = EvidencePacket.model_validate(packet_data)
        except ValueError:
            failed_tasks.append({"task_uid": task_uid, "role": role, "status": "invalid_packet", "message": "Child result did not match the evidence packet contract."})
            continue
        summaries.append({"task_uid": task_uid, "role": role, "summary": packet.summary})
        for reference in packet.evidence:
            evidence.setdefault(reference.chunk_id, reference.model_dump(mode="json"))
        for index, claim in enumerate(packet.claims):
            claims.append({"claim_id": f"{task_uid}:claim:{index}", "task_uid": task_uid, "role": role, **claim.model_dump(mode="json")})
        limitations.extend(text for item in packet.limitations if (text := _limitation_text(item)))
        open_questions.extend(text for item in packet.open_questions if (text := _question_text(item)))
    return {
        "schema_version": 1,
        "evidence_refs": sorted(evidence),
        "evidence": list(evidence.values()),
        "claims": claims,
        "conflicts": _find_explicit_negation_conflicts(claims),
        "limitations": _deduplicate(limitations),
        "open_questions": _deduplicate(open_questions),
        "failed_tasks": failed_tasks,
        "packet_summaries": summaries,
    }


def _limitation_text(item: str | PacketLimitation) -> str:
    return item if isinstance(item, str) else item.statement


def _question_text(item: str | OpenQuestion) -> str:
    return item if isinstance(item, str) else item.question


def _find_explicit_negation_conflicts(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for index, left in enumerate(claims):
        for right in claims[index + 1 :]:
            if _negation_base(str(left["statement"])) != _negation_base(str(right["statement"])):
                continue
            if _has_negation(str(left["statement"])) == _has_negation(str(right["statement"])):
                continue
            conflicts.append({"claim_ids": [str(left["claim_id"]), str(right["claim_id"])], "reason": "Claims make opposite explicit-negation assertions and require Leader evidence review."})
    return conflicts


def _negation_base(statement: str) -> str:
    return re.sub(r"(?:\bnot\b|\bno\b|不|未|无|沒有|没有)", "", statement.lower()).replace(" ", "")


def _has_negation(statement: str) -> bool:
    return bool(re.search(r"(?:\bnot\b|\bno\b|不|未|无|沒有|没有)", statement.lower()))


def _deduplicate(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


__all__ = ["merge_evidence_packets"]
