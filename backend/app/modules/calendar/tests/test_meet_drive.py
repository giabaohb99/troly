"""Meet trong sự kiện, tệp lên Drive (5-01): phần phía module, Google giả của agent Google."""

import sys
import types
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.integrations.google.models import GoogleOutbox
from app.integrations.google.stores import RemoteEvent
from app.integrations.google.tests.conftest import account, fake  # noqa: F401
from app.modules.calendar import service
from app.modules.calendar.google_store import STORE
from app.modules.calendar.models import Event

START = datetime(2026, 11, 26, 2, 0, tzinfo=UTC)


def _payloads(db):
    return [r.payload for r in db.scalars(select(GoogleOutbox).order_by(GoogleOutbox.id))]


def test_meet_flag_goes_to_outbox_and_link_is_stored(db, user, fake, account):  # noqa: F811
    e = service.create_event(db, user, {"title": "Gọi video", "start_at": START, "meet": True})["event"]
    assert _payloads(db)[-1] == {"meet": True}
    STORE.save_meet_url(db, user.user_id, e["id"], "https://meet.google.com/abc-defg-hij")
    assert service.get_event(db, user, e["id"])["meet_url"] == "https://meet.google.com/abc-defg-hij"

    plain = service.create_event(db, user, {"title": "Không Meet", "start_at": START})["event"]
    service.update_event(db, user, plain["id"], {"meet": True})
    assert _payloads(db)[-1].get("meet") is True


def test_write_remote_takes_meet_url_when_google_sends_it(db, user):
    remote = RemoteEvent(
        google_event_id="m1",
        etag="e1",
        updated=None,
        status="confirmed",
        title="Họp",
        start_at=START,
        end_at=START,
    )
    remote.meet_url = "https://meet.google.com/xyz-abcd-efg"
    local = STORE.write_remote(db, user.user_id, None, "primary", remote, None)
    assert db.get(Event, local).meet_url == "https://meet.google.com/xyz-abcd-efg"


def test_guest_event_with_meet_waits_for_approval(db, user):
    out = service.create_event(
        db,
        user,
        {"title": "Họp khách", "start_at": START, "meet": True, "attendees": [{"email": "a@example.com"}]},
    )
    assert out["pending_action"]["tool_name"] == "add_event"


@pytest.fixture
def fake_drive(monkeypatch):
    calls = []
    module = types.ModuleType("app.integrations.google.drive")
    module.request_upload = lambda session, user_id, file_id: calls.append(file_id) or {"queued": True}
    monkeypatch.setitem(sys.modules, "app.integrations.google.drive", module)
    import app.integrations.google as google_pkg

    monkeypatch.setattr(google_pkg, "drive", module, raising=False)
    return calls


def test_drive_route_queues_ready_file_and_store_saves_link(auth_client, db, user, fake_drive):
    from app.modules.file.google_store import STORE as FILE_STORE
    from app.modules.file.models import File

    f = File(
        user_id=user.user_id,
        r2_key="files/u/x",
        original_name="a.docx",
        mime="text/plain",
        size_bytes=3,
        purpose="trip_export",
        status="ready",
    )
    db.add(f)
    db.flush()
    resp = auth_client.post(f"/api/v1/files/{f.id}/drive")
    assert resp.status_code == 202 and resp.json()["data"] == {"queued": True} and fake_drive == [f.id]

    FILE_STORE.save_drive_result(db, user.user_id, f.id, "drv1", "https://drive.google.com/file/d/drv1/view")
    from app.modules.file import service as file_service

    db.refresh(f)
    got = file_service.serialize(f)
    assert got["drive_file_id"] == "drv1" and got["drive_url"].endswith("/view")
