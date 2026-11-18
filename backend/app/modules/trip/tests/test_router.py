"""Đường /trips qua HTTP. Dựng app riêng có router lõi và router trip (registry bật module ở 4-01)."""

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.modules.trip.tests.conftest import run_job


@pytest.fixture
def trip_client(db, user):
    from app.core.errors import install_error_handlers
    from app.core.router import router as core_router
    from app.modules.trip.router import router as trip_router

    app = FastAPI()
    install_error_handlers(app)
    api = APIRouter(prefix="/api/v1")
    api.include_router(core_router)
    api.include_router(trip_router)
    app.include_router(api)
    client = TestClient(app)
    resp = client.post(
        "/api/v1/auth/login", json={"email": "dai.ca@example.com", "password": "matkhau-thu-123"}
    )
    client.headers["Authorization"] = f"Bearer {resp.json()['data']['access_token']}"
    return client


def test_import_get_links_and_stop_patch(db, trip_client, maps_fake, fake_ai, sample_file):
    resp = trip_client.post("/api/v1/trips/import", json={"file_id": sample_file, "start_date": "2026-11-21"})
    assert resp.status_code == 202
    trip_id = resp.json()["data"]["trip_id"]
    assert trip_client.get(f"/api/v1/trips/{trip_id}").json()["data"]["status"] == "importing"
    run_job(db, "trip_import", trip_id)
    trip = trip_client.get(f"/api/v1/trips/{trip_id}").json()["data"]
    assert trip["status"] == "draft" and len(trip["days"]) == 3
    stop = trip["days"][0]["stops"][0]
    assert {"leg_km", "leg_minutes", "parent_stop_id", "resolve_status"} <= set(stop)
    listing = trip_client.get("/api/v1/trips").json()["data"]["items"]
    assert listing[0]["id"] == trip_id and "needs_confirmation_count" in listing[0]
    links = trip_client.get(f"/api/v1/trips/{trip_id}/map-links", params={"day_no": 1, "max_waypoints": 3})
    assert links.status_code == 200 and links.json()["data"]["days"][0]["segments"]
    patched = trip_client.patch(
        f"/api/v1/trips/{trip_id}/stops/{stop['id']}", json={"resolve_status": "manual", "note": "Đổ xăng"}
    )
    assert patched.status_code == 200 and patched.json()["data"]["note"] == "Đổ xăng"
    assert trip_client.post(f"/api/v1/trips/{trip_id}/evaluate").status_code == 202


def test_import_needs_exactly_one_source(trip_client):
    assert trip_client.post("/api/v1/trips/import", json={}).status_code == 400
    assert trip_client.post("/api/v1/trips/import", json={"text": "a", "url": "https://x"}).status_code == 400


def test_bad_max_waypoints_and_missing_trip(trip_client):
    assert trip_client.get("/api/v1/trips/999999").status_code == 404
    assert trip_client.get("/api/v1/trips/999999/map-links", params={"max_waypoints": 5}).status_code in (
        400,
        404,
    )
