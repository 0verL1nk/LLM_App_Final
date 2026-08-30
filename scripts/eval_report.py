"""Render a task-completion eval baseline JSON into a self-contained HTML report.

Usage:
    python scripts/eval_report.py docs/plans/baselines/<baseline>.json [--output out.html]
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

STATUS_PASS_LABEL = "✓ 通过"
STATUS_FAIL_LABEL = "✗ 失败"

STYLE = """
:root { color-scheme: light; }
body {
  margin: 0; padding: 32px 24px 64px;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  background: #f9f9f7; color: #0b0b0b;
}
body.dark { color-scheme: dark; background: #0d0d0d; color: #ffffff; }
.wrap { max-width: 1080px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 15px; margin: 32px 0 12px; color: #52514e; font-weight: 600; }
body.dark h2 { color: #c3c2b7; }
.meta { font-size: 13px; color: #898781; margin-bottom: 8px; }
.meta code { background: rgba(11,11,11,0.05); padding: 1px 5px; border-radius: 4px; }
body.dark .meta code { background: rgba(255,255,255,0.08); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.tile {
  background: #fcfcfb; border: 1px solid rgba(11,11,11,0.10); border-radius: 10px;
  padding: 14px 16px;
}
body.dark .tile { background: #1a1a19; border-color: rgba(255,255,255,0.10); }
.tile .label { font-size: 12px; color: #898781; margin-bottom: 6px; }
.tile .value { font-size: 26px; font-weight: 650; }
.tile .sub { font-size: 12px; color: #898781; margin-top: 4px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th {
  text-align: left; font-weight: 600; color: #898781; padding: 8px 10px;
  border-bottom: 1px solid #e1e0d9; white-space: nowrap;
}
body.dark th { border-bottom-color: #2c2c2a; }
td { padding: 8px 10px; border-bottom: 1px solid #e1e0d9; vertical-align: top; }
body.dark td { border-bottom-color: #2c2c2a; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.badge {
  display: inline-flex; align-items: center; gap: 4px; font-size: 12px;
  padding: 2px 8px; border-radius: 999px; white-space: nowrap;
}
.badge.good { color: #006300; background: rgba(12,163,12,0.12); }
.badge.critical { color: #d03b3b; background: rgba(208,59,59,0.10); }
body.dark .badge.good { color: #0ca30c; }
body.dark .badge.critical { color: #e66767; }
.barcell { display: flex; align-items: center; gap: 8px; min-width: 180px; }
.bartrack { flex: 1; height: 8px; background: rgba(11,11,11,0.06); border-radius: 4px; }
body.dark .bartrack { background: rgba(255,255,255,0.08); }
.bar {
  height: 8px; border-radius: 0 4px 4px 0; background: #2a78d6; position: relative;
}
body.dark .bar { background: #3987e5; }
.barlabel { font-size: 12px; color: #52514e; white-space: nowrap; font-variant-numeric: tabular-nums; }
body.dark .barlabel { color: #c3c2b7; }
details { margin-top: 2px; }
details summary { cursor: pointer; color: #2a78d6; font-size: 12px; }
body.dark details summary { color: #3987e5; }
pre.reason {
  white-space: pre-wrap; font-size: 12px; line-height: 1.55; margin: 8px 0 0;
  padding: 10px 12px; background: rgba(11,11,11,0.04); border-radius: 8px;
  color: #52514e; font-family: inherit;
}
body.dark pre.reason { background: rgba(255,255,255,0.05); color: #c3c2b7; }
.failed-checks { font-size: 12px; color: #d03b3b; margin-top: 2px; }
body.dark .failed-checks { color: #e66767; }
@media (prefers-color-scheme: dark) {
  body:not(.light) { color-scheme: dark; background: #0d0d0d; color: #ffffff; }
  body:not(.light) h2 { color: #c3c2b7; }
  body:not(.light) .tile { background: #1a1a19; border-color: rgba(255,255,255,0.10); }
  body:not(.light) th { border-bottom-color: #2c2c2a; }
  body:not(.light) td { border-bottom-color: #2c2c2a; }
  body:not(.light) .badge.good { color: #0ca30c; }
  body:not(.light) .badge.critical { color: #e66767; }
  body:not(.light) .bartrack { background: rgba(255,255,255,0.08); }
  body:not(.light) .bar { background: #3987e5; }
  body:not(.light) .barlabel { color: #c3c2b7; }
  body:not(.light) details summary { color: #3987e5; }
  body:not(.light) pre.reason { background: rgba(255,255,255,0.05); color: #c3c2b7; }
}
"""


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "-"


def _format_latency(ms: float) -> str:
    if ms < 1000.0:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _tile(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="sub">{_esc(sub)}</div>' if sub else ""
    return f'<div class="tile"><div class="label">{_esc(label)}</div><div class="value">{_esc(value)}</div>{sub_html}</div>'


def _badge(passed: bool) -> str:
    css, label = ("good", STATUS_PASS_LABEL) if passed else ("critical", STATUS_FAIL_LABEL)
    return f'<span class="badge {css}">{label}</span>'


def _bar(passed: int, total: int, tip: str) -> str:
    share = (passed / total * 100) if total else 0.0
    return (
        '<div class="barcell">'
        f'<div class="bartrack"><div class="bar" style="width:{share:.1f}%" title="{_esc(tip)}"></div></div>'
        f'<span class="barlabel">{passed}/{total}</span>'
        "</div>"
    )


def _case_row(case: dict[str, Any]) -> str:
    checks = case.get("process_checks") or {}
    coverage = case.get("evidence_coverage") or {}
    diagnostics = case.get("diagnostics") or {}
    failed = [
        key
        for key in (
            "evidence_coverage_passed",
            "plan_passed",
            "tool_names_passed",
            "forbidden_tools_passed",
            "subagent_types_passed",
            "delegation_count_passed",
            "parallel_delegation_passed",
            "ratio_passed",
        )
        if key in checks and not bool(checks[key])
    ]
    final_checks = case.get("final_checks") or []
    reasoning = final_checks[0].get("reasoning") if final_checks else ""
    error_text = str(diagnostics.get("error") or "")
    failed_note = f'<div class="failed-checks">未过契约: {_esc(", ".join(failed))}</div>' if failed else ""
    if error_text:
        failed_note += f'<div class="failed-checks">执行错误 [{_esc(diagnostics.get("error_type"))}]: {_esc(error_text)}</div>'
    details = (
        f"<details><summary>裁判理由</summary><pre class=\"reason\">{_esc(reasoning)}</pre></details>"
        if reasoning
        else ""
    )
    latency_ms = diagnostics.get("run_latency_ms") or 0.0
    tool_calls = diagnostics.get("total_tool_calls")
    tool_calls_text = "-" if tool_calls is None else str(tool_calls)
    return (
        "<tr>"
        f'<td>{_esc(case.get("case_id"))}</td>'
        f'<td>{_esc(case.get("category"))}</td>'
        f'<td>{_badge(bool(case.get("final_success")))}</td>'
        f'<td>{_badge(bool(case.get("process_success")))}</td>'
        f'<td class="num">{int(coverage.get("count") or 0)}/{int(coverage.get("required_count") or 0)}</td>'
        f'<td class="num">{tool_calls_text}</td>'
        f'<td class="num">{_format_latency(float(latency_ms))}</td>'
        f"<td>{failed_note}{details}</td>"
        "</tr>"
    )


def _category_rows(cases: list[dict[str, Any]]) -> str:
    categories: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        categories.setdefault(str(case.get("category")), []).append(case)
    rows: list[str] = []
    for name in sorted(categories):
        group = categories[name]
        passed = sum(1 for item in group if bool(item.get("completed")))
        failed_ids = [str(item.get("case_id")) for item in group if not bool(item.get("completed"))]
        tip = f"{name}: {passed}/{len(group)} 通过" + (f"; 未过: {', '.join(failed_ids)}" if failed_ids else "")
        rows.append(
            "<tr>"
            f"<td>{_esc(name)}</td>"
            f'<td class="num">{len(group)}</td>'
            f"<td>{_bar(passed, len(group), tip)}</td>"
            f"<td>{_esc(', '.join(failed_ids) or '-')}</td>"
            "</tr>"
        )
    return "".join(rows)


def render_report_html(report: dict[str, Any], *, title: str = "") -> str:
    cases = report.get("cases") or []
    run_config = report.get("run_config") or {}
    latencies = [float((case.get("diagnostics") or {}).get("run_latency_ms") or 0.0) for case in cases]
    tool_calls = [
        int((case.get("diagnostics") or {}).get("total_tool_calls"))
        for case in cases
        if (case.get("diagnostics") or {}).get("total_tool_calls") is not None
    ]
    avg_latency = _mean(latencies)
    avg_tools = _mean([float(value) for value in tool_calls])
    completed = int(report.get("completed_cases") or 0)
    total = int(report.get("total_cases") or 0)

    provenance = " · ".join(
        f"{key}=<code>{_esc(value)}</code>"
        for key, value in run_config.items()
        if value not in (None, "", [])
    )
    remediation = report.get("remediation_area_counts") or {}
    remediation_html = (
        " · ".join(f"{_esc(area)} × {count}" for area, count in sorted(remediation.items()))
        or "无"
    )
    headline = title or "Agent 任务完成度评测基线"
    generated = str(report.get("generated_at_utc") or "")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(headline)}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
<h1>{_esc(headline)}</h1>
<div class="meta">生成时间: {_esc(generated)}</div>
<div class="meta">运行溯源: {provenance or "-"}</div>
<div class="meta">fixture: <code>{_esc(report.get("fixture_path"))}</code> · 用例 {total} 条 · 完成 {completed} 条</div>

<h2>聚合指标</h2>
<div class="tiles">
{_tile("完成率 (结果+过程)", _pct(report.get("completion_rate")), f"{completed}/{total} 用例")}
{_tile("结果层 · 裁判通过率", _pct(report.get("final_success_rate")))}
{_tile("过程层 · 契约通过率", _pct(report.get("process_success_rate")))}
{_tile("证据覆盖通过率", _pct(report.get("evidence_coverage_rate")))}
{_tile("计划执行完成度均值", _pct(report.get("average_execution_completion_ratio")))}
{_tile("效率层 · 平均时延", _format_latency(avg_latency) if avg_latency is not None else "-")}
{_tile("效率层 · 平均工具调用", f"{avg_tools:.1f}" if avg_tools is not None else "-", "次/用例")}
</div>

<h2>分类通过情况</h2>
<table>
<thead><tr><th>分类</th><th class="num">用例数</th><th>完成比例</th><th>未过用例</th></tr></thead>
<tbody>{_category_rows(cases)}</tbody>
</table>

<h2>改进方向归因</h2>
<div class="meta">{remediation_html}</div>

<h2>逐用例明细</h2>
<table>
<thead><tr><th>用例</th><th>分类</th><th>结果层</th><th>过程层</th><th class="num">证据</th><th class="num">工具调用</th><th class="num">时延</th><th>裁判与契约</th></tr></thead>
<tbody>{''.join(_case_row(case) for case in cases)}</tbody>
</table>
</div>
</body>
</html>
"""


def _default_output(report_path: Path) -> Path:
    return report_path.with_suffix(".html")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an eval baseline JSON as a self-contained HTML report.")
    parser.add_argument("report", type=Path, help="Path to the baseline JSON report.")
    parser.add_argument("--output", type=Path, default=None, help="Output HTML path (default: beside the JSON).")
    parser.add_argument("--title", default="", help="Optional report title override.")
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    title = args.title.strip() or (
        "Agent 任务完成度评测基线"
        f" · {str((report.get('run_config') or {}).get('runner_mode') or 'eval')}"
    )
    output = args.output or _default_output(args.report)
    output.write_text(render_report_html(report, title=title), encoding="utf-8")
    print(f"report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
