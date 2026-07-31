"""Dynamic per-turn system context injection."""

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

from .system_message import append_system_instruction
from .types import AgentState


class TurnContextMiddleware(AgentMiddleware):
    """Merge structured per-turn context into the provider system message."""

    state_schema = AgentState

    def before_model(  # type: ignore[override]
        self,
        state: AgentState,
        runtime: Runtime,
        config: RunnableConfig | None = None,
    ) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return {"turn_system_context": ""}

        last_msg = messages[-1]
        if not hasattr(last_msg, "type") or last_msg.type != "human":
            return None

        configurable = config.get("configurable", {}) if config else {}
        turn_context = configurable.get("turn_context")
        system_content = self._build_system_content(turn_context)
        return {"turn_system_context": system_content}

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        """Keep dynamic instructions out of conversation history."""
        state = request.state or {}
        instruction = str(state.get("turn_system_context") or "").strip()
        system_message = append_system_instruction(request.system_message, instruction)
        return handler(request.override(system_message=system_message))

    @staticmethod
    def _build_system_content(turn_context: Any) -> str:
        if not isinstance(turn_context, dict):
            return ""

        lines: list[str] = []
        response_language = str(turn_context.get("response_language") or "").strip().lower()
        if response_language == "en":
            lines.append("If the user does not explicitly request another language, answer in English.")
        elif response_language == "zh":
            lines.append("如果用户没有明确要求其他语言，请使用中文回答。")

        memory_items = turn_context.get("memory_items")
        if isinstance(memory_items, list):
            memory_lines: list[str] = []
            for item in memory_items:
                if not isinstance(item, dict):
                    continue
                memory_type = str(item.get("memory_type") or "episodic").strip().lower() or "episodic"
                content = " ".join(str(item.get("content") or "").split()).strip()
                if not content:
                    continue
                memory_lines.append(f"- ({memory_type}) {content}")
            if memory_lines:
                lines.append("Semantically retrieved long-term memory candidates:")
                lines.extend(memory_lines)
                lines.append(
                    "Use a candidate only when it is directly relevant. If it conflicts with the current request or current evidence, ignore it and prefer the current information."
                )

        return "\n".join(lines).strip()


turn_context_middleware = TurnContextMiddleware()

__all__ = ["TurnContextMiddleware", "turn_context_middleware"]
