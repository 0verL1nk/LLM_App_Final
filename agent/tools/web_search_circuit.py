"""Circuit breaker for web search providers.

Consecutive failures open a cooling window that doubles per trip (capped),
with half-open probing on expiry; the chain skips cooling providers quietly.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# Provider circuit breaker: consecutive failures open a cooling window that
# doubles per trip (capped), with half-open probing on expiry. Env-overridable.
PROVIDER_CIRCUIT_FAILURE_THRESHOLD = 3
PROVIDER_CIRCUIT_COOLDOWN_SECONDS = 60.0
PROVIDER_CIRCUIT_MAX_COOLDOWN_SECONDS = 600.0


class _ProviderCoolingDownError(RuntimeError):
    """Internal signal: the provider is skipped because its circuit is open."""


class _CircuitBreakerProvider:
    """Wrap a web search provider so repeated failures stop hammering it."""

    def __init__(self, name: str, client: Any) -> None:
        self.name = name
        self._client = client
        self._threshold = int(
            os.getenv("AGENT_WEB_CIRCUIT_THRESHOLD", str(PROVIDER_CIRCUIT_FAILURE_THRESHOLD))
        )
        self._cooldown_seconds = float(
            os.getenv(
                "AGENT_WEB_CIRCUIT_COOLDOWN_SECONDS",
                str(PROVIDER_CIRCUIT_COOLDOWN_SECONDS),
            )
        )
        self._max_cooldown = float(
            os.getenv(
                "AGENT_WEB_CIRCUIT_MAX_COOLDOWN_SECONDS",
                str(PROVIDER_CIRCUIT_MAX_COOLDOWN_SECONDS),
            )
        )
        self._consecutive_failures = 0
        self._cooldown_until = 0.0

    def run(self, query: str) -> str:
        if time.monotonic() < self._cooldown_until:
            raise _ProviderCoolingDownError(f"{self.name} cooling down")
        was_open = self._consecutive_failures >= self._threshold
        try:
            result = self._client.run(query)
        except Exception as exc:
            self._record_failure()
            raise exc
        if was_open:
            logger.info("tool.search_web provider recovered: %s", self.name)
        self._consecutive_failures = 0
        self._cooldown_seconds = float(
            os.getenv(
                "AGENT_WEB_CIRCUIT_COOLDOWN_SECONDS",
                str(PROVIDER_CIRCUIT_COOLDOWN_SECONDS),
            )
        )
        return result

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._threshold:
            self._cooldown_until = time.monotonic() + self._cooldown_seconds
            logger.warning(
                "tool.search_web provider circuit opened: %s cooling down for %.0fs "
                "after %d consecutive failures",
                self.name,
                self._cooldown_seconds,
                self._consecutive_failures,
            )
            self._cooldown_seconds = min(self._cooldown_seconds * 2, self._max_cooldown)
