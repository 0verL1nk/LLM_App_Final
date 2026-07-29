from typing import Any, Protocol


class AgentInvoker(Protocol):
    def invoke(
        self,
        payload: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> Any: ...


class EvidenceRetriever(Protocol):
    def __call__(self, query: str) -> dict[str, Any]: ...
