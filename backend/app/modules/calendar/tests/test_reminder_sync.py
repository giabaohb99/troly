"""QĐ-39: phút nhắc đồng bộ hai chiều với Google, cờ báo thức giữ qua đồng bộ."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.integrations.google.models import GoogleOutbox
from app.integrations.google.stores import RemoteEvent
from app.integrations.google.tests.conftest import account, fake  # noqa: F401
from app.modules.calendar import service
from app.modules.calendar.google_store import STORE
from app.modules.calendar.models import Event

START = datetime(2026, 11, 27, 2, 0, tzinfo=UTC)


def remote(gid, **kw):
    base = {
        "etag": "e",
        "updated": None,
        "status": "confirmed",
        "title": "Họp",
        "start_at": START,
        "end_at": START + timedelta(hours=1),
    }
    return RemoteEvent(google_event_id=gid, **{**base, **kw})


def test_write_remote_takes_google_minutes_and_alarm_flag(db, user):
    gid = STORE.write_remote(db, user.user_id, None, "primary", remote("g1", reminder_minutes=[10, 30]), None)
    assert db.get(Event, gid).remind_minutes == [10, 30]

    app_event = service.create_event(
        db, user, {"title": "Đón con", "start_at": START, "remind_minutes": [20]}
    )
    row = db.get(Event, app_event["event"]["id"])
    STORE.write_remote(
        db, user.user_id, None, "primary", remote(row.google_event_id, reminder_minutes=[]), row.id
    )
    assert row.remind_minutes == [20] and row.remind_source == "app"  # Google im: giữ phút của app
    STORE.write_remote(
        db, user.user_id, None, "primary", remote(row.google_event_id, reminder_minutes=[5]), row.id
    )
    assert row.remind_minutes == [5]  # người dùng đặt nhắc trên Google

    STORE.write_remote(db, user.user_id, None, "primary", remote(row.google_event_id, is_alarm=True), row.id)
    assert row.is_alarm is True and STORE.get_for_push(db, user.user_id, row.id).is_alarm is True
    STORE.write_remote(db, user.user_id, None, "primary", remote(row.google_event_id, is_alarm=None), row.id)
    assert row.is_alarm is True  # không có cờ thì giữ nguyên


def _rows(db):
    return [(r.op, r.payload) for r in db.scalars(select(GoogleOutbox).order_by(GoogleOutbox.id))]


def test_reminder_and_alarm_changes_are_pushed_without_approval(db, user, fake, account):  # noqa: F811
    gid = STORE.write_remote(db, user.user_id, account.id, "primary", remote("g2"), None)
    service.update_event(db, user, gid, {"remind_minutes": [45]})
    assert _rows(db)[-1] == ("patch", {"reminders_changed": True})

    app_event = service.create_event(db, user, {"title": "Uống thuốc", "start_at": START})["event"]
    before = len(_rows(db))
    service.update_event(db, user, app_event["id"], {"remind_minutes": [0, 10]})
    assert len(_rows(db)) == before  # app nhắc: Google im, không cần đẩy phút
    # Đẩy xong lần tạo rồi mới đổi báo thức: phải có lệnh patch riêng.
    db.query(GoogleOutbox).filter(GoogleOutbox.local_id == app_event["id"]).update({"status": "done"})
    service.update_event(db, user, app_event["id"], {"is_alarm": True})
    assert _rows(db)[-1] == ("patch", {})
    assert len(_rows(db)) == before + 1
