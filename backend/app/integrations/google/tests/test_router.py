"""Đường Google qua HTTP. Dựng app riêng có router lõi và router Google, vì main.py do agent kiến trúc gắn."""

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def google_client(db, user, fake):
    from app.core.errors import install_error_handlers
    from app.core.router import router as core_router
    from app.integrations.google.router import router as google_router

    app = FastAPI()
    install_error_handlers(app)
    api = APIRouter(prefix="/api/v1")
    api.include_router(core_router)
    api.include_router(google_router)
    app.include_router(api)
    client = TestClient(app)
    resp = client.post(
        "/api/v1/auth/login", json={"email": "dai.ca@example.com", "password": "matkhau-thu-123"}
    )
    client.headers["Authorization"] = f"Bearer {resp.json()['data']['access_token']}"
    return client


def test_connect_callback_status_flow(google_client, fake):
    resp = google_client.post("/api/v1/google/connect", json={"packs": ["calendar", "tasks"]})
    assert resp.status_code == 200
    state = parse_qs(urlparse(resp.json()["data"]["auth_url"]).query)["state"][0]
    page = google_client.get(
        "/api/v1/google/oauth/callback", params={"code": fake.issue_code(), "state": state}
    )
    assert page.status_code == 200 and "ket-qua=ok" in page.text
    status = google_client.get("/api/v1/google/status").json()["data"]
    assert status["connected"] and status["email"] == "dai.ca@gmail.com"


def test_status_when_not_connected(google_client):
    data = google_client.get("/api/v1/google/status").json()["data"]
    assert data["connected"] is False


def test_unknown_pack_rejected(google_client):
    assert google_client.post("/api/v1/google/connect", json={"packs": ["photos"]}).status_code == 400


def test_sync_without_connection_is_409(google_client):
    resp = google_client.post("/api/v1/google/sync/calendar")
    assert resp.status_code == 409 and resp.json()["data"]["code"] == "GOOGLE_NOT_CONNECTED"


def test_webhook_always_200_without_auth(google_client):
    resp = google_client.post(
        "/api/v1/webhooks/google/calendar",
        headers={"Authorization": "", "X-Goog-Channel-ID": "khong-phai-uuid", "X-Goog-Channel-Token": "x"},
    )
    assert resp.status_code == 200 and resp.content == b""
