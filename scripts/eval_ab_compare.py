"""Side-by-side comparison of two eval reports (A/B arms).

Usage:
    python scripts/eval_ab_compare.py <control.json> <treatment.json> [--output out.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _arm_metrics(report: dict[str, Any]) -> dict[str, Any]:
    cases = report.get("cases") or []
    trial_total = 0
    trial_pass = 0
    process_pass = 0
    for case in cases:
        trials = (case.get("trials") or {}).get("summary") or []
        for trial in trials:
            trial_total += 1
            trial_pass += int(bool(trial.get("completed")))
            process_pass += int(bool(trial.get("process_success")))
    return {
        "cases": len(cases),
        "pass_k_cases": sum(1 for case in cases if bool(case.get("completed"))),
        "trials": trial_total,
        "trial_completion_rate": trial_pass / trial_total if trial_total else 0.0,
        "trial_process_rate": process_pass / trial_total if trial_total else 0.0,
        "final_rate": float(report.get("final_success_rate") or 0.0),
        "evidence_rate": float(report.get("evidence_coverage_rate") or 0.0),
    }


def build_comparison(control: dict[str, Any], treatment: dict[str, Any]) -> dict[str, Any]:
    control_cases = {str(c.get("case_id")): c for c in control.get("cases") or []}
    treatment_cases = {str(c.get("case_id")): c for c in treatment.get("cases") or []}
    rows: list[dict[str, Any]] = []
    for case_id in sorted(set(control_cases) & set(treatment_cases)):
        c = control_cases[case_id]
        t = treatment_cases[case_id]
        c_trials = (c.get("trials") or {}).get("passed_trials")
        t_trials = (t.get("trials") or {}).get("passed_trials")
        rows.append(
            {
                "case_id": case_id,
                "control_pass": bool(c.get("completed")),
                "treatment_pass": bool(t.get("completed")),
                "control_trials_passed": c_trials if c_trials is not None else int(bool(c.get("completed"))),
                "treatment_trials_passed": t_trials if t_trials is not None else int(bool(t.get("completed"))),
            }
        )
    flipped = [r for r in rows if r["control_pass"] != r["treatment_pass"]]
    return {
        "control": _arm_metrics(control),
        "treatment": _arm_metrics(treatment),
        "cases": rows,
        "flipped": flipped,
        "flipped_count": len(flipped),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two eval report arms.")
    parser.add_argument("control", type=Path)
    parser.add_argument("treatment", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    control = json.loads(args.control.read_text(encoding="utf-8"))
    treatment = json.loads(args.treatment.read_text(encoding="utf-8"))
    comparison = build_comparison(control, treatment)
    if args.output:
        args.output.write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    for arm in ("control", "treatment"):
        m = comparison[arm]
        print(
            f"{arm:10s} pass^k {m['pass_k_cases']}/{m['cases']} | "
            f"trial completion {m['trial_completion_rate']:.0%} | "
            f"trial process {m['trial_process_rate']:.0%} | "
            f"final {m['final_rate']:.0%} | evidence {m['evidence_rate']:.0%}"
        )
    print(f"flipped cases: {comparison['flipped_count']}")
    for row in comparison["flipped"]:
        direction = "UP" if row["treatment_pass"] else "DOWN"
        print(
            f"  {direction}: {row['case_id']} "
            f"(trials {row['control_trials_passed']} -> {row['treatment_trials_passed']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
