"""/device/events, /device/config, /devices/listened-apps (12 mục 5.8)."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core import clock


@pytest.fixture
def device(auth_client):
    resp = auth_client.post("/api/v1/devices", json={"name": "S25+"})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Device {resp.json()['data']['device_token']}"}


def event(package="com.VCB", text_="So du TK VCB 0011xxxx9876 -45,000 VND luc 18-11-2026 12:05:11", **kw):
    return {
        "client_event_id": str(kw.pop("client_event_id", uuid.uuid4())),
        "kind": "notification",
        "app_package": package,
        "posted_at": kw.pop("posted_at", clock.now().isoformat()),
        "payload": {"title": kw.pop("title", "Thông báo VCB"), "text": text_, "secret_extra": "x", **kw},
    }


def post(client, headers, events):
    resp = client.post("/api/v1/device/events", json={"events": events}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_events_accept_dedupe_and_reject_per_event(client, device, db):
    ok_event = event()
    old = event(posted_at=(clock.now() - timedelta(days=8)).isoformat())
    data = post(
        client,
        device,
        [
            ok_event,
            event(package="com.unknown.app"),
            event(text_="Ma OTP cua Quy khach la 482913"),
            old,
            {"client_event_id": str(uuid.uuid4()), "kind": "notification", "payload": {}},
            {"kind": "bogus"},
        ],
    )
    codes = {r["client_event_id"]: r["code"] for r in data["rejected"]}
    assert data["accepted"] == 1 and data["duplicates"] == 0
    assert sorted(codes.values()) == sorted(
        ["APP_NOT_LISTENED", "OTP_DETECTED", "EVENT_TOO_OLD", "INVALID_EVENT", "INVALID_EVENT"]
    )
    assert codes[old["client_event_id"]] == "EVENT_TOO_OLD"

    again = post(client, device, [ok_event])
    assert again == {"accepted": 0, "duplicates": 1, "rejected": []}

    payload = db.execute(text("SELECT payload FROM tab_device_event WHERE status = 'pending'")).scalar_one()
    assert "secret_extra" not in payload and payload["title"] == "Thông báo VCB"
    # OTP: không giữ nội dung, chỉ đếm.
    otp_rows = db.execute(
        text("SELECT payload::text FROM tab_device_event WHERE error = 'OTP_DETECTED'")
    ).all()
    assert [r[0] for r in otp_rows] == ["{}"]


def test_sms_accepted_from_real_default_sms_package(client, device):
    sms = event(package="com.example.sms", text_="Chieu nay hop luc 3h nhe", title="Anh Hai")
    assert post(client, device, [sms])["rejected"][0]["code"] == "APP_NOT_LISTENED"
    client.post("/api/v1/device/heartbeat", json={"default_sms_package": "com.example.sms"}, headers=device)
    assert post(client, device, [{**sms, "client_event_id": str(uuid.uuid4())}])["accepted"] == 1


def test_config_etag_and_listened_apps_change_revision(auth_client, device):
    first = auth_client.get("/api/v1/device/config", headers=device)
    assert first.status_code == 200
    cfg = first.json()["data"]
    packages = {a["package_name"]: a for a in cfg["listened_apps"]}
    assert {"com.VCB", "vn.com.techcombank.bb.app", "com.mservice.momotransfer", "sms_default"} <= set(
        packages
    )
    assert cfg["upload"] == {"batch_max": 50, "min_interval_seconds": 30} and cfg["otp_rules_version"]
    etag = first.headers["ETag"]
    assert (
        auth_client.get("/api/v1/device/config", headers={**device, "If-None-Match": etag}).status_code == 304
    )

    apps = auth_client.get("/api/v1/devices/listened-apps").json()["data"]["items"]
    zalo = next(a for a in apps if a["package_name"] == "com.zing.zalo")
    resp = auth_client.patch(f"/api/v1/devices/listened-apps/{zalo['id']}", json={"enabled": False})
    assert resp.status_code == 200 and resp.json()["data"]["enabled"] is False
    assert (
        auth_client.get("/api/v1/device/config", headers={**device, "If-None-Match": etag}).status_code == 200
    )

    created = auth_client.post(
        "/api/v1/devices/listened-apps",
        json={"package_name": "vn.vpbank.app", "label": "VPBank", "purpose": "expense", "parser": "generic"},
    )
    assert created.status_code == 201
    dup = auth_client.post(
        "/api/v1/devices/listened-apps",
        json={"package_name": "vn.vpbank.app", "label": "VPBank", "purpose": "expense", "parser": "generic"},
    )
    assert dup.status_code == 409
    assert (
        auth_client.delete(f"/api/v1/devices/listened-apps/{created.json()['data']['id']}").status_code == 200
    )
    # Bị tắt thì sự kiện bị từ chối.
    zalo_event = event(package="com.zing.zalo", text_="chao", title="Lan")
    assert post(auth_client, device, [zalo_event])["rejected"][0]["code"] == "APP_NOT_LISTENED"
