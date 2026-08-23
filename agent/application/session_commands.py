"""Slash command use cases for research sessions (/skills, /compact).

Commands execute without an agent run; their results persist as ordinary
session messages so the workspace transcript stays the single source of truth.
"""

from __future__ import annotations

import logging
from typing import Any

from ..adapters.orm.memory_repository import list_memory_items
from ..adapters.orm.run_repository import list_session_runs
from ..adapters.sqlite.project_repository import (
    list_project_files,
    list_project_session_messages,
    list_project_sessions,
    save_project_session_messages,
)
from ..adapters.sqlite.rag_ingestion_repository import list_project_ingestions
from ..adapters.user_settings import (
    read_api_key_for_user,
    read_base_url_for_user,
    read_model_name_for_user,
)
from ..context_governance import build_context_usage_snapshot, estimate_message_tokens
from ..llm_provider import build_openai_compatible_chat_model
from ..skills.loader import discover_available_skills
from .workspace import require_project

logger = logging.getLogger(__name__)

# Manual compact mirrors the runtime's SummarizationMiddleware spirit: replace
# older history with one summary and keep the tail verbatim.
COMPACT_MIN_MESSAGES = 10
COMPACT_KEEP_RECENT_MESSAGES = 6
SUMMARY_MAX_CHARS = 600

_SUMMARY_SYSTEM_PROMPT = (
    "你是对话压缩助手。请把下面的对话历史压缩成一份忠实、信息密集的摘要，"
    "保留：研究目标、已确认的结论、关键证据与出处、未决问题、用户偏好。"
    f"直接输出摘要正文，不要任何前言或解释。用中文，不超过 {SUMMARY_MAX_CHARS} 字。"
)

_ROLE_LABELS = {"user": "用户", "assistant": "助手"}

# Command surface reference: keep in sync with web/src/lib/slash-commands.ts.
HELP_TEXT = "\n".join(
    [
        "可用命令：",
        "",
        "- `/skills` — 列出可用技能及其用途",
        "- `/技能名 任务` — 显式调用指定技能，例如 `/summary 总结这篇论文`",
        "- `/compact` — 压缩会话上下文：较早历史归纳为摘要，近期消息保留原文",
        "- `/documents` — 查看项目资料清单与处理状态",
        "- `/memory` — 查看项目记忆与稳定偏好",
        "- `/model` — 查看当前模型配置",
        "- `/new` — 新建一个探索会话并切换过去",
        "- `/rename 新名称` — 重命名当前会话",
        "- `/help` — 显示本帮助",
        "",
        "输入框中键入 `/` 会自动弹出命令列表：↑↓ 选择、Tab 补全、Enter 执行、Esc 关闭。",
    ]
)


class SessionCommandError(ValueError):
    """Client-fixable command problem (unknown command, missing model)."""


class SessionCommandConflict(Exception):
    """Command rejected because the session is busy."""


def list_skill_catalog() -> list[dict[str, str]]:
    """Return the merged user+bundled skill registry sorted by name."""
    skills = sorted(discover_available_skills(), key=lambda item: item.name)
    return [{"name": item.name, "description": item.description} for item in skills]


def format_skills_reply(skills: list[dict[str, str]]) -> str:
    lines = [f"可用技能（{len(skills)} 个）：", ""]
    for skill in skills:
        description = str(skill.get("description") or "").strip() or "（无描述）"
        lines.append(f"- **/{skill['name']}** — {description}")
    lines.extend(
        [
            "",
            "在输入框输入 /技能名 并附上任务即可显式调用，例如：/summary 总结这篇论文的主要贡献。",
        ]
    )
    return "\n".join(lines)


def execute_session_command(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    command: str,
    args: str = "",
) -> dict[str, Any]:
    """Run one slash command against the session and persist its transcript."""
    normalized = str(command or "").strip().lower()
    handlers = {
        "skills": _execute_skills,
        "compact": _execute_compact,
        "help": _execute_help,
        "documents": _execute_documents,
        "memory": _execute_memory,
        "model": _execute_model,
    }
    handler = handlers.get(normalized)
    if handler is None:
        raise SessionCommandError(f"未知命令：/{command or '?'}。输入 /help 查看全部命令。")
    _require_session(project_uid=project_uid, session_uid=session_uid, user_uuid=user_uuid)
    logger.info(
        "session command: user=%s project=%s session=%s command=%s",
        user_uuid, project_uid, session_uid, normalized,
    )
    return handler(project_uid=project_uid, session_uid=session_uid, user_uuid=user_uuid, args=args)


