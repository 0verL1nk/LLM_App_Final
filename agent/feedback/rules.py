"""Deterministic feedback-signal rules for the research feedback loop.

v1 uses no model classification: every signal is a deterministic rule over
data already persisted by the durable runtime (prompts, steering inputs,
execution modes, citation audit). Constants are named and env-overridable so
thresholds can be tuned operationally without code changes.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# 修正类追问：与上一 prompt 的字符三元组 Jaccard 相似度阈值（宁漏勿滥，从紧）。
CORRECTION_SIMILARITY_THRESHOLD = float(
    os.getenv("PAPERSAGE_FEEDBACK_CORRECTION_SIMILARITY", "0.5")
)
# 修正类追问：steering 输入必须落在答案完成前后的时间窗内（分钟）。
CORRECTION_WINDOW_MINUTES = int(os.getenv("PAPERSAGE_FEEDBACK_CORRECTION_WINDOW_MINUTES", "60"))
# 修正类追问：以这些开头词直接命中（design.md D1 规则）。
CORRECTION_LEADING_WORDS: tuple[str, ...] = ("不对", "不是", "重新", "更正", "错了")
# 模式切换重问：相邻两轮 prompt 相似度阈值。
MODE_SWITCH_SIMILARITY_THRESHOLD = float(
    os.getenv("PAPERSAGE_FEEDBACK_MODE_SWITCH_SIMILARITY", "0.7")
)
# 发现聚合：同桶最小重复次数，低于该值视为一次性噪声不进入发现列表。
FINDING_MIN_REPEATS = int(os.getenv("PAPERSAGE_FEEDBACK_FINDING_MIN_REPEATS", "2"))
# 发现聚合：只统计时间窗内的事件（天）。
FINDING_WINDOW_DAYS = int(os.getenv("PAPERSAGE_FEEDBACK_FINDING_WINDOW_DAYS", "30"))
# 脱敏：payload 只保留该长度的预览片段，不落全文。
PREVIEW_MAX_CHARS = int(os.getenv("PAPERSAGE_FEEDBACK_PREVIEW_MAX_CHARS", "120"))

# 三元组相似度对过短文本无意义：低于该字符数按数据不足跳过。
_MIN_COMPARABLE_CHARS = 6

SIGNAL_CORRECTION_FOLLOWUP = "correction_followup"
SIGNAL_MODE_SWITCH_REASK = "mode_switch_reask"
SIGNAL_EVIDENCE_GAP = "evidence_gap"

# citation_audit 的合法取值（与 turn_engine 的 P3-lite 输出保持一致）。
_CITATION_AUDIT_FAILED = "failed"

_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class SteeringInputFact:
    """The persisted facts one steering input contributes to rule evaluation."""

    input_uid: str
    text: str
    created_at: str


def normalize_text(text: str) -> str:
    """Collapse whitespace so similarity is insensitive to formatting only."""
    return _WHITESPACE_RE.sub(" ", str(text or "").strip())


def trigram_jaccard_similarity(left: str, right: str) -> float:
    """Locality-sensitive character-trigram Jaccard similarity in [0, 1]."""
    left_set = _trigrams(normalize_text(left))
    right_set = _trigrams(normalize_text(right))
    if not left_set or not right_set:
        return 0.0
    intersection = len(left_set & right_set)
    union = len(left_set | right_set)
    return intersection / union if union else 0.0


def _trigrams(text: str) -> frozenset[str]:
    if len(text) < 3:
        return frozenset({text} if text else ())
    return frozenset(text[index : index + 3] for index in range(len(text) - 2))


def prompt_digest(text: str) -> str:
    """Stable sha256 digest of the normalized prompt for idempotency keys."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def redact_preview(text: str, max_chars: int = PREVIEW_MAX_CHARS) -> str:
    """Short preview only: feedback storage must never keep full prompts."""
    normalized = normalize_text(text)
    return normalized[:max(0, max_chars)]


def event_idempotency_key(
    *, user_uuid: str, run_uid: str, signal_type: str, trigger_digest: str
) -> str:
    """sha256(user + run + signal_type + digest) per design.md D2."""
    return hashlib.sha256(
        f"{user_uuid}\0{run_uid}\0{signal_type}\0{trigger_digest}".encode("utf-8")
    ).hexdigest()


def _parse_iso_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None


