"""Trace middleware for tracking agent execution phases."""

import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.runtime import Runtime

from .types import AgentState


class TraceMiddleware(AgentMiddleware):
    """Middleware that emits trace events during agent execution."""

    def before_model(  # type: ignore[override]
        self, state: AgentState, runtime: Runtime, config: RunnableConfig | None = None
    ) -> dict[str, Any] | None:
        """Keep model invocations out of the public execution timeline.

        Provider-side deliberation is not an auditable user-facing action. Tool,
        plan, and delegation events are emitted by ``wrap_tool_call`` instead.
        """
        return None

    def after_model(  # type: ignore[override]
        self, state: AgentState, runtime: Runtime, config: RunnableConfig | None = None
    ) -> dict[str, Any] | None:
        """Do not expose a model response as reasoning or progress."""
        return None

    def wrap_tool_call(self, request: ToolCallRequest, handler: Any) -> Any:
        """Emit observable lifecycle events around each actual tool execution."""
        tool_call = request.tool_call
        tool_name = str(tool_call.get("name") or "unknown")
        tool_call_id = str(tool_call.get("id") or request.runtime.tool_call_id or "")
        arguments = tool_call.get("args") if isinstance(tool_call.get("args"), dict) else {}
        on_event = request.runtime.config.get("configurable", {}).get("on_event")
        started_at = time.perf_counter()
        self._emit_tool_event(
            on_event,
            "tool_call",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            arguments=arguments,
        )
        try:
            result = handler(request)
        except Exception as exc:
            self._emit_tool_event(
                on_event,
                "tool_result",
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                arguments=arguments,
                summary=str(exc),
                status="failed",
                duration_ms=(time.perf_counter() - started_at) * 1000,
            )
            raise
        self._emit_tool_event(
            on_event,
            "tool_result",
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            arguments=arguments,
            summary=str(getattr(result, "content", "")),
            status=str(getattr(result, "status", "success")),
            duration_ms=(time.perf_counter() - started_at) * 1000,
        )
        return result

    @staticmethod
    def _emit_tool_event(
        on_event: Any,
        performative: str,
        *,
        tool_name: str,
        tool_call_id: str,
        arguments: dict[str, Any],
        summary: str = "",
        status: str = "",
        duration_ms: float | None = None,
    ) -> None:
        if not callable(on_event):
            return
        on_event(
            {
                "sender": "agent" if performative == "tool_call" else tool_name,
                "receiver": tool_name if performative == "tool_call" else "agent",
                "performative": performative,
                "content": summary,
                "metadata": {
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "arguments": arguments,
                    "summary": summary,
                    "status": status,
                    "duration_ms": duration_ms,
                },
            }
        )

    def after_agent(  # type: ignore[override]
        self, state: AgentState, runtime: Runtime, config: RunnableConfig | None = None
    ) -> dict[str, Any] | None:
        """The durable run itself emits the terminal event."""
        return None
