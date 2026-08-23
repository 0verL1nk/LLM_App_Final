"""Web搜索提供者模块"""
import logging
import os
import re
import time
from typing import Any
from urllib.parse import quote

import httpx
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from .utils import (
    DEFAULT_BRAVE_SEARCH_URL,
    DEFAULT_SEARXNG_INSTANCES,
    DEFAULT_WEB_MAX_RESULTS,
    DEFAULT_WEB_TIMEOUT_SECONDS,
    _env_flag,
    _env_value,
    _format_web_results,
    _is_dangerous_query,
    _load_secret,
    _preview,
    _sanitize_query,
)

logger = logging.getLogger(__name__)


class SearchWebInput(BaseModel):
    query: str = Field(
        description="Supplemental public-web query used only when document evidence is insufficient."
    )


def _parse_searxng_instances() -> list[str]:
    configured = str(os.getenv("AGENT_SEARXNG_BASE_URLS", "") or "").strip()
    if configured.lower() in {"none", "off", "disabled", "false"}:
        # Explicit opt-out: skip SearXNG entirely instead of falling back to
        # the slow public instance pool.
        return []
    if configured:
        items = [item.strip().rstrip("/") for item in configured.split(",")]
        return [item for item in items if item]
    return [item.rstrip("/") for item in DEFAULT_SEARXNG_INSTANCES]


def _build_brave_web_search_client():
    api_key = _load_secret("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return None
    search_url = _env_value("BRAVE_SEARCH_URL", default=DEFAULT_BRAVE_SEARCH_URL)

    class _BraveWebSearch:
        def __init__(self, key: str, url: str):
            self.api_key = key
            self.search_url = url

        def run(self, query: str) -> str:
            response = httpx.get(
                self.search_url,
                params={
                    "q": query,
                    "count": DEFAULT_WEB_MAX_RESULTS,
                },
                headers={
                    "X-Subscription-Token": self.api_key,
                    "Accept": "application/json",
                    "User-Agent": WIKIPEDIA_COMPLIANT_USER_AGENT,
                },
                timeout=DEFAULT_WEB_TIMEOUT_SECONDS,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"brave status={response.status_code}")
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("brave invalid payload")
            web_block = payload.get("web")
            results = web_block.get("results") if isinstance(web_block, dict) else None
            return _format_web_results(
                results,
                title_key="title",
                url_key="url",
                snippet_key="description",
            )

    return _BraveWebSearch(api_key, search_url)


def _build_searxng_web_search_client():
    instances = _parse_searxng_instances()
    if not instances:
        return None

    class _SearxngWebSearch:
        def __init__(self, base_urls: list[str]):
            self.base_urls = base_urls

        def run(self, query: str) -> str:
            last_error = "unknown error"
            for base_url in self.base_urls:
                try:
                    response = httpx.get(
                        f"{base_url}/search",
                        params={
                            "q": query,
                            "format": "json",
                            "safesearch": "1",
                        },
                        headers={"User-Agent": WIKIPEDIA_COMPLIANT_USER_AGENT},
                        timeout=DEFAULT_WEB_TIMEOUT_SECONDS,
                    )
                    if response.status_code >= 400:
                        last_error = f"{base_url} status={response.status_code}"
                        continue
                    payload = response.json()
                    if not isinstance(payload, dict):
                        last_error = f"{base_url} invalid json payload"
                        continue
                    results = payload.get("results")
                    rendered = _format_web_results(
                        results,
                        title_key="title",
                        url_key="url",
                        snippet_key="content",
                    )
                    if rendered != "No web search results found.":
                        return rendered
                    last_error = f"{base_url} no results"
                except Exception as exc:
                    last_error = f"{base_url} {exc}"
                    continue
            raise RuntimeError(f"SearXNG unavailable: {last_error}")

    return _SearxngWebSearch(instances)


def _build_wikipedia_web_search_client():
    class _WikipediaWebSearch:
        def run(self, query: str) -> str:
            response = httpx.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": DEFAULT_WEB_MAX_RESULTS,
                },
                headers={"User-Agent": WIKIPEDIA_COMPLIANT_USER_AGENT},
                timeout=DEFAULT_WEB_TIMEOUT_SECONDS,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"wikipedia status={response.status_code}")
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("wikipedia invalid payload")
            query_block = payload.get("query")
            search_items = query_block.get("search") if isinstance(query_block, dict) else None
            if not isinstance(search_items, list):
                return "No web search results found."
            normalized: list[dict[str, str]] = []
            for item in search_items[:DEFAULT_WEB_MAX_RESULTS]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                snippet = str(item.get("snippet") or "").strip()
                snippet = re.sub(r"<[^>]+>", "", snippet)
                pageid = item.get("pageid")
                if isinstance(pageid, int):
                    url = f"https://en.wikipedia.org/?curid={pageid}"
                else:
                    url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
                normalized.append(
                    {
                        "title": title or "Untitled",
                        "url": url,
                        "content": snippet,
                    }
                )
            return _format_web_results(
                normalized,
                title_key="title",
                url_key="url",
                snippet_key="content",
            )

    return _WikipediaWebSearch()


