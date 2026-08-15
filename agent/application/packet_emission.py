"""Scope-validated EvidencePacket emission shared by every capability profile."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from ..domain.agent_task import (
    AtomicClaim,
    ClaimType,
    EvidencePacket,
    EvidenceReference,
    PacketLimitation,
)


@dataclass(frozen=True)
class EvidenceScope:
    """The evidence ids a task may cite: current project documents and this run's web results."""

    project_uid: str
    allowed_doc_uids: frozenset[str] = frozenset()
    allowed_chunk_ids: frozenset[str] = frozenset()
    # Exact URLs the run actually fetched (the web-results ledger). None means
    # no ledger exists for this run yet; URL evidence then cannot be verified
    # and enforcement is explicitly disabled rather than silently faked.
    allowed_urls: frozenset[str] | None = None

    def local_evidence_allowed(self, *, project_uid: str, doc_uid: str, chunk_id: str) -> bool:
        if project_uid.strip() != self.project_uid:
            return False
        if doc_uid not in self.allowed_doc_uids or not chunk_id:
            return False
        return chunk_id in self.allowed_chunk_ids if self.allowed_chunk_ids else True


_SECTION_HEADER = re.compile(r"^\s*[\[【]([^\]】]+)[\]】]\s*$")
_CLAIM_EVIDENCE_SUFFIX = re.compile(r"\s*[\[【]\s*(?:证据|evidence)\s*[:：]\s*([^\]】]+)[\]】]\s*$")
_LIST_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.、)])\s*")
_NARRATIVE_HEADERS = ("结论", "conclusion")
_CLAIM_HEADERS = ("主张", "claims", "claim")
_LIMITATION_HEADERS = ("局限", "limitations", "limitation")
_OPEN_QUESTION_HEADERS = ("待验证点", "开放问题", "open questions", "open question")


