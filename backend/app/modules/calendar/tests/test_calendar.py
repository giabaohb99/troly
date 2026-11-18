"""Lịch: trải lần lặp và ngoại lệ, nhắc trên máy, sửa một lần, khách mời phải duyệt (11 mục 3.11)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.errors import NotFoundError
from app.integrations.google.stores import RemoteEvent
from app.modules.calendar import service
from app.modules.calendar.google_store import STORE
from app.modules.calendar.models import Event

VN = timedelta(hours=7)


def vn(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=UTC) - VN


def google_event(db, user, gid, **kw):
    base = {"etag": f"e-{gid}", "updated": None, "status": "confirmed", "title": "Sự kiện Google"}
    return STORE.write_remote(
        db, user.user_id, None, "primary", RemoteEvent(google_event_id=gid, **{**base, **kw}), None
    )


@pytest.fixture
def weekly(db, user):
    """Họp thứ Hai 09:00 bốn tuần từ 23/11; bỏ 30/11 bằng EXDATE; 7/12 dời 14:00; 14/12 bị hủy."""
    master = google_event(
        db,
        user,
        "w1",
        title="Họp thứ Hai",
        start_at=vn(2026, 11, 23, 9),
        end_at=vn(2026, 11, 23, 10),
        timezone="Asia/Ho_Chi_Minh",
        recurrence=["RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=4", "EXDATE;TZID=Asia/Ho_Chi_Minh:20261130T090000"],
    )
    google_event(
        db,
        user,
        "w1_moved",
        title="Họp dời chiều",
        start_at=vn(2026, 12, 7, 14),
        end_at=vn(2026, 12, 7, 15),
        recurring_event_id="w1",
        original_start_at=vn(2026, 12, 7, 9),
    )
    google_event(
        db,
        user,
        "w1_cancel",
        status="cancelled",
        recurring_event_id="w1",
        original_start_at=vn(2026, 12, 14, 9),
    )
    return master


def test_expands_recurrence_with_exdate_moved_and_cancelled(db, user, weekly):
    items = service.list_events(db, user, vn(2026, 11, 20), vn(2026, 12, 31))
    assert [(i["title"], i["start_at"]) for i in items] == [
        ("Họp thứ Hai", vn(2026, 11, 23, 9)),
        ("Họp dời chiều", vn(2026, 12, 7, 14)),
    ]
    assert all(i["id"] == weekly and i["is_recurring"] for i in items)
    assert items[1]["occurrence_start"] == vn(2026, 12, 7, 9)


def test_all_day_and_single_events_in_window(db, user):
    service.create_event(
        db,
        user,
        {
            "title": "Nghỉ phép",
            "all_day": True,
            "start_date": date(2026, 12, 1),
            "end_date": date(2026, 12, 3),
        },
    )
    service.create_event(db, user, {"title": "Khám răng", "start_at": vn(2026, 12, 2, 8)})
    titles = [i["title"] for i in service.list_events(db, user, vn(2026, 12, 2), vn(2026, 12, 3))]
    assert titles == ["Nghỉ phép", "Khám răng"]
    assert service.list_events(db, user, vn(2026, 12, 3), vn(2026, 12, 4)) == []


def test_series_edit_is_refused_but_one_occurrence_can_change(db, user, weekly):
    with pytest.raises(service.RecurringSeriesEdit):
        service.update_event(db, user, weekly, {"title": "Đổi cả chuỗi"})
    out = service.update_event(db, user, weekly, {"title": "Họp ngắn"}, occurrence_start=vn(2026, 11, 23, 9))
    assert out["id"] == weekly and out["title"] == "Họp ngắn"
    x = (
        db.query(Event)
        .filter(Event.recurring_event_id == "w1", Event.original_start_at == vn(2026, 11, 23, 9))
        .one()
    )
    assert x.title == "Họp ngắn" and x.start_at == vn(2026, 11, 23, 9)
    service.delete_event(db, user, weekly, occurrence_start=vn(2026, 11, 23, 9))
    assert service.list_events(db, user, vn(2026, 11, 20), vn(2026, 11, 30)) == []
    with pytest.raises(NotFoundError):
        service.update_event(db, user, weekly, {"title": "x"}, occurrence_start=vn(2026, 11, 24, 9))


def test_reminders_only_app_source_and_cover_occurrences(db, user, weekly):
    service.create_event(
        db,
        user,
        {
            "title": "Đón con",
            "start_at": vn(2026, 11, 25, 16),
            "remind_minutes": [30, 0],
            "location": "Trường",
        },
    )
    google_event(
        db, user, "g2", title="Lịch của Google", start_at=vn(2026, 11, 26, 9), end_at=vn(2026, 11, 26, 10)
    )
    # Đổi nguồn nhắc của cả chuỗi về app không cần sửa chuỗi trên Google.
    service.update_event(db, user, weekly, {"remind_source": "app", "remind_minutes": [10]})

    data = service.list_reminders(db, user, vn(2026, 11, 22), 31)
    keys = [(i["title"], i["fire_at"]) for i in data["items"]]
    assert keys == [
        ("Họp thứ Hai", vn(2026, 11, 23, 8, 50)),
        ("Đón con", vn(2026, 11, 25, 15, 30)),
        ("Đón con", vn(2026, 11, 25, 16)),
        ("Họp dời chiều", vn(2026, 12, 7, 13, 50)),
    ]
    first = data["items"][1]
    assert first["body"] == "16:00 - Trường" and first["deep_link"].startswith("troly://lich/su-kien/")
    assert service.list_reminders(db, user, vn(2026, 11, 22), 31)["revision"] == data["revision"]


def test_reminders_api_etag_and_device_auth(auth_client, db, user):
    service.create_event(
        db,
        user,
        {
            "title": "Uống thuốc",
            "start_at": datetime.now(UTC) + timedelta(days=1),
            "remind_minutes": [5],
            "is_alarm": True,
        },
    )
    resp = auth_client.get("/api/v1/calendar/reminders")
    assert resp.status_code == 200 and resp.json()["data"]["items"][0]["kind"] == "alarm"
    etag = resp.headers["ETag"]
    assert auth_client.get("/api/v1/calendar/reminders", headers={"If-None-Match": etag}).status_code == 304
    token = auth_client.post("/api/v1/devices", json={"name": "S25+"}).json()["data"]["device_token"]
    resp = auth_client.get("/api/v1/calendar/reminders", headers={"Authorization": f"Device {token}"})
    assert resp.status_code == 200 and len(resp.json()["data"]["items"]) == 1


def test_guests_need_approval_then_event_is_created(auth_client, db, user):
    body = {
        "title": "Ăn tối",
        "start_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
        "attendees": [{"email": "Ban.Than@example.com"}],
    }
    resp = auth_client.post("/api/v1/calendar/events", json=body)
    assert resp.status_code == 202
    pending = resp.json()["data"]["pending_action"]
    assert pending["tool_name"] == "add_event" and pending["action"]["type"] == "confirm"
    assert db.query(Event).count() == 0

    approved = auth_client.post(f"/api/v1/chat/actions/{pending['id']}/approve")
    assert approved.status_code == 200, approved.text
    [e] = db.query(Event).all()
    assert e.attendees[0]["email"] == "ban.than@example.com"

    # Sửa nội dung cần duyệt lại; đổi nhắc thì không.
    assert auth_client.patch(f"/api/v1/calendar/events/{e.id}", json={"title": "Ăn trưa"}).status_code == 202
    assert (
        auth_client.patch(f"/api/v1/calendar/events/{e.id}", json={"remind_minutes": [60]}).status_code == 200
    )
    assert auth_client.delete(f"/api/v1/calendar/events/{e.id}").status_code == 202


def test_delete_restore_and_api_series_error(auth_client, db, user, weekly):
    e = service.create_event(db, user, {"title": "Cắt tóc", "start_at": vn(2026, 12, 5, 10)})["event"]
    assert auth_client.delete(f"/api/v1/calendar/events/{e['id']}").json()["data"] is None
    assert auth_client.get(f"/api/v1/calendar/events/{e['id']}").status_code == 404
    assert auth_client.post(f"/api/v1/calendar/events/{e['id']}/restore").status_code == 200
    resp = auth_client.patch(f"/api/v1/calendar/events/{weekly}", json={"title": "x"})
    assert resp.status_code == 409 and resp.json()["data"]["code"] == "RECURRING_SERIES_EDIT"
    rng = auth_client.get(
        "/api/v1/calendar/events",
        params={"from": vn(2026, 1, 1).isoformat(), "to": vn(2026, 6, 1).isoformat()},
    )
    assert rng.status_code == 400


def test_invited_event_only_reminders_change_and_occurrence_link(db, user, weekly):
    invited = google_event(
        db,
        user,
        "inv1",
        title="Tiệc cưới",
        start_at=vn(2026, 12, 20, 18),
        end_at=vn(2026, 12, 20, 21),
        organizer_self=False,
    )
    assert service.get_event(db, user, invited)["is_organizer"] is False
    with pytest.raises(service.ConflictError) as err:
        service.update_event(db, user, invited, {"title": "Đổi tên"})
    assert err.value.code == "EVENT_NOT_ORGANIZER"
    assert (
        service.update_event(db, user, invited, {"remind_source": "app", "remind_minutes": [60]})[
            "remind_source"
        ]
        == "app"
    )

    service.update_event(db, user, weekly, {"remind_source": "app", "remind_minutes": [10]})
    first = service.list_reminders(db, user, vn(2026, 11, 22), 2)["items"][0]
    assert first["deep_link"] == f"troly://lich/su-kien/{weekly}?lan=2026-11-23T02:00:00Z"
    assert first["reminder_key"] == f"event:{weekly}:20261123T020000Z:10"


def test_reminders_accept_bare_revision(auth_client, db, user):
    resp = auth_client.get("/api/v1/calendar/reminders")
    revision = resp.json()["data"]["revision"]
    assert (
        auth_client.get("/api/v1/calendar/reminders", headers={"If-None-Match": revision}).status_code == 304
    )


def test_bulk_delete_approval_and_card_in_conversation(db, user):
    from app.modules.calendar.approvals import EXECUTORS

    a = service.create_event(db, user, {"title": "A", "start_at": vn(2026, 12, 1, 9)})["event"]
    b = service.create_event(db, user, {"title": "B", "start_at": vn(2026, 12, 1, 10)})["event"]
    out = EXECUTORS["delete_event"](db, user, {"events": [{"event_id": a["id"]}, {"event_id": b["id"]}]})
    assert out == {"deleted": 2, "event_ids": [a["id"], b["id"]]}
    assert service.list_events(db, user, vn(2026, 12, 1), vn(2026, 12, 2)) == []

    pending = service.create_event(
        db,
        user,
        {"title": "C", "start_at": vn(2026, 12, 2, 9), "attendees": [{"email": "x@example.com"}]},
        conversation_id=None,
    )["pending_action"]
    assert pending["tool_name"] == "add_event"
