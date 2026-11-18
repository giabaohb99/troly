import json
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.integrations.google import outbox, tasks_sync
from app.integrations.google.models import GoogleOutbox, GoogleSyncState


def _state(db, account) -> GoogleSyncState:
    return db.scalar(
        select(GoogleSyncState).where(
            GoogleSyncState.google_account_id == account.id, GoogleSyncState.service == "tasks"
        )
    )


def _pushed(db, account, task_store, **fields) -> dict:
    local_id = task_store.add_local(**fields)
    outbox.enqueue(db, account.user_id, "tasks", "insert", "task", local_id)
    outbox.push_due(db)
    return task_store.rows[local_id]


def test_push_creates_list_and_task_with_date_only_due(db, fake, account, task_store):
    row = _pushed(
        db,
        account,
        task_store,
        title="Nộp thuế",
        due_date=date(2026, 11, 30),
        priority="high",
        note="Mang CCCD",
    )
    (list_id,) = fake.lists
    assert fake.lists[list_id]["title"] == "Trợ lý"
    task = fake.tasks[list_id][row["google_task_id"]]
    assert task["due"] == "2026-11-30T00:00:00.000Z"
    assert task["notes"] == "Mang CCCD\nƯu tiên: cao"
    assert row["google_tasklist_id"] == list_id and row["sync_status"] == "synced"


def test_timed_task_is_not_pushed_and_moves_off_tasks(db, fake, account, task_store):
    row = _pushed(db, account, task_store, title="Gọi điện")
    row["due_at"] = datetime(2026, 11, 30, 3, 0, tzinfo=UTC)
    outbox.enqueue(db, account.user_id, "tasks", "patch", "task", row["id"])
    outbox.push_due(db)
    (list_id,) = fake.lists
    assert all(t.get("deleted") for t in fake.tasks[list_id].values())
    assert row["google_task_id"] is None


def test_pull_reads_completion_and_uncheck(db, fake, account, task_store):
    row = _pushed(db, account, task_store, title="Mua sữa")
    state = _state(db, account)
    (list_id,) = fake.lists
    fake.put_task(
        list_id, {"id": row["google_task_id"], "status": "completed", "completed": "2026-11-18T09:00:00Z"}
    )
    tasks_sync.pull_status(db, account, state)
    assert row["status"] == "done" and row["completed_source"] == "google"
    fake.put_task(list_id, {"id": row["google_task_id"], "status": "needsAction"})
    tasks_sync.pull_status(db, account, state)
    assert row["status"] == "todo"
    params = fake.calls("GET", r"/tasks$")[-1].url.params
    assert params["showHidden"] == "true" and params["showDeleted"] == "true" and "updatedMin" in params


def test_pull_marks_remote_deleted_and_drops_pending_edit(db, fake, account, task_store):
    row = _pushed(db, account, task_store, title="Đi chợ")
    (list_id,) = fake.lists
    row["title"] = "Đi chợ sáng"
    outbox.enqueue(db, account.user_id, "tasks", "patch", "task", row["id"])
    fake.put_task(list_id, {"id": row["google_task_id"], "deleted": True})
    tasks_sync.pull_status(db, account, _state(db, account))
    assert row["sync_status"] == "remote_deleted"
    waiting = db.scalars(select(GoogleOutbox).where(GoogleOutbox.op == "patch")).one()
    assert waiting.status == "failed"


def test_title_change_on_google_is_ignored(db, fake, account, task_store):
    row = _pushed(db, account, task_store, title="Tên trong app")
    (list_id,) = fake.lists
    fake.put_task(list_id, {"id": row["google_task_id"], "title": "Tên trên Google"})
    tasks_sync.pull_status(db, account, _state(db, account))
    assert row["title"] == "Tên trong app"


def test_echo_of_own_push_is_skipped_and_no_outbox_created(db, fake, account, task_store):
    row = _pushed(db, account, task_store, title="Việc")
    before = db.scalar(select(GoogleOutbox.id).order_by(GoogleOutbox.id.desc()))
    tasks_sync.pull_status(db, account, _state(db, account))
    assert row["status"] == "todo"
    assert db.scalar(select(GoogleOutbox.id).order_by(GoogleOutbox.id.desc())) == before


def test_tasks_added_directly_on_google_are_ignored(db, fake, account, task_store):
    _pushed(db, account, task_store, title="Việc")
    (list_id,) = fake.lists
    fake.put_task(list_id, {"id": "la", "title": "Tự thêm trên Google", "status": "needsAction"})
    assert tasks_sync.pull_status(db, account, _state(db, account)) == 0


def test_patch_404_marks_remote_deleted(db, fake, account, task_store):
    row = _pushed(db, account, task_store, title="Việc")
    (list_id,) = fake.lists
    fake.tasks[list_id].pop(row["google_task_id"])
    row["title"] = "Đổi tên"
    outbox.enqueue(db, account.user_id, "tasks", "patch", "task", row["id"])
    outbox.push_due(db)
    assert row["sync_status"] == "remote_deleted"


def test_done_task_sends_completed_status(db, fake, account, task_store):
    row = _pushed(db, account, task_store, title="Việc", status="done")
    (list_id,) = fake.lists
    assert fake.tasks[list_id][row["google_task_id"]]["status"] == "completed"
    body = json.loads(fake.calls("POST", r"/tasks$")[0].content)
    assert body["status"] == "completed"
