"""Inject durable user follow-ups at safe tool-to-model boundaries."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

from ..application.steering_inputs import (
    claim_steering_inputs_for_model,
    confirm_steering_inputs_for_model,
)
from .types import AgentState


class SteeringInputMiddleware(AgentMiddleware):
    """Deliver queued follow-ups only after a tool has produced its result."""

    state_schema = AgentState

    def before_model(  # type: ignore[override]
        self, state: AgentState, runtime: Runtime, config: RunnableConfig | None = None
    ) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        configurable = config.get("configurable", {}) if config else {}
        initial_delivery = bool(configurable.get("steering_initial_delivery"))
        if not messages or (
            getattr(messages[-1], "type", "") != "tool" and not initial_delivery
        ):
            return {"steering_inputs_for_model": []}
        run_uid = str(configurable.get("run_uid") or "").strip()
        if not run_uid:
            return {"steering_inputs_for_model": []}
        inputs = claim_steering_inputs_for_model(
            run_uid=run_uid,
            db_name=str(configurable.get("steering_db_name") or "./database.sqlite"),
        )
        if not inputs:
            return {"steering_inputs_for_model": []}
        return {
            "messages": [HumanMessage(content=str(item["text"])) for item in inputs],
            "steering_inputs_for_model": inputs,
        }

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        state = request.state or {}
        inputs = state.get("steering_inputs_for_model")
        if not isinstance(inputs, list) or not inputs:
            return handler(request)
        runtime = request.runtime
        configurable = getattr(runtime, "config", {}).get("configurable", {}) if runtime else {}
        run_uid = str(configurable.get("run_uid") or "").strip()
        if not run_uid:
            return handler(request)
        response = handler(request)
        confirm_steering_inputs_for_model(
            run_uid=run_uid,
            inputs=[item for item in inputs if isinstance(item, dict)],
            db_name=str(configurable.get("steering_db_name") or "./database.sqlite"),
        )
        return response

    def after_model(  # type: ignore[override]
        self, state: AgentState, runtime: Runtime, config: RunnableConfig | None = None
    ) -> dict[str, Any]:
        """Do not let an already confirmed batch leak into a later model call."""
        return {"steering_inputs_for_model": []}


steering_input_middleware = SteeringInputMiddleware()

__all__ = ["SteeringInputMiddleware", "steering_input_middleware"]
