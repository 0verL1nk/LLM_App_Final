"""Deterministic feedback-signal rules: hit, miss, and insufficient-data paths."""

import importlib
from datetime import UTC, datetime, timedelta

from agent.feedback import rules
from agent.feedback.rules import (
    CORRECTION_SIMILARITY_THRESHOLD,
    SIGNAL_CORRECTION_FOLLOWUP,
    SIGNAL_EVIDENCE_GAP,
    SIGNAL_MODE_SWITCH_REASK,
    SteeringInputFact,
    evaluate_correction_followup,
    evaluate_evidence_gap,
    evaluate_mode_switch_reask,
    event_idempotency_key,
    prompt_digest,
    redact_preview,
    trigram_jaccard_similarity,
)

_PROMPT = "帮我总结这篇论文提出的方法与实验结论"


def _completed_at(minutes_ago: float = 0.0) -> datetime:
    return datetime.now(UTC) - timedelta(minutes=minutes_ago)


def _input(text: str, *, minutes_before_completion: float = 5.0, uid: str = "input-1") -> SteeringInputFact:
    return SteeringInputFact(
        input_uid=uid,
        text=text,
        created_at=_completed_at(minutes_before_completion).isoformat(),
    )


def test_trigram_jaccard_similarity_orders_related_above_unrelated() -> None:
    reask = _PROMPT + "，重点是实验设置"
    unrelated = "今天天气怎么样，适合出门吗"

    assert trigram_jaccard_similarity(_PROMPT, _PROMPT) == 1.0
    assert trigram_jaccard_similarity(_PROMPT, reask) > trigram_jaccard_similarity(_PROMPT, unrelated)
    assert trigram_jaccard_similarity("", _PROMPT) == 0.0
    assert trigram_jaccard_similarity("ab", _PROMPT) >= 0.0


def test_correction_followup_hits_on_leading_word() -> None:
    signals = evaluate_correction_followup(
        prompt=_PROMPT,
        steering_inputs=[_input("不对，请重新整理方法部分")],
        completed_at=_completed_at(),
    )

    assert len(signals) == 1
    assert signals[0]["signal_type"] == SIGNAL_CORRECTION_FOLLOWUP
    assert signals[0]["payload"]["rule"] == "leading_word"
    assert signals[0]["trigger_digest"] == prompt_digest("不对，请重新整理方法部分")


def test_correction_followup_hits_on_similarity() -> None:
    steering_text = _PROMPT + "，另外补充实验局限性"
    assert trigram_jaccard_similarity(steering_text, _PROMPT) >= CORRECTION_SIMILARITY_THRESHOLD

    signals = evaluate_correction_followup(
        prompt=_PROMPT,
        steering_inputs=[_input(steering_text)],
        completed_at=_completed_at(),
    )

    assert len(signals) == 1
    assert signals[0]["payload"]["rule"] == "similarity"


def test_correction_followup_misses_unrelated_text_and_out_of_window() -> None:
    assert (
        evaluate_correction_followup(
            prompt=_PROMPT,
            steering_inputs=[_input("帮我查一下别的主题的内容，谢谢")],
            completed_at=_completed_at(),
        )
        == []
    )
    assert (
        evaluate_correction_followup(
            prompt=_PROMPT,
            steering_inputs=[_input("不对，重新总结", minutes_before_completion=24 * 60)],
            completed_at=_completed_at(),
        )
        == []
    )


def test_correction_followup_skips_insufficient_data_instead_of_guessing() -> None:
    too_short_prompt = evaluate_correction_followup(
        prompt="继续",
        steering_inputs=[_input("不对，重新总结")],
        completed_at=_completed_at(),
    )
    empty_inputs = evaluate_correction_followup(
        prompt=_PROMPT,
        steering_inputs=[
            SteeringInputFact(input_uid="", text="不对，重新总结", created_at=_completed_at().isoformat()),
            SteeringInputFact(input_uid="input-2", text="   ", created_at=_completed_at().isoformat()),
            SteeringInputFact(input_uid="input-3", text="不对，重新总结", created_at="not-a-timestamp"),
        ],
        completed_at=_completed_at(),
    )

    assert too_short_prompt == []
    assert empty_inputs == []


