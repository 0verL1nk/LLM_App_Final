from pathlib import Path

from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.adapters.orm.run_repository import create_run, list_run_items, update_run_status
from agent.application.steering_inputs import (
    move_unconfirmed_inputs_to_followup,
    queue_steering_input,
)
from agent.middlewares.steering_input import SteeringInputMiddleware


def _running_run(database: str) -> dict[str, object]:
    run, _ = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="request-001",
        prompt="初始问题",
        db_name=database,
    )
    assert update_run_status(run_uid=str(run["run_uid"]), status="running", db_name=database)
    return run


def test_steering_inputs_are_idempotent_and_projected(tmp_path: Path) -> None:
    database = str(tmp_path / "steering.sqlite")
    run = _running_run(database)
    kwargs = {
        "project_uid": "project-1",
        "session_uid": "session-1",
        "user_uuid": "user-1",
        "client_request_id": "follow-up-001",
        "text": "再核验实验设置",
        "db_name": database,
    }

    first, created = queue_steering_input(**kwargs)
    duplicate, duplicate_created = queue_steering_input(**kwargs)

    assert created is True
    assert duplicate_created is False
    assert duplicate["input_uid"] == first["input_uid"]
    assert first["run_uid"] == run["run_uid"]
    assert list_run_items(run_uid=str(run["run_uid"]), db_name=database) == [
        {
            "id": f"item_steering_input_{run['run_uid']}_{first['input_uid']}",
            "taskId": None,
            "type": "human_request",
            "status": "in_progress",
            "payload": {"inputId": first["input_uid"], "text": "再核验实验设置", "state": "queued"},
            "createdAt": list_run_items(run_uid=str(run["run_uid"]), db_name=database)[0]["createdAt"],
            "updatedAt": list_run_items(run_uid=str(run["run_uid"]), db_name=database)[0]["updatedAt"],
        }
    ]


def test_middleware_batches_inputs_only_after_a_tool_and_confirms_on_success(tmp_path: Path) -> None:
    database = str(tmp_path / "steering.sqlite")
    run = _running_run(database)
    for index, text in enumerate(["限定 2024 年以后", "比较基线方法"], start=1):
        queue_steering_input(
            project_uid="project-1",
            session_uid="session-1",
            user_uuid="user-1",
            client_request_id=f"follow-up-{index:03d}",
            text=text,
            db_name=database,
        )
    middleware = SteeringInputMiddleware()
    config = {"configurable": {"run_uid": run["run_uid"], "steering_db_name": database}}

    assert middleware.before_model(
        {"messages": [HumanMessage(content="初始问题")]}, None, config
    ) == {"steering_inputs_for_model": []}
    update = middleware.before_model(
        {"messages": [ToolMessage(content="检索完成", tool_call_id="tool-1")]}, None, config
    )
    assert update is not None
    assert [message.content for message in update["messages"]] == ["限定 2024 年以后", "比较基线方法"]

    request = ModelRequest(
        model="llm",  # type: ignore[arg-type]
        messages=update["messages"],
        system_message=None,
        state={**update, "messages": update["messages"]},
        runtime=type("Runtime", (), {"config": config})(),
    )
    response = middleware.wrap_model_call(request, lambda _request: ModelResponse(result=[AIMessage(content="继续")]))

    assert isinstance(response, ModelResponse)
    items = list_run_items(run_uid=str(run["run_uid"]), db_name=database)
    assert [item["status"] for item in items] == ["completed", "completed"]


def test_unconfirmed_claim_is_replayed_after_worker_interruption(tmp_path: Path) -> None:
    database = str(tmp_path / "steering.sqlite")
    run = _running_run(database)
    queue_steering_input(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="follow-up-001",
        text="补充约束",
        db_name=database,
    )
    middleware = SteeringInputMiddleware()
    config = {"configurable": {"run_uid": run["run_uid"], "steering_db_name": database}}
    state = {"messages": [ToolMessage(content="检索完成", tool_call_id="tool-1")]}

    first = middleware.before_model(state, None, config)
    replay = middleware.before_model(state, None, config)

    assert first is not None and replay is not None
    assert [message.content for message in replay["messages"]] == ["补充约束"]


def test_terminal_run_forwards_unconfirmed_inputs_to_a_new_initial_model_boundary(tmp_path: Path) -> None:
    database = str(tmp_path / "steering.sqlite")
    source = _running_run(database)
    queued, _ = queue_steering_input(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="follow-up-001",
        text="只比较公开数据集",
        db_name=database,
    )
    assert update_run_status(run_uid=str(source["run_uid"]), status="completed", db_name=database)
    target, _ = create_run(
        project_uid="project-1",
        session_uid="session-1",
        user_uuid="user-1",
        client_request_id="steering-followup-run-1",
        prompt="继续处理补充要求",
        db_name=database,
    )

    moved = move_unconfirmed_inputs_to_followup(
        source_run_uid=str(source["run_uid"]), target_run_uid=str(target["run_uid"]), db_name=database
    )

    assert [item["input_uid"] for item in moved] == [queued["input_uid"]]
    source_item = list_run_items(run_uid=str(source["run_uid"]), db_name=database)[0]
    target_item = list_run_items(run_uid=str(target["run_uid"]), db_name=database)[0]
    assert source_item["payload"]["state"] == "forwarded"
    assert target_item["payload"]["state"] == "queued"
    middleware = SteeringInputMiddleware()
    update = middleware.before_model(
        {"messages": [HumanMessage(content="继续处理补充要求")]},
        None,
        {"configurable": {"run_uid": target["run_uid"], "steering_db_name": database, "steering_initial_delivery": True}},
    )
    assert update is not None
    assert [message.content for message in update["messages"]] == ["只比较公开数据集"]
