"""Print the durable runtime migration baseline report for one SQLite database.

Usage (from the repository root, so ``agent`` resolves as a package):

    uv run python -m scripts.durable_runtime_baseline --database ./database.sqlite
    uv run python -m scripts.durable_runtime_baseline --database ./db.sqlite --format json

The metrics contract and recorded baseline live in
``docs/architecture/durable-runtime-baseline.md``.
"""

from __future__ import annotations

import argparse
import json

from agent.adapters.orm.baseline_metrics_repository import get_baseline_metrics


def render_markdown(metrics: dict) -> str:
    runs = metrics["runs"]
    tasks = metrics["tasks"]
    lines = [
        f"# Durable runtime baseline - {metrics['database']}",
        "",
        f"- generated_at: {metrics['generated_at']}",
        f"- stalled_after_seconds: {metrics['stalled_after_seconds']}",
        f"- runs: total={runs['total']} status={runs['status_counts']}",
        f"- run_success_rate: {runs['success_rate']}",
        f"- stalled_runs: {runs['stalled']}",
        f"- tasks: total={tasks['total']} status={tasks['status_counts']}",
        f"- delegation_count: {tasks['delegation_count']}",
        f"- events_total: {metrics['events']['total']}",
        f"- duplicate_lifecycle_events: {metrics['events']['duplicate_lifecycle_events']}",
        f"- duplicate_item_terminal_events: {metrics['events']['duplicate_item_terminal_events']}",
        f"- reconnect_recovery: {metrics['reconnect_recovery']}",
        f"- task_latency_ms: {metrics['task_latency_ms']}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="./database.sqlite", help="SQLite database path")
    parser.add_argument("--stalled-after-seconds", type=float, default=300.0)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    metrics = get_baseline_metrics(
        db_name=args.database, stalled_after_seconds=args.stalled_after_seconds
    )
    if args.format == "json":
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