def _require_session(*, project_uid: str, session_uid: str, user_uuid: str) -> None:
    require_project(project_uid=project_uid, user_uuid=user_uuid)
    if not any(
        str(item.get("session_uid") or "") == session_uid
        for item in list_project_sessions(project_uid=project_uid, uuid=user_uuid)
    ):
        raise LookupError("Session not found")


def _append_command_messages(
    *,
    project_uid: str,
    session_uid: str,
    user_uuid: str,
    user_text: str,
    assistant_text: str,
) -> dict[str, str]:
    messages = list_project_session_messages(
        session_uid=session_uid, project_uid=project_uid, uuid=user_uuid
    )
    messages.append({"role": "user", "content": user_text})
    assistant_message = {"role": "assistant", "content": assistant_text}
    messages.append(assistant_message)
    save_project_session_messages(
        session_uid=session_uid, project_uid=project_uid, uuid=user_uuid, messages=messages
    )
    return assistant_message


def _execute_skills(*, project_uid: str, session_uid: str, user_uuid: str, args: str) -> dict[str, Any]:
    message = _append_command_messages(
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid=user_uuid,
        user_text="/skills",
        assistant_text=format_skills_reply(list_skill_catalog()),
    )
    return {"message": message, "stats": None}


def _execute_help(*, project_uid: str, session_uid: str, user_uuid: str, args: str) -> dict[str, Any]:
    message = _append_command_messages(
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid=user_uuid,
        user_text="/help",
        assistant_text=HELP_TEXT,
    )
    return {"message": message, "stats": None}


def _format_ingestion_status(ingestion: dict[str, Any] | None) -> str:
    if not isinstance(ingestion, dict):
        return "未处理"
    status = str(ingestion.get("status") or "").strip()
    stage = str(ingestion.get("stage") or "").strip()
    if not status:
        return "未处理"
    return f"{status}（{stage}）" if stage else status


def _execute_documents(*, project_uid: str, session_uid: str, user_uuid: str, args: str) -> dict[str, Any]:
    documents = list_project_files(project_uid=project_uid, uuid=user_uuid, active_only=False)
    if not documents:
        body = "项目资料库为空：尚未上传资料。上传后可在此查看处理状态。"
    else:
        ingestions = {
            str(item.get("doc_uid") or ""): item
            for item in list_project_ingestions(project_uid=project_uid, uuid=user_uuid)
        }
        lines = [f"项目资料（{len(documents)} 份）：", ""]
        for document in documents:
            name = str(document.get("file_name") or document.get("name") or "未命名")
            availability = "在库" if int(document.get("is_active") or 0) else "已移出"
            status = _format_ingestion_status(ingestions.get(str(document.get("uid") or "")))
            lines.append(f"- {name} — {status} · {availability}")
        body = "\n".join(lines)
    message = _append_command_messages(
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid=user_uuid,
        user_text="/documents",
        assistant_text=body,
    )
    return {"message": message, "stats": None}


