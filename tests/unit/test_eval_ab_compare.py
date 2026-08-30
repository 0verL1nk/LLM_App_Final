from scripts.eval_ab_compare import build_comparison


def _case(case_id: str, completed: bool, passed_trials: int | None = None) -> dict:
    return {
        "case_id": case_id,
        "completed": completed,
        "final_success": completed,
        "process_success": completed,
        "trials": (
            {"summary": [{"completed": i < passed_trials, "process_success": i < passed_trials} for i in range(2)]}
            if passed_trials is not None
            else None
        ),
    }


def _report(cases: list[dict]) -> dict:
    return {
        "cases": cases,
        "final_success_rate": 0.5,
        "evidence_coverage_rate": 1.0,
    }


def test_build_comparison_reports_arm_metrics_and_flips() -> None:
    control = _report(
        [
            _case("a", True, 2),
            _case("b", False, 0),
            _case("c", True, 1),
        ]
    )
    treatment = _report(
        [
            _case("a", True, 2),
            _case("b", True, 1),
            _case("c", False, 0),
        ]
    )

    result = build_comparison(control, treatment)

    assert result["control"]["pass_k_cases"] == 2
    assert result["treatment"]["pass_k_cases"] == 2
    assert result["control"]["trial_completion_rate"] == 3 / 6
    assert result["treatment"]["trial_completion_rate"] == 3 / 6
    assert result["flipped_count"] == 2
    flipped_ids = sorted(row["case_id"] for row in result["flipped"])
    assert flipped_ids == ["b", "c"]


def test_build_comparison_handles_single_trial_reports() -> None:
    control = _report([_case("x", True)])
    treatment = _report([_case("x", False)])

    result = build_comparison(control, treatment)

    assert result["flipped_count"] == 1
    assert result["flipped"][0]["treatment_trials_passed"] == 0
