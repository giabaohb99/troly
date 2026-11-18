"""Store thật của calendar, task chạy cùng phần đồng bộ Google (Google giả của agent Google)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.integrations.google import calendar_sync, outbox, stores, tasks_sync
from app.integrations.google.models import GoogleOutbox, GoogleSyncState
from app.integrations.google.tests.conftest import account, fake  # noqa: F401
from app.modules.calendar import service as calendar_service
from app.modules.calendar.models import Event
from app.modules.task import service as task_service
from app.modules.task.models import Task
from app.registry import register_integrations

START = datetime(2026, 11, 25, 2, 0, tzinfo=UTC)


@pytest.fixture
def real_stores():
    register_integrations()
    yield
    stores.register_calendar_store(None)
    stores.register_task_store(None)


def _state(db, acc, service):
    return db.scalar(
        select(GoogleSyncState).where(
            GoogleSyncState.google_account_id == acc.id, GoogleSyncState.service == service
        )
    )


def test_event_round_trip_google_wins_and_recurring(db, user, fake, account, real_stores):  # noqa: F811
    e = calendar_service.create_event(db, user, {"title": "Gặp khách", "start_at": START})["event"]
    row = db.get(Event, e["id"])
    assert row.sync_status == "pending"
    outbox.push_due(db)
    db.refresh(row)
    assert row.sync_status == "synced" and row.google_event_id in fake.events
    assert fake.events[row.google_event_id]["reminders"] == {"useDefault": False, "overrides": []}

    calendar_sync.sync_calendar(db, account, _state(db, account, "calendar"))
    fake.put_event({"id": row.google_event_id, "summary": "Gặp khách (dời)"})
    fake.put_event(
        {
            "id": "rec1",
            "summary": "Tập gym",
            "start": {"dateTime": "2026-11-23T11:00:00Z", "timeZone": "Asia/Ho_Chi_Minh"},
            "end": {"dateTime": "2026-11-23T12:00:00Z"},
            "recurrence": ["RRULE:FREQ=DAILY;COUNT=3"],
            "organizer": {"self": True},
        }
    )
    calendar_sync.sync_calendar(db, account, _state(db, account, "calendar"))
    db.refresh(row)
    assert row.title == "Gặp khách (dời)" and row.remind_source == "app"
    items = calendar_service.list_events(
        db, user, datetime(2026, 11, 23, tzinfo=UTC), datetime(2026, 11, 26, tzinfo=UTC)
    )
    assert [i["title"] for i in items] == ["Tập gym", "Tập gym", "Gặp khách (dời)", "Tập gym"]

    gym = next(i for i in items if i["title"] == "Tập gym")
    calendar_service.delete_event(db, user, gym["id"], occurrence_start=items[1]["occurrence_start"])
    outbox.push_due(db)
    assert db.scalar(select(GoogleOutbox.status).order_by(GoogleOutbox.id.desc())) == "done"
    left = calendar_service.list_events(
        db, user, datetime(2026, 11, 23, tzinfo=UTC), datetime(2026, 11, 26, tzinfo=UTC)
    )
    assert [i["title"] for i in left].count("Tập gym") == 2


def test_task_push_and_google_completion(db, user, fake, account, real_stores):  # noqa: F811
    t = task_service.create_task(db, user, {"title": "Mua quà sinh nhật"})
    outbox.push_due(db)
    row = db.get(Task, t["id"])
    db.refresh(row)
    assert row.sync_status == "synced" and row.google_task_id
    fake.put_task(
        row.google_tasklist_id,
        {"id": row.google_task_id, "status": "completed", "completed": "2026-11-18T05:00:00.000Z"},
    )
    tasks_sync.pull_status(db, account, _state(db, account, "tasks"))
    db.refresh(row)
    assert (row.status, row.completed_source) == ("done", "google")

    # Thêm giờ: rời Google Tasks, đi Calendar bằng sự kiện.
    task_service.update_task(db, user, t["id"], {"due_at": START + timedelta(days=1)})
    outbox.push_due(db)
    db.refresh(row)
    assert row.google_task_id is None and row.event_id is not None
    assert db.get(Event, row.event_id).google_event_id in fake.events
