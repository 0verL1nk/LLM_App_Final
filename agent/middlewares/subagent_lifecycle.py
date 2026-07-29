"""Real-time lifecycle events for ephemeral Deep Agents subagents."""

import json
import time
from contextvars import ContextVar

from langchain.agents.middleware import AgentMiddleware
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

from .types import AgentState

_started_at: ContextVar[float | None] = ContextVar("subagent_started_at", default=None)


class SubagentLifecycleMiddleware(AgentMiddleware):
    def __init__(self, role: str) -> None:
        super().__init__()
        self.role = role

    def before_agent(
        self, state: AgentState, runtime: Runtime, config: RunnableConfig | None = None
    ) -> None:
        started = time.time()
        _started_at.set(started)
        self._emit(config, "subagent_start", state, started_at_ms=started * 1000.0)

    def after_agent(
        self, state: AgentState, runtime: Runtime, config: RunnableConfig | None = None
    ) -> None:
        completed = time.time()
        started = _started_at.get()
        self._emit(
            config,
            "subagent_complete",
            state,
            started_at_ms=(started * 1000.0 if started is not None else None),
            completed_at_ms=completed * 1000.0,
            duration_ms=((completed - started) * 1000.0 if started is not None else None),
        )

    def _emit(
        self,
        config: RunnableConfig | None,
        performative: str,
        state: AgentState,
        **timing: float | None,
    ) -> None:
        configurable = config.get("configurable", {}) if config else {}
        on_event = configurable.get("on_event")
        if not callable(on_event):
            return
        messages = state.get("messages", [])
        description = str(getattr(messages[0], "content", "") or "") if messages else ""
        on_event(
            {
                "sender": self.role,
                "receiver": "leader",
                "performative": performative,
                "content": json.dumps(
                    {"role": self.role, "description": description, **timing},
                    ensure_ascii=False,
                ),
            }
        )


__all__ = ["SubagentLifecycleMiddleware"]
