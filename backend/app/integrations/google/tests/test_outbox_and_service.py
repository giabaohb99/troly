import json
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from app.core import clock
from app.core.models import JobQueue
from app.integrations.google import oauth, outbox, service
from app.integrations.google.models import GoogleAccount, GoogleOutbox, GoogleSyncState


def test_enqueue_without_account_does_nothing(db, user):
    assert outbox.enqueue(db, user.user_id, "calendar", "insert", "event", 1) is False
    assert db.scalar(select(GoogleOutbox)) is None


def test_enqueue_merges_waiting_row_and_delete_wins(db, account):
    outbox.enqueue(db, account.user_id, "calendar", "insert", "event", 7)
    outbox.enqueue(db, account.user_id, "calendar", "patch", "event", 7, {"send_updates": "all"})
    outbox.enqueue(db, account.user_id, "calendar", "delete", "event", 7)
    rows = db.scalars(select(GoogleOutbox)).all()
    assert len(rows) == 1 and rows[0].op == "delete" and rows[0].payload == {"send_updates": "all"}


def test_transient_failure_backs_off_then_fails_after_five(db, fake, account, cal_store):
    start = datetime(2026, 11, 21, 3, 0, tzinfo=UTC)
    local_id = cal_store.add_local(start_at=start, end_at=start, google_event_id=outbox.new_event_id())
    outbox.enqueue(db, account.user_id, "calendar", "insert", "event", local_id)
    row = db.scalar(select(GoogleOutbox))
    for attempt in range(1, 6):
        fake.forced = [httpx.Response(503)] * 6
        row.next_attempt_at = clock.now()
        outbox.push_due(db)
        db.refresh(row)
        assert row.attempts == attempt
    assert row.status == "failed"
    assert cal_store.rows[local_id]["sync_status"] == "error"


def test_reauth_keeps_command_pending(db, fake, account, cal_store):
    local_id = cal_store.add_local(
        start_at=clock.now(), end_at=clock.now(), google_event_id=outbox.new_event_id()
    )
    outbox.enqueue(db, account.user_id, "calendar", "insert", "event", local_id)
    account.access_expires_at = clock.now()
    fake.refresh_tokens.clear()
    outbox.push_due(db)
    row = db.scalar(select(GoogleOutbox))
    assert row.status == "pending" and row.attempts == 0
    assert db.get(GoogleAccount, account.id).status == "reauth_required"


def test_retry_with_reapply_restores_discarded_change(db, account, cal_store):
    local_id = cal_store.add_local(title="Bản Google")
    outbox.enqueue(db, account.user_id, "calendar", "patch", "event", local_id)
    row = db.scalar(select(GoogleOutbox))
    outbox.mark_conflict(row, {"title": "Bản của app"})
    db.flush()
    data = service.retry_outbox(db, account.user_id, row.id, reapply=True)
    assert data["status"] == "pending"
    assert cal_store.rows[local_id]["title"] == "Bản của app"


def test_initial_sync_pulls_calendar_creates_list_and_pushes_existing_tasks(
    db, fake, account, cal_store, task_store
):
    fake.put_event(
        {"id": "ev1", "summary": "A", "start": {"date": "2026-11-20"}, "end": {"date": "2026-11-21"}}
    )
    task_id = task_store.add_local(title="Việc có sẵn")
    job = db.scalar(select(JobQueue).where(JobQueue.kind == "google_initial_sync"))
    service.run_initial_sync(db, job)
    assert cal_store.by_google("ev1")["all_day"] is True
    states = {s.service: s for s in db.scalars(select(GoogleSyncState))}
    assert states["calendar"].initial_sync_state == "done" and states["calendar"].channel_id is not None
    assert states["tasks"].resource_id in fake.lists
    waiting = db.scalar(select(GoogleOutbox).where(GoogleOutbox.local_id == task_id))
    assert waiting is not None and waiting.service == "tasks"


def test_sync_due_respects_min_interval_unless_webhook(db, fake, account, cal_store):
    job = db.scalar(select(JobQueue).where(JobQueue.kind == "google_initial_sync"))
    service.run_initial_sync(db, job)
    state = db.scalar(select(GoogleSyncState).where(GoogleSyncState.service == "calendar"))
    state.next_sync_at = clock.now() - timedelta(seconds=1)
    calls = len(fake.calls("GET", r"/events$"))
    service.sync_due(db, "calendar", min_seconds=300)
    assert len(fake.calls("GET", r"/events$")) == calls  # vừa đồng bộ, chưa đủ 5 phút
    state.needs_sync = True
    state.next_sync_at = clock.now() - timedelta(seconds=1)
    service.sync_due(db, "calendar", min_seconds=300)
    assert len(fake.calls("GET", r"/events$")) == calls + 1


def test_status_reports_packs_and_failed_count(db, account):
    outbox.enqueue(db, account.user_id, "calendar", "insert", "event", 3)
    db.scalar(select(GoogleOutbox)).status = "failed"
    data = service.get_status(db, account.user_id)
    assert data["connected"] and data["email"] == "dai.ca@gmail.com"
    names = {p["name"]: p for p in data["packs"]}
    assert names["calendar"]["enabled"] and not names["gmail"]["enabled"]
    assert data["failed_outbox_count"] == 1
    assert data["initial_sync"]["state"] == "pending"


def test_disconnect_revokes_stops_channels_and_deletes_account(db, fake, account, cal_store, task_store):
    job = db.scalar(select(JobQueue).where(JobQueue.kind == "google_initial_sync"))
    service.run_initial_sync(db, job)
    refresh = oauth._decrypt(account, account.refresh_token_enc)
    service.disconnect(db, account.user_id, keep_data=True)
    assert refresh in fake.revoked and fake.stopped
    assert cal_store.disconnected == [True] and task_store.disconnected == [True]
    assert oauth.get_account(db, account.user_id) is None


def test_callback_html_redirects_to_app(db, user, fake):
    html = oauth.callback_html(oauth.CallbackResult("thieu-quyen", "Thiếu quyền <x>", ["calendar"]))
    assert "troly://cai-dat/google?ket-qua=thieu-quyen" in html and "&lt;x&gt;" in html


def test_conflict_detail_hidden_from_api(db, account):
    outbox.enqueue(db, account.user_id, "calendar", "patch", "event", 9)
    row = db.scalar(select(GoogleOutbox))
    outbox.mark_conflict(row, {"title": "x"})
    item = service.list_outbox(db, account.user_id, ["conflict"])[0]
    assert item["has_discarded_change"] is True and item["last_error"] is None
    assert json.loads(row.last_error) == {"title": "x"}


def test_missing_store_keeps_command_pending(db, fake, account):
    outbox.enqueue(db, account.user_id, "calendar", "insert", "event", 5)
    outbox.push_due(db)
    row = db.scalar(select(GoogleOutbox))
    assert row.status == "pending" and row.attempts == 0 and row.next_attempt_at > clock.now()
