from fastapi.testclient import TestClient

from app import main


def test_health_returns_ok_when_database_up():
    client = TestClient(main.app)

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["db"] is True


def test_health_returns_503_when_database_down(monkeypatch):
    monkeypatch.setattr(main, "check_database", lambda: False)
    client = TestClient(main.app)

    response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["data"]["status"] == "degraded"
    assert body["message"]
