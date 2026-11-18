import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.integrations.google import calendar_sync, outbox
from app.integrations.google.models import GoogleOutbox, GoogleSyncState


def _state(db, account) -> GoogleSyncState:
    return db.scalar(
        select(GoogleSyncState).where(
            GoogleSyncState.google_account_id == account.id, GoogleSyncState.service == "calendar"
        )
    )


def _event(event_id: str, **extra) -> dict:
    start = datetime(2026, 11, 20, 2, 0, tzinfo=UTC)
    return {
        "id": event_id,
        "summary": "Họp nhóm",
        "start": {"dateTime": start.isoformat().replace("+00:00", "Z"), "timeZone": "Asia/Ho_Chi_Minh"},
        "end": {"dateTime": (start + timedelta(hours=1)).isoformat().replace("+00:00", "Z")},
        "organizer": {"self": True},
        **extra,
    }


def _initial_sync(db, account):
    state = _state(db, account)
    calendar_sync.sync_calendar(db, account, state)
    return state


def test_full_sync_uses_time_min_and_stores_sync_token(db, fake, account, cal_store):
    fake.put_event(_event("ev1"))
    fake.put_event(_event("ev2", recurrence=["RRULE:FREQ=WEEKLY;BYDAY=MO"]))
    state = _initial_sync(db, account)
    params = fake.calls("GET", r"/events$")[0].url.params
    assert params["singleEvents"] == "false" and "timeMin" in params and params["showDeleted"] == "true"
    assert state.sync_token == f"tok-{fake.seq}" and state.last_full_sync_at is not None
    assert cal_store.by_google("ev2")["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=MO"]
    assert cal_store.by_google("ev1")["remind_source"] == "google"
    assert state.needs_sync is False and state.next_sync_at is not None


def test_incremental_sync_sends_only_sync_token(db, fake, account, cal_store):
    fake.put_event(_event("ev1"))
    state = _initial_sync(db, account)
    fake.put_event({"id": "ev1", "summary": "Họp nhóm dời giờ"})
    calendar_sync.sync_calendar(db, account, state)
    params = fake.calls("GET", r"/events$")[-1].url.params
    assert "syncToken" in params and "timeMin" not in params
    assert cal_store.by_google("ev1")["title"] == "Họp nhóm dời giờ"


def test_pagination_reads_every_page(db, fake, account, cal_store, monkeypatch):
    monkeypatch.setattr(calendar_sync, "PAGE_SIZE", 2)
    for i in range(5):
        fake.put_event(_event(f"ev{i}"))
    _initial_sync(db, account)
    assert len(cal_store.rows) == 5


def test_410_wipes_google_rows_but_keeps_pending_ones(db, fake, account, cal_store):
    fake.put_event(_event("ev1"))
    fake.put_event(_event("ev2"))
    state = _initial_sync(db, account)
    pending_id = cal_store.by_google("ev2")["id"]
    outbox.enqueue(db, account.user_id, "calendar", "patch", "event", pending_id)
    fake.expire_sync_tokens()
    fake.events.pop("ev1")  # đã mất trên Google, lần đồng bộ đủ không trả về
    calendar_sync.sync_calendar(db, account, state)
    assert cal_store.by_google("ev1") is None
    assert cal_store.by_google("ev2") is not None and cal_store.by_google("ev2")["id"] == pending_id


def test_cancelled_master_and_cancelled_exception(db, fake, account, cal_store):
    fake.put_event(_event("ev1"))
    state = _initial_sync(db, account)
    fake.cancel_event("ev1")
    fake.put_event(
        {
            "id": "master_20261127T020000Z",
            "status": "cancelled",
            "recurringEventId": "master",
            "originalStartTime": {"dateTime": "2026-11-27T02:00:00Z"},
        }
    )
    calendar_sync.sync_calendar(db, account, state)
    assert cal_store.by_google("ev1")["deleted"] is True
    exception = cal_store.by_google("master_20261127T020000Z")
    assert exception["recurring_event_id"] == "master" and exception["deleted"] is True


def test_own_write_echo_is_skipped(db, fake, account, cal_store):
    fake.put_event(_event("ev1"))
    state = _initial_sync(db, account)
    cal_store.by_google("ev1")["title"] = "Tên trong app"
    calendar_sync.sync_calendar(db, account, state)  # Google không đổi gì: không về lại
    assert cal_store.by_google("ev1")["title"] == "Tên trong app"


def test_remote_change_while_local_pending_becomes_conflict(db, fake, account, cal_store):
    fake.put_event(_event("ev1"))
    state = _initial_sync(db, account)
    row = cal_store.by_google("ev1")
    row["title"] = "Sửa trong app"
    outbox.enqueue(db, account.user_id, "calendar", "patch", "event", row["id"])
    fake.put_event({"id": "ev1", "summary": "Sửa trên Google"})
    calendar_sync.sync_calendar(db, account, state)
    assert row["title"] == "Sửa trên Google"
    item = db.scalar(select(GoogleOutbox))
    assert item.status == "conflict"
    assert json.loads(item.last_error)["title"] == "Sửa trong app"


