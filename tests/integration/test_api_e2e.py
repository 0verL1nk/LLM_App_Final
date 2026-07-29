from fastapi.testclient import TestClient

from api.main import app


def test_api_health_and_spa_contract() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
