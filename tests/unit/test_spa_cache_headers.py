from fastapi.testclient import TestClient

from api import main as api_main
from api.main import app


def test_spa_entry_is_served_without_caching(tmp_path, monkeypatch) -> None:
    """A heuristic-cached entry page breaks lazy imports after an in-place update."""
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(api_main, "WEB_DIST", tmp_path)
    monkeypatch.setattr(api_main, "ROOT_STATIC_FILES", {})
    client = TestClient(app)

    for path in ("/", "/research/some-route"):
        response = client.get(path)

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
