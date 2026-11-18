"""Việc: có giờ thành sự kiện lịch, lọc hạn, xong từ Google, Google xóa thì người dùng chọn (11 mục 3.11)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.core import clock
from app.core.errors import ValidationError
from app.modules.calendar import service as calendar_service
from app.modules.calendar.models import Event
from app.modules.task import service
from app.modules.task.google_store import STORE
from app.modules.task.models import Task

NOW = datetime(2026, 11, 18, 3, 0, tzinfo=UTC)  # 10:00 giờ Việt Nam


@pytest.fixture
def _clock(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: NOW)


def test_task_with_time_creates_moves_and_removes_event(db, user, _clock):
    t = service.create_task(
        db, user, {"title": "Gọi điện cho mẹ", "due_at": NOW + timedelta(hours=5), "remind_minutes": [15]}
    )
    e = db.get(Event, t["event_id"])
    assert (e.title, e.start_at, e.task_id, e.remind_minutes) == (
        "Gọi điện cho mẹ",
        NOW + timedelta(hours=5),
        t["id"],
        [15],
    )
    [reminder] = calendar_service.list_reminders(db, user, NOW, 1)["items"]
    assert reminder["source"] == "task" and reminder["source_id"] == t["id"]

    service.update_task(db, user, t["id"], {"due_at": NOW + timedelta(hours=8), "title": "Gọi mẹ"})
    db.refresh(e)
    assert e.start_at == NOW + timedelta(hours=8) and e.title == "Gọi mẹ"

    out = service.update_task(db, user, t["id"], {"due_date": date(2026, 11, 20)})
    db.refresh(e)
    assert out["due_at"] is None and out["event_id"] is None and e.deleted_at is not None


def test_moving_event_updates_task_due(db, user, _clock):
    t = service.create_task(db, user, {"title": "Nộp hồ sơ", "due_at": NOW + timedelta(days=1)})
    calendar_service.update_event(db, user, t["event_id"], {"start_at": NOW + timedelta(days=2)})
    assert service.get_task(db, user, t["id"])["due_at"] == NOW + timedelta(days=2)


def test_due_filters_and_paging(db, user, _clock):
    service.create_task(db, user, {"title": "Quá hạn", "due_date": date(2026, 11, 17)})
    service.create_task(db, user, {"title": "Hôm nay có giờ", "due_at": NOW + timedelta(hours=2)})
    service.create_task(db, user, {"title": "Hôm nay", "due_date": date(2026, 11, 18)})
    service.create_task(db, user, {"title": "Tuần này", "due_date": date(2026, 11, 22)})
    service.create_task(db, user, {"title": "Không hạn"})

    def titles(**kw):
        return [i["title"] for i in service.list_tasks(db, user, **kw)["items"]]

    assert titles(due="overdue") == ["Quá hạn"]
    assert titles(due="today") == ["Hôm nay có giờ", "Hôm nay"]
    assert titles(due="none") == ["Không hạn"]
    assert titles() == ["Quá hạn", "Hôm nay có giờ", "Hôm nay", "Tuần này", "Không hạn"]
    page = service.list_tasks(db, user, limit=2)
    rest = service.list_tasks(db, user, cursor=page["next_cursor"], limit=10)
    assert [i["title"] for i in page["items"] + rest["items"]] == titles()


def test_both_due_kinds_rejected(db, user):
    with pytest.raises(ValidationError):
        service.create_task(db, user, {"title": "x", "due_date": date(2026, 11, 20), "due_at": NOW})


def test_google_done_and_remote_delete_choice(db, user, _clock):
    t = service.create_task(db, user, {"title": "Mua sữa"})
    STORE.save_push_result(db, user.user_id, t["id"], "gt1", "list1", "etag1", NOW)
    assert STORE.list_unlinked(db, user.user_id) == []
    STORE.apply_remote_status(db, user.user_id, t["id"], True, NOW, "etag2", NOW)
    got = service.get_task(db, user, t["id"])
    assert (got["status"], got["completed_source"], got["sync_status"]) == ("done", "google", "synced")

    STORE.mark_remote_deleted(db, user.user_id, t["id"])
    kept = service.resolve_remote_delete(db, user, t["id"], keep=True)
    assert kept["sync_status"] == "local_only" and db.get(Task, t["id"]).google_task_id is None

    STORE.save_push_result(db, user.user_id, t["id"], "gt2", "list1", "etag3", NOW)
    STORE.mark_remote_deleted(db, user.user_id, t["id"])
    assert service.resolve_remote_delete(db, user, t["id"], keep=False) is None
    assert db.get(Task, t["id"]).deleted_at is not None


def test_api_complete_reopen_delete_restore(auth_client, db, user):
    t = auth_client.post("/api/v1/tasks", json={"title": "Đóng tiền điện", "due_date": "2026-11-25"}).json()[
        "data"
    ]
    assert auth_client.post(f"/api/v1/tasks/{t['id']}/complete").json()["data"]["status"] == "done"
    assert auth_client.post(f"/api/v1/tasks/{t['id']}/reopen").json()["data"]["status"] == "todo"
    assert auth_client.delete(f"/api/v1/tasks/{t['id']}").json()["data"] is None
    assert auth_client.get(f"/api/v1/tasks/{t['id']}").status_code == 404
    assert auth_client.post(f"/api/v1/tasks/{t['id']}/restore").json()["data"]["id"] == t["id"]
    assert (
        auth_client.post(f"/api/v1/tasks/{t['id']}/resolve-remote-delete", json={"keep": True}).status_code
        == 400
    )
