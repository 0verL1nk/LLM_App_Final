from typing import Any

from langchain.agents import create_agent


def create_runtime_agent(
    *,
    model: Any,
    system_prompt: str,
    tools: list[Any],
    middleware: list[Any] | None = None,
    checkpointer: Any | None = None,
) -> Any:
    create_kwargs: dict[str, Any] = {
        "model": model,
        "tools": list(tools),
        "system_prompt": system_prompt,
    }
    if checkpointer is not None:
        create_kwargs["checkpointer"] = checkpointer
    if middleware:
        create_kwargs["middleware"] = middleware
    return create_agent(**create_kwargs)