def _build_native_web_search_client():
    try:
        from duckduckgo_search import DDGS
    except Exception:
        return None

    class _NativeDuckDuckGoSearch:
        def run(self, query: str) -> str:
            with DDGS(timeout=int(DEFAULT_WEB_TIMEOUT_SECONDS)) as client:
                results = client.text(query, max_results=DEFAULT_WEB_MAX_RESULTS)
            return _format_web_results(
                results, title_key="title", url_key="href", snippet_key="body"
            )

    return _NativeDuckDuckGoSearch()


# Firecrawl 429 retry: exponential backoff capped at a short per-wait
# maximum (keyless limits are per time-window; frequent short waits beat
# rare long ones), env-tunable, honoring a server Retry-After within the cap.
FIRECRAWL_RETRY_MAX_ATTEMPTS = 15
FIRECRAWL_RETRY_INITIAL_DELAY_SECONDS = 2.0
FIRECRAWL_RETRY_MAX_DELAY_SECONDS = 10.0
FIRECRAWL_RETRY_MIN_DELAY_SECONDS = 1.0

# Wikimedia's UA policy rejects generic clients with 403; every outbound
# search request carries this descriptive product UA instead.
WIKIPEDIA_COMPLIANT_USER_AGENT = (
    "PaperSage/1.8 (+search_web; local-first research assistant; "
    "https://github.com/0verL1nk/PaperSage)"
)

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


def _build_firecrawl_web_search_client():
    """Firecrawl /v2/search provider.

    Works keyless on the free tier (rate-limited); set FIRECRAWL_API_KEY to
    use an authenticated account. Disable with AGENT_WEB_FIRECRAWL_ENABLED=0.
    """
    if not _env_flag("AGENT_WEB_FIRECRAWL_ENABLED", default=True):
        return None
    api_key = _load_secret("FIRECRAWL_API_KEY")
    search_url = _env_value(
        "AGENT_FIRECRAWL_SEARCH_URL", default="https://api.firecrawl.dev/v2/search"
    )

    class _FirecrawlWebSearch:
        def __init__(self, key: str, url: str):
            self.api_key = key
            self.search_url = url
            self._max_attempts = int(
                os.getenv("AGENT_WEB_FIRECRAWL_RETRIES", str(FIRECRAWL_RETRY_MAX_ATTEMPTS))
            )
            self._max_delay = float(
                os.getenv(
                    "AGENT_WEB_FIRECRAWL_RETRY_MAX_DELAY",
                    str(FIRECRAWL_RETRY_MAX_DELAY_SECONDS),
                )
            )

        def run(self, query: str) -> str:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": WIKIPEDIA_COMPLIANT_USER_AGENT,
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            body = {"query": query, "limit": DEFAULT_WEB_MAX_RESULTS}
            response = None
            for attempt in range(1, self._max_attempts + 1):
                response = httpx.post(
                    self.search_url,
                    json=body,
                    headers=headers,
                    timeout=DEFAULT_WEB_TIMEOUT_SECONDS,
                )
                if response.status_code < 400:
                    break
                if response.status_code != 429:
                    raise RuntimeError(f"firecrawl status={response.status_code}")
                if attempt == self._max_attempts:
                    raise RuntimeError(f"firecrawl status={response.status_code}")
                time.sleep(self._retry_delay(attempt, response, self._max_delay))
            payload = response.json()
            data_block = payload.get("data") if isinstance(payload, dict) else None
            results = data_block.get("web") if isinstance(data_block, dict) else None
            return _format_web_results(
                results,
                title_key="title",
                url_key="url",
                snippet_key="description",
            )

        @staticmethod
        def _retry_delay(attempt: int, response: Any, max_delay: float) -> float:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(FIRECRAWL_RETRY_MIN_DELAY_SECONDS, min(float(retry_after), max_delay))
                except ValueError:
                    pass
            return min(
                FIRECRAWL_RETRY_INITIAL_DELAY_SECONDS * (2 ** (attempt - 1)),
                max_delay,
            )

    return _FirecrawlWebSearch(api_key, search_url)