def _format_memory_section(title: str, items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return [f"**{title}**：暂无", ""]
    lines = [f"**{title}**（{len(items)} 条）：", ""]
    for item in items:
        entry_title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        prefix = f"- **{entry_title}**：" if entry_title else "- "
        lines.append(f"{prefix}{content}")
    lines.append("")
    return lines


def _execute_memory(*, project_uid: str, session_uid: str, user_uuid: str, args: str) -> dict[str, Any]:
    project_memory = list_memory_items(uuid=user_uuid, project_uid=project_uid, level="L3")
    stable_preferences = list_memory_items(uuid=user_uuid, project_uid=project_uid, level="L4")
    body = "\n".join(
        [
            *_format_memory_section("项目记忆（L3）", project_memory),
            *_format_memory_section("稳定偏好（L4）", stable_preferences),
            "以上内容由系统在对话后整理，可在「详情」面板中编辑或删除。",
        ]
    )
    message = _append_command_messages(
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid=user_uuid,
        user_text="/memory",
        assistant_text=body,
    )
    return {"message": message, "stats": None}


def _execute_model(*, project_uid: str, session_uid: str, user_uuid: str, args: str) -> dict[str, Any]:
    model_name = str(read_model_name_for_user(uuid=user_uuid) or "").strip() or "未配置"
    base_url = str(read_base_url_for_user(uuid=user_uuid) or "").strip() or "默认（OpenAI 官方）"
    api_key_configured = "已配置" if read_api_key_for_user(uuid=user_uuid) else "未配置"
    body = "\n".join(
        [
            "当前模型配置：",
            "",
            f"- 模型：{model_name}",
            f"- 接入点：{base_url}",
            f"- API Key：{api_key_configured}",
            "",
            "可在「设置」页修改模型与密钥。",
        ]
    )
    message = _append_command_messages(
        project_uid=project_uid,
        session_uid=session_uid,
        user_uuid=user_uuid,
        user_text="/model",
        assistant_text=body,
    )
    return {"message": message, "stats": None}


def _execute_compact(*, project_uid: str, session_uid: str, user_uuid: str, args: str) -> dict[str, Any]:
    active_runs = list_session_runs(project_uid=project_uid, session_uid=session_uid, user_uuid=user_uuid)
    if active_runs:
        raise SessionCommandConflict("有进行中的研究运行，请等待其完成后再压缩会话上下文")

    messages = list_project_session_messages(
        session_uid=session_uid, project_uid=project_uid, uuid=user_uuid
    )
    tokens_before = estimate_message_tokens(messages)
    user_text = f"/compact {args}".strip() if str(args or "").strip() else "/compact"

    if len(messages) < COMPACT_MIN_MESSAGES:
        no_op_text = (
            f"当前会话共 {len(messages)} 条消息，尚未达到压缩门槛（≥{COMPACT_MIN_MESSAGES} 条），无需压缩。"
        )
        message = _append_command_messages(
            project_uid=project_uid, session_uid=session_uid, user_uuid=user_uuid,
            user_text=user_text, assistant_text=no_op_text,
        )
        return {
            "message": message,
            "stats": _stats(
                compacted=False,
                messages_before=len(messages),
                messages_after=len(messages) + 2,
                tokens_before=tokens_before,
                messages=list_project_session_messages(
                    session_uid=session_uid, project_uid=project_uid, uuid=user_uuid
                ),
            ),
        }

    api_key = read_api_key_for_user(uuid=user_uuid)
    model_name = read_model_name_for_user(uuid=user_uuid)
    if not api_key or not model_name:
        raise SessionCommandError("Model provider is not configured")

    to_summarize = messages[:-COMPACT_KEEP_RECENT_MESSAGES]
    recent = messages[-COMPACT_KEEP_RECENT_MESSAGES:]
    model = build_openai_compatible_chat_model(
        api_key=api_key,
        model_name=model_name,
        base_url=read_base_url_for_user(uuid=user_uuid),
    )
    summary_text = _invoke_summary(model, _format_transcript(to_summarize))
    summary_message = {
        "role": "assistant",
        "content": f"【会话摘要 · 压缩自 {len(to_summarize)} 条历史消息】\n\n{summary_text}",
    }
    kept_messages = [summary_message, *recent]
    tokens_after_estimate = estimate_message_tokens(kept_messages)
    confirmation = (
        f"已压缩会话上下文：{len(messages)} 条消息压缩为 {len(kept_messages)} 条"
        f"（1 条摘要 + 近期 {len(recent)} 条原文），约 {tokens_before} → {tokens_after_estimate} tokens。"
    )
    final_messages = [
        *kept_messages,
        {"role": "user", "content": user_text},
        {
            "role": "assistant",
            "content": confirmation,
            # The composer's context card reads the newest assistant message;
            # without a fresh snapshot the indicator disappears after compact.
            "context_snapshot": build_context_usage_snapshot(messages=kept_messages),
        },
    ]
    save_project_session_messages(
        session_uid=session_uid, project_uid=project_uid, uuid=user_uuid, messages=final_messages
    )
    return {
        "message": final_messages[-1],
        "stats": _stats(
            compacted=True,
            messages_before=len(messages),
            messages_after=len(final_messages),
            tokens_before=tokens_before,
            messages=final_messages,
        ),
    }


def _stats(
    *,
    compacted: bool,
    messages_before: int,
    messages_after: int,
    tokens_before: int,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "compacted": compacted,
        "messages_before": messages_before,
        "messages_after": messages_after,
        "tokens_before": tokens_before,
        "tokens_after": estimate_message_tokens(messages),
    }


def _format_transcript(messages: list[dict[str, str]]) -> str:
    lines = []
    for message in messages:
        label = _ROLE_LABELS.get(str(message.get("role") or ""), str(message.get("role") or "用户"))
        lines.append(f"{label}：{str(message.get('content') or '')}")
    return "\n\n".join(lines)


def _invoke_summary(model: Any, transcript: str) -> str:
    response = model.invoke(
        [
            {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ]
    )
    content = getattr(response, "content", response)
    return str(content or "").strip()


__all__ = [
    "COMPACT_KEEP_RECENT_MESSAGES",
    "COMPACT_MIN_MESSAGES",
    "SessionCommandConflict",
    "SessionCommandError",
    "execute_session_command",
    "format_skills_reply",
    "list_skill_catalog",
]