def test_push_insert_uses_preset_id_and_silences_google_reminders(db, fake, account, cal_store):
    start = datetime(2026, 11, 21, 3, 0, tzinfo=UTC)
    local_id = cal_store.add_local(
        title="Khám răng",
        start_at=start,
        end_at=start + timedelta(hours=1),
        google_event_id=outbox.new_event_id(),
    )
    preset = cal_store.rows[local_id]["google_event_id"]
    outbox.enqueue(db, account.user_id, "calendar", "insert", "event", local_id)
    outbox.push_due(db)
    body = json.loads(fake.calls("POST", r"/events$")[0].content)
    assert body["id"] == preset
    assert body["reminders"] == {"useDefault": False, "overrides": []}
    assert body["extendedProperties"]["private"]["troly_event_id"] == str(local_id)
    assert cal_store.rows[local_id]["google_etag"] == fake.events[preset]["etag"]
    assert db.scalar(select(GoogleOutbox)).status == "done"


def test_insert_retry_after_duplicate_counts_as_done(db, fake, account, cal_store):
    start = datetime(2026, 11, 21, 3, 0, tzinfo=UTC)
    preset = outbox.new_event_id()
    fake.put_event(_event(preset))  # lần gửi trước đã tới Google nhưng mất phản hồi
    local_id = cal_store.add_local(start_at=start, end_at=start, google_event_id=preset)
    outbox.enqueue(db, account.user_id, "calendar", "insert", "event", local_id)
    outbox.push_due(db)
    assert cal_store.rows[local_id]["google_etag"] == fake.events[preset]["etag"]
    assert db.scalar(select(GoogleOutbox)).status == "done"


def test_patch_412_takes_google_version_and_keeps_local_change(db, fake, account, cal_store):
    fake.put_event(_event("ev1"))
    _initial_sync(db, account)
    row = cal_store.by_google("ev1")
    row["title"] = "Sửa trong app"
    fake.put_event({"id": "ev1", "summary": "Sửa trên Google"})  # etag đổi, app chưa biết
    outbox.enqueue(db, account.user_id, "calendar", "patch", "event", row["id"])
    outbox.push_due(db)
    item = db.scalar(select(GoogleOutbox))
    assert item.status == "conflict"
    assert json.loads(item.last_error)["title"] == "Sửa trong app"
    assert row["title"] == "Sửa trên Google"


def test_send_updates_all_for_guests(db, fake, account, cal_store):
    start = datetime(2026, 11, 21, 3, 0, tzinfo=UTC)
    local_id = cal_store.add_local(
        start_at=start,
        end_at=start,
        google_event_id=outbox.new_event_id(),
        attendees=[{"email": "ban@example.com"}],
    )
    outbox.enqueue(db, account.user_id, "calendar", "insert", "event", local_id, {"send_updates": "all"})
    outbox.push_due(db)
    request = fake.calls("POST", r"/events$")[0]
    assert request.url.params["sendUpdates"] == "all"
    assert json.loads(request.content)["attendees"] == [{"email": "ban@example.com"}]


def test_delete_missing_on_google_is_fine(db, fake, account, cal_store):
    fake.put_event(_event("ev1"))
    _initial_sync(db, account)
    row = cal_store.by_google("ev1")
    fake.events.pop("ev1")
    row["deleted"] = True
    outbox.enqueue(db, account.user_id, "calendar", "delete", "event", row["id"])
    outbox.push_due(db)
    assert db.scalar(select(GoogleOutbox)).status == "done"


def test_single_occurrence_edit_resolves_instance_id(db, fake, account, cal_store):
    fake.put_event(_event("master", recurrence=["RRULE:FREQ=WEEKLY"]))
    _initial_sync(db, account)
    original = datetime(2026, 11, 27, 2, 0, tzinfo=UTC)
    local_id = cal_store.add_local(
        title="Họp nhóm (dời)",
        recurring_event_id="master",
        original_start_at=original,
        start_at=original + timedelta(hours=2),
        end_at=original + timedelta(hours=3),
    )
    outbox.enqueue(db, account.user_id, "calendar", "patch", "event", local_id)
    outbox.push_due(db)
    assert fake.calls("GET", r"/master/instances")
    assert cal_store.rows[local_id]["google_event_id"] == "master_20261127T020000Z"
    assert fake.events["master_20261127T020000Z"]["summary"] == "Họp nhóm (dời)"


def test_watch_created_and_webhook_sets_needs_sync(db, fake, account, cal_store):
    state = _initial_sync(db, account)
    assert calendar_sync.ensure_watch(db, account, state) is True
    channel = fake.channels[str(state.channel_id)]
    assert channel["address"] == "https://assistant.example.test/api/v1/webhooks/google/calendar"
    state.needs_sync = False
    assert calendar_sync.handle_webhook(db, str(state.channel_id), "sai", "exists") is False
    assert state.needs_sync is False
    assert calendar_sync.handle_webhook(db, str(state.channel_id), channel["token"], "exists") is True
    assert state.needs_sync is True


def test_renew_replaces_channel_and_stops_old(db, fake, account, cal_store):
    state = _initial_sync(db, account)
    calendar_sync.ensure_watch(db, account, state)
    old = str(state.channel_id)
    assert calendar_sync.ensure_watch(db, account, state) is False  # còn hạn dài
    state.channel_expires_at = datetime.now(UTC) + timedelta(hours=10)
    assert calendar_sync.ensure_watch(db, account, state) is True
    assert old in fake.stopped and str(state.channel_id) != old


@pytest.mark.parametrize("status", [429, 503])
def test_transient_errors_retry_inside_call(db, fake, account, cal_store, status):
    import httpx

    fake.forced = [httpx.Response(status, json={"error": {"errors": [{"reason": "backendError"}]}})] * 2
    _initial_sync(db, account)
    assert len(fake.sleeps) == 2
