import time
from types import SimpleNamespace

from agent.tools import web_search


def _reset_clients(monkeypatch) -> None:
    monkeypatch.setattr(web_search, "_web_search_clients", None)


def _fake_response(status_code: int, payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        status_code=status_code,
        headers={},
        json=lambda: payload,
    )


FIRECRAWL_OK_PAYLOAD = {
    "success": True,
    "data": {
        "web": [
            {
                "title": "Self-RAG paper",
                "url": "https://arxiv.org/abs/2310.11511",
                "description": "Self-reflective retrieval-augmented generation.",
            }
        ]
    },
}


def test_firecrawl_client_enabled_by_default_without_key(monkeypatch):
    _reset_clients(monkeypatch)
    monkeypatch.delenv("AGENT_WEB_FIRECRAWL_ENABLED", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    client = web_search._build_firecrawl_web_search_client()

    assert client is not None
    assert client.api_key == ""


def test_firecrawl_client_disabled_via_env(monkeypatch):
    monkeypatch.setenv("AGENT_WEB_FIRECRAWL_ENABLED", "0")

    assert web_search._build_firecrawl_web_search_client() is None


def test_firecrawl_run_sends_keyless_request_and_parses_data_web(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return _fake_response(200, FIRECRAWL_OK_PAYLOAD)

    monkeypatch.setattr(web_search.httpx, "post", fake_post)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    client = web_search._build_firecrawl_web_search_client()

    rendered = client.run("Self-RAG")

    assert captured["url"] == "https://api.firecrawl.dev/v2/search"
    assert captured["json"]["query"] == "Self-RAG"
    assert "Authorization" not in captured["headers"]
    assert "Self-RAG paper" in rendered
    assert "https://arxiv.org/abs/2310.11511" in rendered


def test_firecrawl_run_sends_bearer_when_key_configured(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(headers=headers)
        return _fake_response(200, FIRECRAWL_OK_PAYLOAD)

    monkeypatch.setattr(web_search.httpx, "post", fake_post)
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-key")
    client = web_search._build_firecrawl_web_search_client()

    client.run("Self-RAG")

    assert captured["headers"]["Authorization"] == "Bearer fc-test-key"


def test_firecrawl_run_raises_on_error_status(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        return _fake_response(429, {"success": False})

    monkeypatch.setattr(web_search.httpx, "post", fake_post)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    client = web_search._build_firecrawl_web_search_client()

    try:
        client.run("Self-RAG")
    except RuntimeError as exc:
        assert "firecrawl status=429" in str(exc)
    else:
        raise AssertionError("Expected firecrawl error status to raise")


def test_provider_chain_includes_firecrawl_and_ddg_fallback_appends(monkeypatch):
    _reset_clients(monkeypatch)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_WEB_ENABLE_DDG_FALLBACK", "1")

    try:
        clients = web_search._ensure_web_search_clients()
    finally:
        _reset_clients(monkeypatch)

    names = [name for name, _client in clients]
    assert "firecrawl_search" in names
    assert "wikipedia_api" in names
    assert "native_duckduckgo_search" in names
    assert names.index("wikipedia_api") < names.index("native_duckduckgo_search")


def test_provider_chain_without_ddg_flag_has_no_fallback(monkeypatch):
    _reset_clients(monkeypatch)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_WEB_ENABLE_DDG_FALLBACK", raising=False)

    try:
        clients = web_search._ensure_web_search_clients()
    finally:
        _reset_clients(monkeypatch)

    names = [name for name, _client in clients]
    assert "firecrawl_search" in names
    assert "native_duckduckgo_search" not in names
    assert "langchain_duckduckgo_search" not in names


def test_searxng_explicitly_disabled_skips_public_pool(monkeypatch):
    monkeypatch.setenv("AGENT_SEARXNG_BASE_URLS", "none")

    assert web_search._parse_searxng_instances() == []
    assert web_search._build_searxng_web_search_client() is None


def test_searxng_off_alias_also_disables(monkeypatch):
    monkeypatch.setenv("AGENT_SEARXNG_BASE_URLS", "off")

    assert web_search._parse_searxng_instances() == []


def test_firecrawl_run_retries_429_with_backoff_then_succeeds(monkeypatch):
    _reset_clients(monkeypatch)
    calls = {"count": 0}
    delays: list[float] = []

    class _FakeResponse:
        def __init__(self, status_code: int, headers: dict[str, str] | None = None):
            self.status_code = status_code
            self.headers = headers or {}

        def json(self):
            return {"data": {"web": [{"title": "t", "url": "https://a", "description": "d"}]}}

    def _fake_post(url, json=None, headers=None, timeout=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse(429, {"Retry-After": "3"})
        return _FakeResponse(200)

    monkeypatch.setattr(web_search.httpx, "post", _fake_post)
    monkeypatch.setattr(web_search.time, "sleep", delays.append)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_WEB_FIRECRAWL_ENABLED", "1")

    client = web_search._build_firecrawl_web_search_client()
    result = client.run("Self-RAG 最新进展")

    assert calls["count"] == 2
    assert delays == [3.0]
    assert "https://a" in result


def test_firecrawl_run_raises_after_exhausted_429_retries(monkeypatch):
    _reset_clients(monkeypatch)
    calls = {"count": 0}
    delays: list[float] = []

    class _FakeResponse:
        status_code = 429
        headers: dict[str, str] = {}

    def _fake_post(url, json=None, headers=None, timeout=None):
        calls["count"] += 1
        return _FakeResponse()

    monkeypatch.setattr(web_search.httpx, "post", _fake_post)
    monkeypatch.setattr(web_search.time, "sleep", delays.append)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.setenv("AGENT_WEB_FIRECRAWL_ENABLED", "1")

    client = web_search._build_firecrawl_web_search_client()

    try:
        client.run("Self-RAG 最新进展")
    except RuntimeError as exc:
        assert "status=429" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError after exhausted retries")

    assert calls["count"] == web_search.FIRECRAWL_RETRY_MAX_ATTEMPTS
    assert delays == [2.0, 4.0, 8.0] + [10.0] * (web_search.FIRECRAWL_RETRY_MAX_ATTEMPTS - 4)


class _FlakyProvider:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, query: str) -> str:
        self.calls += 1
        raise RuntimeError("boom")


def test_circuit_breaker_opens_after_threshold_and_skips(monkeypatch):
    monkeypatch.setenv("AGENT_WEB_CIRCUIT_THRESHOLD", "2")
    breaker = web_search._CircuitBreakerProvider("flaky", _FlakyProvider())

    for _ in range(2):
        try:
            breaker.run("q")
        except RuntimeError:
            pass

    # Circuit now open: the underlying client is not invoked.
    underlying = breaker._client
    calls_before = underlying.calls
    try:
        breaker.run("q")
    except RuntimeError as exc:
        assert "cooling down" in str(exc)
    assert underlying.calls == calls_before


def test_circuit_breaker_doubles_cooldown_up_to_cap(monkeypatch):
    monkeypatch.setenv("AGENT_WEB_CIRCUIT_THRESHOLD", "1")
    monkeypatch.setenv("AGENT_WEB_CIRCUIT_COOLDOWN_SECONDS", "60")
    monkeypatch.setenv("AGENT_WEB_CIRCUIT_MAX_COOLDOWN_SECONDS", "120")

    breaker = web_search._CircuitBreakerProvider("flaky", _FlakyProvider())
    try:
        breaker.run("q")  # trip 1 -> 60s window
    except RuntimeError:
        pass
    first_window = 60.0
    breaker._cooldown_until = 0.0  # force expiry for the next trip
    try:
        breaker.run("q")  # trip 2 -> doubled, capped at 120
    except RuntimeError:
        pass
    assert first_window == 60.0
    assert breaker._cooldown_seconds == 120.0
    assert breaker._cooldown_until - time.monotonic() > 100  # second window is the doubled one


def test_circuit_breaker_recovers_after_cooldown(monkeypatch):
    monkeypatch.setenv("AGENT_WEB_CIRCUIT_THRESHOLD", "3")

    class _RecoveringProvider:
        def __init__(self) -> None:
            self.calls = 0
            self.fail_first = 1

        def run(self, query: str) -> str:
            self.calls += 1
            if self.calls <= self.fail_first:
                raise RuntimeError("boom")
            return "ok result"

    provider = _RecoveringProvider()
    breaker = web_search._CircuitBreakerProvider("flaky", provider)
    try:
        breaker.run("q")  # failure 1 (below threshold, breaker stays closed)
    except RuntimeError:
        pass
    assert breaker.run("q") == "ok result"  # success resets the counter
    assert breaker._consecutive_failures == 0
