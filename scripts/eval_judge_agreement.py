"""Compute per-case agreement between two eval reports on the same fixture.

Usage:
    python scripts/eval_judge_agreement.py <report-a.json> <report-b.json> [--output out.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_agreement(report_a: dict[str, Any], report_b: dict[str, Any]) -> dict[str, Any]:
    cases_a = {str(case.get("case_id")): case for case in report_a.get("cases") or []}
    cases_b = {str(case.get("case_id")): case for case in report_b.get("cases") or []}
    shared_ids = sorted(set(cases_a) & set(cases_b))
    rows: list[dict[str, Any]] = []
    agree_count = 0
    for case_id in shared_ids:
        final_a = bool(cases_a[case_id].get("final_success"))
        final_b = bool(cases_b[case_id].get("final_success"))
        agree = final_a == final_b
        agree_count += int(agree)
        rows.append(
            {
                "case_id": case_id,
                "final_a": final_a,
                "final_b": final_b,
                "agree": agree,
            }
        )
    total = len(shared_ids) or 1
    return {
        "total_shared_cases": len(shared_ids),
        "agree_count": agree_count,
        "agreement_rate": agree_count / total,
        "cases": rows,
        "report_a": str((report_a.get("run_config") or {}).get("judge_model") or "a"),
        "report_b": str((report_b.get("run_config") or {}).get("judge_model") or "b"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Judge agreement between two eval reports.")
    parser.add_argument("report_a", type=Path)
    parser.add_argument("report_b", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report_a = json.loads(args.report_a.read_text(encoding="utf-8"))
    report_b = json.loads(args.report_b.read_text(encoding="utf-8"))
    agreement = build_agreement(report_a, report_b)
    if args.output:
        args.output.write_text(
            json.dumps(agreement, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(
        f"judge agreement: {agreement['agree_count']}/{agreement['total_shared_cases']} "
        f"({agreement['agreement_rate']:.0%}) "
        f"[{agreement['report_a']} vs {agreement['report_b']}]"
    )
    for row in agreement["cases"]:
        if not row["agree"]:
            print(f"  disagree: {row['case_id']} (a={row['final_a']} b={row['final_b']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
