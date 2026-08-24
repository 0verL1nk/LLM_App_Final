from scripts.eval_judge_agreement import build_agreement



def _report(finals: dict[str, bool]) -> dict:
    return {
        "run_config": {"judge_model": "j"},
        "cases": [{"case_id": k, "final_success": v} for k, v in finals.items()],
    }


def test_build_agreement_counts_and_rates() -> None:
    a = _report({"x": True, "y": False, "z": True})
    b = _report({"x": True, "y": True, "z": False})
    result = build_agreement(a, b)
    assert result["total_shared_cases"] == 3
    assert result["agree_count"] == 1
    assert result["agreement_rate"] == 1 / 3
    disagree_ids = [row["case_id"] for row in result["cases"] if not row["agree"]]
    assert disagree_ids == ["y", "z"]


def test_build_agreement_empty_overlap_does_not_divide_by_zero() -> None:
    result = build_agreement(_report({}), _report({}))
    assert result["agreement_rate"] == 0.0
