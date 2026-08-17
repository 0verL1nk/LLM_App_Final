from types import SimpleNamespace

from agent.tools import web_search


def _reset_clients(monkeypatch) -> None:
    monkeypatch.setattr(web_search, "_web_search_clients", None)


def _fake_response(status_code: int, payload: dict) -> SimpleNamespace:
    return SimpleNamespace(status_code=status_code, json=lambda: payload)


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
