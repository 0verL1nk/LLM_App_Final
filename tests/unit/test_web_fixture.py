"""Tests for frozen web-search fixtures (record / replay / miss semantics)."""

from agent.application.evals import web_fixture
from agent.tools import web_search


def _teardown() -> None:
    web_fixture.deactivate()


def test_normalize_query_collapses_case_and_whitespace() -> None:
    assert web_fixture.normalize_query("  Self-RAG   最新 进展 ") == "self-rag 最新 进展"


def test_save_and_load_fixture_roundtrip(tmp_path) -> None:
    original_dir = web_fixture.WEB_FIXTURE_DIR
    web_fixture.WEB_FIXTURE_DIR = tmp_path
    try:
        entries = {"self-rag": {"text": "result text", "provider": "p", "captured_at": "t"}}
        checksum = web_fixture.save_fixture("unit", entries)
        loaded = web_fixture.load_fixture("unit")

        assert loaded == entries
        assert checksum == web_fixture.checksum(entries)
    finally:
        web_fixture.WEB_FIXTURE_DIR = original_dir


def test_replay_hit_returns_recorded_text_without_live_chain(tmp_path, monkeypatch) -> None:
    original_dir = web_fixture.WEB_FIXTURE_DIR
    web_fixture.WEB_FIXTURE_DIR = tmp_path
    try:
        web_fixture.save_fixture(
            "unit",
            {"self-rag": {"text": "recorded result", "provider": "p", "captured_at": "t"}},
        )
        monkeypatch.setattr(
            web_search,
            "_run_web_search_internal",
            lambda _q: (_ for _ in ()).throw(AssertionError("live chain must not run")),
        )
        web_fixture.activate_replay("unit")
        try:
            assert web_search.search_web.invoke({"query": "SELF-RAG  "}) == "recorded result"
        finally:
            _teardown()
    finally:
        web_fixture.WEB_FIXTURE_DIR = original_dir


def test_replay_miss_is_explicit_and_never_falls_back(tmp_path, monkeypatch) -> None:
    original_dir = web_fixture.WEB_FIXTURE_DIR
    web_fixture.WEB_FIXTURE_DIR = tmp_path
    try:
        web_fixture.save_fixture("unit", {})
        monkeypatch.setattr(
            web_search,
            "_run_web_search_internal",
            lambda _q: (_ for _ in ()).throw(AssertionError("live chain must not run")),
        )
        web_fixture.activate_replay("unit")
        try:
            result = web_search.search_web.invoke({"query": "未采集的查询"})
            assert web_fixture.FIXTURE_MISS_MARKER in result
        finally:
            _teardown()
    finally:
        web_fixture.WEB_FIXTURE_DIR = original_dir


def test_record_stores_success_but_not_live_failure(tmp_path, monkeypatch) -> None:
    original_dir = web_fixture.WEB_FIXTURE_DIR
    web_fixture.WEB_FIXTURE_DIR = tmp_path
    try:
        calls = {"n": 0}

        def _fake_live(query: str):
            calls["n"] += 1
            if calls["n"] == 1:
                return "provider_a", "live result text", None
            return None, None, "Web search failed: everything down"

        monkeypatch.setattr(web_search, "_run_web_search_internal", _fake_live)
        web_fixture.activate_record("unit", refresh=True)
        try:
            assert web_search.search_web.invoke({"query": "good query"}) == "live result text"
            assert "Web search failed" in web_search.search_web.invoke({"query": "bad query"})

            entries = web_fixture.load_fixture("unit")
            assert "good query" in entries
            assert "bad query" not in entries
        finally:
            _teardown()
    finally:
        web_fixture.WEB_FIXTURE_DIR = original_dir