def evaluate_correction_followup(
    *,
    prompt: str,
    steering_inputs: list[SteeringInputFact],
    completed_at: datetime,
) -> list[dict[str, Any]]:
    """Deterministic correction rule: steering inputs that re-ask or correct.

    A steering input is a correction_followup signal when it arrived within
    CORRECTION_WINDOW_MINUTES of turn completion AND either starts with a
    correction leading word OR is at least CORRECTION_SIMILARITY_THRESHOLD
    similar to the turn prompt. Inputs with unusable data are skipped, never
    guessed.
    """
    normalized_prompt = normalize_text(prompt)
    if len(normalized_prompt) < _MIN_COMPARABLE_CHARS:
        return []
    signals: list[dict[str, Any]] = []
    for item in steering_inputs:
        text = normalize_text(item.text)
        if not text or not item.input_uid:
            continue
        created_at = _parse_iso_timestamp(item.created_at)
        if created_at is None:
            continue
        delta_minutes = (completed_at - created_at).total_seconds() / 60.0
        if delta_minutes < 0 or delta_minutes > CORRECTION_WINDOW_MINUTES:
            continue
        similarity = trigram_jaccard_similarity(text, normalized_prompt)
        leading_hit = any(text.startswith(word) for word in CORRECTION_LEADING_WORDS)
        if leading_hit:
            rule = "leading_word"
        elif similarity >= CORRECTION_SIMILARITY_THRESHOLD:
            rule = "similarity"
        else:
            continue
        signals.append(
            {
                "signal_type": SIGNAL_CORRECTION_FOLLOWUP,
                "trigger_digest": prompt_digest(text),
                "payload": {
                    "rule": rule,
                    "similarity": round(similarity, 4),
                    "input_uid": item.input_uid,
                    "steering_preview": redact_preview(text),
                    "prompt_preview": redact_preview(normalized_prompt),
                },
            }
        )
    return signals


def evaluate_mode_switch_reask(
    *,
    prompt: str,
    requested_mode: str,
    previous_prompt: str,
    previous_requested_mode: str,
) -> dict[str, Any] | None:
    """Deterministic mode-switch rule: same question re-asked under a new mode.

    Returns None (skip, no guess) whenever any required datum is missing.
    """
    normalized_prompt = normalize_text(prompt)
    normalized_previous = normalize_text(previous_prompt)
    current_mode = str(requested_mode or "").strip().lower()
    previous_mode = str(previous_requested_mode or "").strip().lower()
    if (
        len(normalized_prompt) < _MIN_COMPARABLE_CHARS
        or len(normalized_previous) < _MIN_COMPARABLE_CHARS
        or not current_mode
        or not previous_mode
        or current_mode == previous_mode
    ):
        return None
    similarity = trigram_jaccard_similarity(normalized_prompt, normalized_previous)
    if similarity < MODE_SWITCH_SIMILARITY_THRESHOLD:
        return None
    return {
        "signal_type": SIGNAL_MODE_SWITCH_REASK,
        "trigger_digest": prompt_digest(f"{normalized_previous}\0{previous_mode}\0{current_mode}"),
        "payload": {
            "similarity": round(similarity, 4),
            "requested_mode": current_mode,
            "previous_requested_mode": previous_mode,
            "prompt_preview": redact_preview(normalized_prompt),
            "previous_prompt_preview": redact_preview(normalized_previous),
        },
    }


def evaluate_evidence_gap(
    *, citation_audit: str, retrieved_evidence_count: int
) -> dict[str, Any] | None:
    """Deterministic evidence-gap rule over the turn's citation audit.

    Consumes the P3-lite ``citation_audit`` field exactly: "failed" means
    evidence was retrieved but the answer cites none of it. Any other value
    ("passed", "not_applicable") or missing data yields no signal.
    """
    if str(citation_audit or "").strip() != _CITATION_AUDIT_FAILED:
        return None
    return {
        "signal_type": SIGNAL_EVIDENCE_GAP,
        "trigger_digest": "",  # filled by the caller with the run prompt digest
        "payload": {
            "citation_audit": _CITATION_AUDIT_FAILED,
            "retrieved_evidence_count": max(0, int(retrieved_evidence_count or 0)),
        },
    }


__all__ = [
    "CORRECTION_LEADING_WORDS",
    "CORRECTION_SIMILARITY_THRESHOLD",
    "CORRECTION_WINDOW_MINUTES",
    "FINDING_MIN_REPEATS",
    "FINDING_WINDOW_DAYS",
    "MODE_SWITCH_SIMILARITY_THRESHOLD",
    "PREVIEW_MAX_CHARS",
    "SIGNAL_CORRECTION_FOLLOWUP",
    "SIGNAL_EVIDENCE_GAP",
    "SIGNAL_MODE_SWITCH_REASK",
    "SteeringInputFact",
    "event_idempotency_key",
    "evaluate_correction_followup",
    "evaluate_evidence_gap",
    "evaluate_mode_switch_reask",
    "normalize_text",
    "prompt_digest",
    "redact_preview",
    "trigram_jaccard_similarity",
]