def parse_structured_sections(answer: str) -> dict[str, Any]:
    """Split a profile's bracketed output sections without inventing content."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in str(answer or "").splitlines():
        header = _SECTION_HEADER.match(line)
        if header is not None:
            current = header.group(1).strip().lower()
            sections.setdefault(current, [])
            continue
        if current is None:
            continue
        bulletless = _LIST_BULLET.sub("", line.strip())
        if bulletless:
            sections[current].append(bulletless)
    narrative_lines = next(
        (lines for name, lines in sections.items() if name in _NARRATIVE_HEADERS),
        [],
    )
    claims: list[dict[str, Any]] = []
    for name, lines in sections.items():
        if name not in _CLAIM_HEADERS:
            continue
        for line in lines:
            match = _CLAIM_EVIDENCE_SUFFIX.search(line)
            if match is None:
                claims.append({"statement": line, "evidence_refs": [], "claim_type": ClaimType.HYPOTHESIS.value})
                continue
            refs = [item.strip() for item in re.split(r"[,，;；]", match.group(1)) if item.strip()]
            claims.append(
                {
                    "statement": line[: match.start()].strip(),
                    "evidence_refs": refs,
                    "claim_type": ClaimType.PAPER_FACT.value,
                }
            )
    return {
        "narrative": "\n".join(narrative_lines).strip(),
        "claims": claims,
        "limitations": [
            line for name, lines in sections.items() if name in _LIMITATION_HEADERS for line in lines
        ],
        "open_questions": [
            line for name, lines in sections.items() if name in _OPEN_QUESTION_HEADERS for line in lines
        ],
    }


def build_validated_packet(
    raw_result: dict[str, Any],
    *,
    scope: EvidenceScope,
) -> tuple[EvidencePacket, dict[str, Any]]:
    """Convert one profile output into a validated packet, rejecting out-of-scope citations.

    Narrative text stays as explanation. Claims citing evidence outside the
    authorized scope have that reference dropped; a claim left without support
    cannot masquerade as a paper fact and is rejected with a recorded failure.
    """
    answer = str(raw_result.get("answer") or raw_result.get("summary") or "").strip()
    if not answer:
        raise RuntimeError("Subagent execution completed without a final answer")
    parsed = parse_structured_sections(answer)
    report: dict[str, Any] = {"dropped_evidence_items": 0, "dropped_claim_refs": [], "rejected_claims": []}

    valid_ref_ids: set[str] = set()
    evidence_entries: list[EvidenceReference] = []
    for item in raw_result.get("evidence_items") or []:
        if not isinstance(item, dict):
            continue
        reference = _evidence_reference(item, scope)
        if reference is None:
            report["dropped_evidence_items"] += 1
            continue
        if reference.chunk_id in valid_ref_ids:
            continue
        valid_ref_ids.add(reference.chunk_id)
        evidence_entries.append(reference)
    evidence_refs = [reference.chunk_id for reference in evidence_entries]

    raw_claims = raw_result.get("claims")
    if not isinstance(raw_claims, list):
        raw_claims = parsed["claims"]
    claims: list[AtomicClaim] = []
    for raw_claim in raw_claims:
        if not isinstance(raw_claim, dict) or not str(raw_claim.get("statement") or "").strip():
            continue
        candidate = dict(raw_claim)
        cited_refs = [str(ref).strip() for ref in candidate.get("evidence_refs") or [] if str(ref).strip()]
        kept_refs = [ref for ref in cited_refs if ref in valid_ref_ids]
        dropped = [ref for ref in cited_refs if ref not in valid_ref_ids]
        if dropped:
            report["dropped_claim_refs"].append({"claim": str(candidate.get("statement"))[:200], "refs": dropped})
        claim_type = str(candidate.get("claim_type") or ClaimType.PAPER_FACT.value)
        if not kept_refs and claim_type != ClaimType.HYPOTHESIS.value:
            report["rejected_claims"].append(
                {"statement": str(candidate.get("statement"))[:500], "reason": "cited_only_out_of_scope_evidence"}
            )
            continue
        candidate["evidence_refs"] = kept_refs
        if not kept_refs:
            candidate["claim_type"] = ClaimType.HYPOTHESIS.value
        claims.append(AtomicClaim.model_validate(candidate))

    raw_limitations = raw_result.get("limitations")
    limitations: list[str | PacketLimitation] = (
        list(raw_limitations) if isinstance(raw_limitations, list) else list(parsed["limitations"])
    )
    raw_open_questions = raw_result.get("open_questions")
    open_questions: list[Any] = (
        list(raw_open_questions) if isinstance(raw_open_questions, list) else list(parsed["open_questions"])
    )
    dropped_total = report["dropped_evidence_items"] + len(report["dropped_claim_refs"]) + len(report["rejected_claims"])
    if dropped_total:
        limitations.append(
            PacketLimitation(
                kind="uncovered",
                statement=(
                    f"证据范围校验拒绝了 {dropped_total} 项越界引用或主张；"
                    "这些内容不会被渲染为可定位来源。"
                ),
            )
        )

    summary = parsed["narrative"] or answer
    packet = EvidencePacket.model_validate(
        {
            "research_question": str(raw_result.get("research_question") or ""),
            "summary": summary[:6000],
            "evidence_refs": evidence_refs,
            "claims": [claim.model_dump(mode="json") for claim in claims],
            "evidence": [reference.model_dump(mode="json") for reference in evidence_entries],
            "limitations": limitations,
            "open_questions": open_questions,
            "confidence": raw_result.get("confidence"),
            "metrics": {"run_latency_ms": float(raw_result.get("run_latency_ms") or 0.0)},
        }
    )
    report["valid_evidence_refs"] = sorted(valid_ref_ids)
    return packet, report


def _evidence_reference(item: dict[str, Any], scope: EvidenceScope) -> EvidenceReference | None:
    """Accept one retrieved local chunk or web URL; everything else is out of scope."""
    doc_uid = str(item.get("doc_uid") or "").strip()
    chunk_id = str(item.get("chunk_id") or "").strip()
    source_url = str(item.get("source_url") or item.get("url") or "").strip()
    if not doc_uid and not chunk_id and source_url:
        parsed = urlparse(source_url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            if scope.allowed_urls is not None and source_url not in scope.allowed_urls:
                return None
            return EvidenceReference(
                chunk_id=source_url[:256],
                doc_uid=(parsed.netloc or "web")[:256],
                source_url=source_url,
            )
        return None
    project_uid = str(item.get("project_uid") or "").strip()
    if not scope.local_evidence_allowed(project_uid=project_uid, doc_uid=doc_uid, chunk_id=chunk_id):
        return None
    bbox = item.get("bbox")
    return EvidenceReference(
        chunk_id=chunk_id,
        doc_uid=doc_uid,
        page_no=item.get("page_no"),
        offset_start=item.get("offset_start"),
        offset_end=item.get("offset_end"),
        bbox=[float(coordinate) for coordinate in bbox] if isinstance(bbox, list) else None,
        source_url=source_url,
    )


__all__ = ["EvidenceScope", "build_validated_packet", "parse_structured_sections"]