def test_mode_switch_reask_hits_for_similar_prompt_under_new_mode() -> None:
    signal = evaluate_mode_switch_reask(
        prompt=_PROMPT + "（英文）",
        requested_mode="deep",
        previous_prompt=_PROMPT,
        previous_requested_mode="fast",
    )

    assert signal is not None
    assert signal["signal_type"] == SIGNAL_MODE_SWITCH_REASK
    assert signal["payload"]["requested_mode"] == "deep"
    assert signal["payload"]["previous_requested_mode"] == "fast"


def test_mode_switch_reask_skips_same_mode_dissimilar_or_missing_data() -> None:
    similar_prompt = _PROMPT + "（英文）"
    assert (
        evaluate_mode_switch_reask(
            prompt=similar_prompt,
            requested_mode="deep",
            previous_prompt=_PROMPT,
            previous_requested_mode="deep",
        )
        is None
    )
    assert (
        evaluate_mode_switch_reask(
            prompt="帮我规划下周的实验安排清单",
            requested_mode="deep",
            previous_prompt=_PROMPT,
            previous_requested_mode="fast",
        )
        is None
    )
    for previous_prompt in ("", "   "):
        assert (
            evaluate_mode_switch_reask(
                prompt=similar_prompt,
                requested_mode="deep",
                previous_prompt=previous_prompt,
                previous_requested_mode="fast",
            )
            is None
        )
    assert (
        evaluate_mode_switch_reask(
            prompt=similar_prompt,
            requested_mode="",
            previous_prompt=_PROMPT,
            previous_requested_mode="fast",
        )
        is None
    )


def test_evidence_gap_consumes_citation_audit_exactly() -> None:
    failed = evaluate_evidence_gap(citation_audit="failed", retrieved_evidence_count=4)
    assert failed is not None
    assert failed["signal_type"] == SIGNAL_EVIDENCE_GAP
    assert failed["payload"]["retrieved_evidence_count"] == 4
    assert evaluate_evidence_gap(citation_audit="passed", retrieved_evidence_count=4) is None
    assert evaluate_evidence_gap(citation_audit="not_applicable", retrieved_evidence_count=0) is None
    assert evaluate_evidence_gap(citation_audit="", retrieved_evidence_count=3) is None


def test_redaction_keeps_only_short_previews_and_stable_digests() -> None:
    long_text = "  方法   与实验  " + "结论" * 200

    preview = redact_preview(long_text)
    assert len(preview) <= rules.PREVIEW_MAX_CHARS
    assert "\n" not in preview and "  " not in preview

    assert prompt_digest("帮我 总结") == prompt_digest("帮我\t总结")
    assert prompt_digest("帮我总结") != prompt_digest("帮我对比")

    base = dict(user_uuid="user-1", run_uid="run-1", trigger_digest="digest-1")
    key_a = event_idempotency_key(signal_type=SIGNAL_CORRECTION_FOLLOWUP, **base)
    assert key_a == event_idempotency_key(signal_type=SIGNAL_CORRECTION_FOLLOWUP, **base)
    assert key_a != event_idempotency_key(signal_type=SIGNAL_EVIDENCE_GAP, **base)


def test_threshold_constants_are_env_overridable(monkeypatch) -> None:
    monkeypatch.setenv("PAPERSAGE_FEEDBACK_FINDING_MIN_REPEATS", "5")
    monkeypatch.setenv("PAPERSAGE_FEEDBACK_CORRECTION_SIMILARITY", "0.9")
    try:
        reloaded = importlib.reload(rules)
        assert reloaded.FINDING_MIN_REPEATS == 5
        assert reloaded.CORRECTION_SIMILARITY_THRESHOLD == 0.9
    finally:
        monkeypatch.delenv("PAPERSAGE_FEEDBACK_FINDING_MIN_REPEATS")
        monkeypatch.delenv("PAPERSAGE_FEEDBACK_CORRECTION_SIMILARITY")
        importlib.reload(rules)
    assert rules.FINDING_MIN_REPEATS == 2
