import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from agent.application.turn_engine import execute_turn_core
from agent.archive import list_agent_outputs, save_agent_output
from agent.llm_provider import build_openai_compatible_chat_model
from agent.profiles import paper_leader_profile
from agent.session_factory import (
    AgentDependencies,
    AgentRuntimeOptions,
    AgentSession,
    create_agent_session,
)
from agent.stream import iter_agent_response_deltas
from utils.utils import extract_json_string


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _build_live_llm(
    live_config: dict[str, str],
    *,
    enable_thinking: bool | None = None,
    reasoning_effort: str | None = None,
):
    return build_openai_compatible_chat_model(
        api_key=live_config["OPENAI_API_KEY"],
        model_name=live_config["OPENAI_MODEL_NAME"],
        base_url=live_config["OPENAI_BASE_URL"],
        temperature=0,
        enable_thinking=enable_thinking,
        reasoning_effort=reasoning_effort,
    )


def _doc_search(_query: str) -> str:
    return (
        "文档记录：代号是 ORBIT-427。"
        "方法A在精度方面更好，方法B在速度方面更快。"
    )


def _collect_answer(session, prompt: str) -> str:
    return "".join(
        iter_agent_response_deltas(
            session.agent,
            [{"role": "user", "content": prompt}],
            config=session.runtime_config,
        )
    ).strip()


def _parse_first_json_object(text: str) -> dict:
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("No valid JSON object found in model output")


def _result_has_tool_call(result: dict, tool_name: str) -> bool:
    raw_messages = result.get("messages", []) if isinstance(result, dict) else []
    if not isinstance(raw_messages, list):
        return False
    for message in raw_messages:
        tool_calls = getattr(message, "tool_calls", None)
        if not isinstance(tool_calls, list):
            continue
        for call in tool_calls:
            if isinstance(call, dict):
                name = str(call.get("name") or "").strip()
            else:
                name = str(getattr(call, "name", "") or "").strip()
            if name == tool_name:
                return True
    return False


def _create_session(llm: Any) -> AgentSession:
    return create_agent_session(
        profile=paper_leader_profile,
        deps=AgentDependencies(search_document_fn=_doc_search),
        options=AgentRuntimeOptions(llm=llm),
    )


@pytest.fixture(scope="module")
def live_config() -> dict[str, str]:
    _load_env_file(Path(".env"))
    enabled = os.getenv("RUN_LIVE_E2E", "0").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        pytest.skip("Live E2E disabled. Set RUN_LIVE_E2E=1 in .env")

    required_keys = ["OPENAI_BASE_URL", "OPENAI_MODEL_NAME", "OPENAI_API_KEY"]
    values: dict[str, str] = {}
    missing: list[str] = []
    for key in required_keys:
        value = os.getenv(key, "").strip()
        if not value:
            missing.append(key)
        else:
            values[key] = value

    if missing:
        pytest.skip(f"Live E2E config incomplete, missing: {', '.join(missing)}")
    return values


def test_live_model_roundtrip(live_config: dict[str, str]) -> None:
    llm = _build_live_llm(live_config)
    result = llm.invoke("请只回复 LIVE_OK")
    content = result.content if isinstance(result.content, str) else str(result.content)
    assert "LIVE_OK" in content.upper()


def test_live_model_roundtrip_with_thinking_toggle(
    live_config: dict[str, str],
) -> None:
    llm = _build_live_llm(
        live_config,
        enable_thinking=True,
        reasoning_effort=os.getenv("AGENT_REASONING_EFFORT", "medium"),
    )
    result = llm.invoke("请只回复 THINK_OK")
    content = result.content if isinstance(result.content, str) else str(result.content)
    assert "THINK_OK" in content.upper()


def test_live_agent_roundtrip(live_config: dict[str, str]) -> None:
    session = _create_session(_build_live_llm(live_config))
    answer = _collect_answer(session, "请告诉我文档里的代号是什么？只返回代号")
    assert answer
    assert "427" in answer


def test_live_turn_engine_reports_runtime_policy(live_config: dict[str, str]) -> None:
    llm = _build_live_llm(live_config)
    session = _create_session(llm)
    events: list[dict] = []

    result = execute_turn_core(
        prompt="请比较方法A和方法B的优缺点，并给出 trade-off 建议。",
        leader_agent=session.agent,
        leader_runtime_config=session.runtime_config,
        on_event=lambda item: events.append(dict(item)),
    )

    assert result["answer"]
    assert result["policy_decision"]["source"] == "runtime"


def test_live_mindmap_and_archive_roundtrip(
    live_config: dict[str, str], tmp_path: Path
) -> None:
    session = _create_session(_build_live_llm(live_config))
    prompt = (
        "请基于文档生成思维导图，严格只输出 JSON 对象。"
        '格式必须为 {"name":"主题","children":[{"name":"子主题","children":[...]}]}，'
        "不要 markdown，不要解释。"
    )
    answer = _collect_answer(session, prompt)
    parsed = _parse_first_json_object(extract_json_string(answer))
    assert isinstance(parsed, dict)
    assert "name" in parsed
    assert isinstance(parsed.get("children"), list)

    db_path = tmp_path / "live_e2e_archive.sqlite"
    user_uuid = f"live-{uuid4().hex}"
    doc_uid = f"doc-{uuid4().hex}"
    save_agent_output(
        uuid=user_uuid,
        doc_uid=doc_uid,
        doc_name="live-e2e-paper.pdf",
        output_type="mindmap",
        content=json.dumps(parsed, ensure_ascii=False),
        db_name=str(db_path),
    )
    records = list_agent_outputs(uuid=user_uuid, doc_uid=doc_uid, db_name=str(db_path))
    assert records
    assert records[0]["output_type"] == "mindmap"


def test_live_agent_auto_calls_mindmap_skill(live_config: dict[str, str]) -> None:
    session = _create_session(_build_live_llm(live_config))
    result = session.agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "请根据当前文档生成思维导图。先自行选择并调用合适的 skill，再输出严格 JSON。"
                    ),
                }
            ]
        },
        config=session.runtime_config,
    )

    assert isinstance(result, dict)
    assert _result_has_tool_call(result, "use_skill")
