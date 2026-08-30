"""Regenerate docs/generated/db-schema.md from agent/adapters/orm/models.py.

Loads the SQLAlchemy Core table contracts directly from their module file (no
import-path mutation; ``sys.path.insert`` is prohibited outside tests by
scripts/repository_guard.py) and renders one markdown section per table:
name, purpose, columns with types and key flags, unique constraints, indexes.

Table purposes come from the table's SQL ``comment`` when present, otherwise
from ``TABLE_PURPOSES`` below. An unknown table is a hard error so a new table
cannot land without a documented purpose; a stale registry entry is also an
error so the registry cannot rot.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODELS_PATH = ROOT / "agent" / "adapters" / "orm" / "models.py"
OUTPUT_PATH = ROOT / "docs" / "generated" / "db-schema.md"

HEADER_LINES = (
    "# 数据库 Schema（生成物）",
    "",
    "> 本文件由 `scripts/generate_db_schema.py` 从 `agent/adapters/orm/models.py` 生成，"
    "禁止手改；改表后运行 `make db-schema` 再生成。",
    "",
    "覆盖范围：durable 运行时的 SQLAlchemy Core 表（Alembic 管理迁移，见"
    " `docs/architecture/orm-persistence.md`）。遗留 `sqlite3` 层的表"
    "（`memory_events`、`memory_items`，见 `agent/memory/repository.py`）不在本表内，"
    "其收敛状态见 `docs/exec-plans/tech-debt-tracker.md` 条目 a。",
    "",
)

# One-line purpose per table, keyed by the SQL table name. Keep in sync with
# models.py; the script fails closed on either side drifting.
TABLE_PURPOSES: dict[str, str] = {
    "agent_runs": "Run 是一次用户命令的持久载体：状态、请求/解析执行模式与路由理由；"
    "(uuid, client_request_id) 唯一约束提供提交幂等。",
    "agent_run_events": "Run 的有序事件日志（canonical 真相）：(run_uid, sequence) 唯一，"
    "页面重放与投影重建都从它恢复。",
    "agent_run_items": "事件的查询投影：assistant 消息与 V2 工作项（agent_task、"
    "human_request 等），供页面与检查器直接读取。",
    "agent_tasks": "通用可调度任务（kind 开放注册）：父子关系、状态机、幂等键与"
    " continuation epoch；不绑定 research 语义。",
    "agent_task_attempts": "worker 执行尝试：lease_expires_at 租约与 heartbeat 是唯一"
    "执行权凭据，attempt 编号唯一约束支撑重试历史。",
    "agent_task_outbox": "任务事件发件箱：与任务状态同事务写入，available_at/租约状态"
    "驱动可靠投递与重复发布拒绝。",
    "research_artifacts": "任务产物（EvidencePacket、evidence_merge 等）：内容、证据引用"
    "与 task 溯源；task_uid 唯一，崩溃后由对账补写。",
    "research_plans": "Run 级执行计划快照：revision 比较交换整体替换，不产生计划历史表。",
    "research_plan_steps": "计划步骤：依赖、泳道与任务链接；被链接任务的认领/终态在同一"
    "数据库事务内更新步骤状态。",
    "agent_steering_inputs": "运行中用户追加输入队列：仅工具边界后投递、模型调用成功才"
    "确认，未确认投递可重放。",
    "context_memory_items": "governed 上下文记忆（L2 会话/L3 项目/L4 用户分层）：scope"
    " 复合索引按 uuid+project+level 检索，条目带版本与过期时间。",
    "session_context_summaries": "会话压缩摘要：每会话一行、版本递增，恢复会话时注入"
    "上下文骨架。",
}


def load_models_module() -> ModuleType:
    """Import models.py by explicit file location without touching sys.path."""
    spec = importlib.util.spec_from_file_location("papersage_orm_models", MODELS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module spec from {MODELS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _column_flags(column: Any) -> str:
    """Render the constraint flags worth showing in a schema overview."""
    flags: list[str] = []
    if column.primary_key:
        flags.append("PK")
    for foreign_key in column.foreign_keys:
        flags.append(f"FK→{foreign_key.target_fullname}")
    if not column.nullable and not column.primary_key:
        flags.append("NOT NULL")
    if column.server_default is not None and not column.primary_key:
        flags.append(f"default {str(column.server_default.arg)!r}")
    return ", ".join(flags)


def _render_table(table: Any) -> list[str]:
    purpose = table.comment if table.comment else TABLE_PURPOSES.get(table.name)
    if purpose is None:
        raise KeyError(
            f"Table '{table.name}' has no comment and no TABLE_PURPOSES entry; "
            "document it in scripts/generate_db_schema.py before regenerating."
        )
    lines = [f"## {table.name}", "", purpose, "", "| 列 | 类型 | 约束 |", "|---|---|---|"]
    for column in table.columns:
        flags = _column_flags(column)
        lines.append(f"| {column.name} | {column.type} | {flags} |")
    constraint_names = [
        f"({', '.join(constraint.columns.keys())}) 唯一"
        for constraint in table.constraints
        if constraint.__visit_name__ == "unique_constraint"
    ]
    index_names = [f"{index.name}({', '.join(index.columns.keys())})" for index in table.indexes]
    extras = constraint_names + index_names
    if extras:
        lines += ["", "索引/唯一约束：" + "、".join(extras)]
    lines += [""]
    return lines


def render_schema_markdown(metadata: Any) -> str:
    """Render every table in deterministic (dependency-sorted) order."""
    table_names = {table.name for table in metadata.tables.values()}
    stale = sorted(set(TABLE_PURPOSES) - table_names)
    if stale:
        raise KeyError(
            f"TABLE_PURPOSES references unknown tables {stale}; "
            "remove entries for dropped tables before regenerating."
        )
    lines = list(HEADER_LINES)
    for table in metadata.sorted_tables:
        lines.extend(_render_table(table))
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    if not MODELS_PATH.is_file():
        print(f"Models file not found: {MODELS_PATH}", file=sys.stderr)
        return 1
    module = load_models_module()
    markdown = render_schema_markdown(module.metadata)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(markdown, encoding="utf-8")
    table_count = len(module.metadata.tables)
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT).as_posix()} ({table_count} tables).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
