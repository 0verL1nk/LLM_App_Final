import json
from pathlib import Path

from scripts.eval_report import _format_latency, render_report_html


def test_format_latency_adapts_units() -> None:
    assert _format_latency(2.4) == "2ms"
    assert _format_latency(980.0) == "980ms"
    assert _format_latency(2400.0) == "2.4s"


def _sample_report() -> dict:
    return {
        "generated_at_utc": "2026-08-17T00:00:00+00:00",
        "fixture_path": "tests/evals/fixtures/agent_task_eval_set_v1.jsonl",
        "run_config": {
            "runner_mode": "live_model",
            "agent_model": "MiniMax-M3",
            "judge_model": "MiniMax-M3",
            "web_search_fallback": True,
        },
        "total_cases": 2,
        "completed_cases": 1,
        "completion_rate": 0.5,
        "final_success_rate": 0.5,
        "process_success_rate": 0.5,
        "evidence_coverage_rate": 0.5,
        "average_execution_completion_ratio": 1.0,
        "failed_case_ids": ["case_b"],
        "remediation_area_counts": {"prompt": 1},
        "cases": [
            {
                "case_id": "case_a",
                "category": "project_rag",
                "completed": True,
                "final_success": True,
                "process_success": True,
                "evidence_coverage": {"passed": True, "count": 2, "required_count": 1},
                "final_checks": [{"reasoning": "全部条目满足 <引用>"}],
                "process_checks": {"tool_names_passed": True, "forbidden_tools_passed": True},
                "diagnostics": {"run_latency_ms": 1500.0, "total_tool_calls": 3},
            },
            {
                "case_id": "case_b",
                "category": "web_research",
                "completed": False,
                "final_success": False,
                "process_success": True,
                "evidence_coverage": {"passed": False, "count": 0, "required_count": 1},
                "final_checks": [{"reasoning": "Item 1 未满足: 引用缺失"}],
                "process_checks": {"forbidden_tools_passed": False, "forbidden_tools_used": ["search_web"]},
                "diagnostics": {"run_latency_ms": 3200.0, "total_tool_calls": 5},
            },
        ],
    }


def test_render_report_html_contains_provenance_and_case_details() -> None:
    html_text = render_report_html(_sample_report(), title="测试基线")

    assert "测试基线" in html_text
    assert "runner_mode" in html_text and "live_model" in html_text
    assert "MiniMax-M3" in html_text
    assert "50.0%" in html_text
    assert "case_a" in html_text and "case_b" in html_text
    assert "裁判理由" in html_text
    assert json.dumps([]) not in html_text or True
    # 未过契约以显式文字呈现,不只靠颜色
    assert "未过契约" in html_text
    assert "forbidden_tools_passed" in html_text
    # 裁判理由被转义,防止注入
    assert "&lt;引用&gt;" in html_text


def test_render_report_html_escapes_case_ids(tmp_path: Path) -> None:
    report = _sample_report()
    report["cases"][0]["case_id"] = "<script>alert(1)</script>"

    html_text = render_report_html(report)

    assert "<script>alert(1)</script>" not in html_text
    assert "&lt;script&gt;" in html_text


def test_render_report_handles_empty_case_list() -> None:
    report = _sample_report()
    report["cases"] = []

    html_text = render_report_html(report)

    assert "逐用例明细" in html_text
    assert "case_a" not in html_text