# Module-level cache for web search clients
_web_search_clients: list[tuple[str, Any]] | None = None


def _ensure_web_search_clients() -> list[tuple[str, Any]]:
    global _web_search_clients
    if _web_search_clients is not None:
        return _web_search_clients

    clients: list[tuple[str, Any]] = []

    brave_client = _build_brave_web_search_client()
    if brave_client is not None:
        clients.append(("brave_search_api", brave_client))
        logger.info("tool.search_web provider initialized: brave_search_api")

    searxng_client = _build_searxng_web_search_client()
    if searxng_client is not None:
        clients.append(("searxng_public_pool", searxng_client))
        logger.info("tool.search_web provider initialized: searxng_public_pool")

    firecrawl_client = _build_firecrawl_web_search_client()
    if firecrawl_client is not None:
        clients.append(("firecrawl_search", firecrawl_client))
        logger.info("tool.search_web provider initialized: firecrawl_search")

    wikipedia_client = _build_wikipedia_web_search_client()
    if wikipedia_client is not None:
        clients.append(("wikipedia_api", wikipedia_client))
        logger.info("tool.search_web provider initialized: wikipedia_api")

    if not clients:
        logger.warning("tool.search_web no primary provider initialized")

    allow_ddg_fallback = _env_flag("AGENT_WEB_ENABLE_DDG_FALLBACK", default=False)
    if allow_ddg_fallback:
        fallback_client = _build_native_web_search_client()
        if fallback_client is not None:
            clients.append(("native_duckduckgo_search", fallback_client))
            logger.info("tool.search_web provider fallback initialized: native_duckduckgo_search")
        else:
            try:
                native_client = DuckDuckGoSearchRun()
                clients.append(("langchain_duckduckgo_search", native_client))
                logger.info("tool.search_web provider fallback initialized: langchain_duckduckgo_search")
            except Exception:
                logger.warning("tool.search_web no fallback provider available")

    _web_search_clients = [
        (name, _CircuitBreakerProvider(name, client)) for name, client in clients
    ]
    return _web_search_clients


def _run_web_search_internal(query: str) -> tuple[str | None, str | None, str | None]:
    clients = _ensure_web_search_clients()
    if not clients:
        return (
            None,
            None,
            (
                "Web search is unavailable in current environment. "
                "Set FIRECRAWL_API_KEY or BRAVE_SEARCH_API_KEY in .env, or configure "
                "AGENT_SEARXNG_BASE_URLS, or enable AGENT_WEB_ENABLE_DDG_FALLBACK=1."
            ),
        )
    errors: list[str] = []
    for provider_name, provider in clients:
        try:
            response = provider.run(query)
            response_text = response if isinstance(response, str) else str(response)
            if not response_text or response_text.strip() == "No web search results found.":
                errors.append(f"{provider_name}: no results")
                continue
            return provider_name, response_text, None
        except _ProviderCoolingDownError as exc:
            # Circuit open: skip quietly - the open/recover transitions are
            # already logged once by the breaker.
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"{provider_name}: {exc}")
            logger.info("tool.search_web provider failed: %s (%s)", provider_name, exc)
    return None, None, f"Web search failed: {' | '.join(errors)}"


@tool(
    "search_web",
    description=(
        "Search public web content. For time-sensitive questions run 2-3 queries with "
        "different keywords before answering; prefer results that carry a publication "
        "date, cite the source URL in the answer, and state an explicit as-of date. "
        "If repeated queries still yield no reliable external evidence, say the evidence "
        "is insufficient instead of falling back to generic knowledge."
    ),
    args_schema=SearchWebInput,
)
def search_web(query: str) -> str:
    safe_query = _sanitize_query(query)
    logger.info(
        "tool.search_web called: query_len=%s query_preview=%s",
        len(safe_query),
        _preview(safe_query),
    )
    if not safe_query:
        logger.warning("tool.search_web blocked: empty query after sanitization")
        return "Web search query is empty after sanitization."
    if _is_dangerous_query(safe_query):
        logger.warning("tool.search_web blocked by policy")
        return "Blocked by tool policy: query appears unsafe for web search."
    provider_name, response_text, error_text = _run_web_search_internal(safe_query)
    if response_text is None:
        logger.warning("tool.search_web unavailable: %s", error_text)
        return str(error_text or "Web search failed.")
    logger.info(
        "tool.search_web success: provider=%s response_len=%s",
        provider_name,
        len(response_text),
    )
    return response_text
