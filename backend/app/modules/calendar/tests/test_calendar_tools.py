"""Công cụ AI của lịch và việc (bài kiểm của agent AI, việc 3-02)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.ai.schemas import ToolContext
from app.core import clock
from app.modules.calendar import tools
from app.modules.calendar.models import Event
from app.modules.task import tools as task_tools

NOW = datetime(2026, 11, 18, 4, 30, tzinfo=UTC)  # 11:30 giờ Việt Nam


def vn(d, h, mi=0):
    return datetime(2026, 11, d, h, mi, tzinfo=UTC) - timedelta(hours=7)


@pytest.fixture
def ctx(db, user, monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: NOW)
    return ToolContext(session=db, user=user, conversation_id=None, now=NOW)


def _call(mod, ctx, name, **data):
    spec = next(t for t in mod.TOOLS if t.name == name)
    model = spec.input_model.model_validate(data)
    return (
        spec,
        model,
        (spec.run(ctx, model) if not (spec.needs_approval and spec.needs_approval(model)) else None),
    )


def _add(ctx, **kw):
    base = {
        "title": "Họp với anh Tuấn",
        "start_at": vn(19, 15),
        "end_at": None,
        "all_day": None,
        "start_date": None,
        "end_date": None,
        "location": "Văn phòng",
        "description": None,
        "remind_minutes": [30],
        "attendee_emails": None,
    }
    return _call(tools, ctx, "add_event", **{**base, **kw})[2]


def test_add_event_lists_and_reports_conflict(ctx):
    first = _add(ctx)
    assert first.result["when"] == "15:00 19/11/2026 tới 16:00" and first.result["trung_lich"] == []
    assert first.actions[0]["screen"] == "event_detail"
    second = _add(ctx, title="Đi nha sĩ", start_at=vn(19, 15, 30))
    assert [c["title"] for c in second.result["trung_lich"]] == ["Họp với anh Tuấn"]
    listed = _call(tools, ctx, "list_events", from_date="2026-11-19", to_date=None, query="tuan")[2]
    assert [e["title"] for e in listed.result["items"]] == ["Họp với anh Tuấn"]


def test_guests_go_through_confirm_card(ctx, db):
    out = _add(ctx, attendee_emails=["hanh@example.com"])
    assert out.result["trang_thai"] == "cho_duyet"
    assert out.actions[0]["type"] == "confirm" and out.actions[0]["pending_action_id"] > 0
    assert db.scalars(select(Event)).all() == []


def test_delete_one_has_undo_and_many_needs_approval(ctx, db):
    a = _add(ctx).result["event_id"]
    b = _add(ctx, title="Ăn tối", start_at=vn(19, 19)).result["event_id"]
    c = _add(ctx, title="Xem phim", start_at=vn(19, 21)).result["event_id"]
    spec, model, out = _call(
        tools, ctx, "delete_event", events=[{"event_id": a, "occurrence_start": None}], reason="hủy"
    )
    assert out.actions[0]["type"] == "undo" and db.get(Event, a).deleted_at is not None
    spec, model, out = _call(
        tools,
        ctx,
        "delete_event",
        events=[{"event_id": b, "occurrence_start": None}, {"event_id": c, "occurrence_start": None}],
        reason="dọn",
    )
    assert out is None  # cần duyệt
    draft = spec.prepare(ctx, model)
    assert draft.input["events"][0]["event_id"] == b and draft.danger is True
    assert db.get(Event, b).deleted_at is None


def test_set_reminder_is_alarm(ctx, db):
    out = _call(tools, ctx, "set_reminder", text="Mua thuốc cho mẹ", remind_at=vn(18, 17))[2]
    e = db.get(Event, out.result["event_id"])
    assert e.is_alarm is True and e.remind_minutes == [0]


def _task(ctx, **kw):
    base = {
        "title": "Nộp hồ sơ visa",
        "due_date": None,
        "due_at": None,
        "priority": None,
        "remind_minutes": None,
        "note": None,
    }
    return _call(task_tools, ctx, "add_task", **{**base, **kw})[2]


def test_task_with_time_goes_on_calendar_and_completes(ctx):
    out = _task(ctx, due_at=vn(20, 17), priority="high")
    assert out.result["da_len_lich"] is True and out.result["priority"] == "high"
    tid = out.result["task_id"]
    done = _call(
        task_tools,
        ctx,
        "update_task",
        task_id=tid,
        title=None,
        due_date=None,
        due_at=None,
        clear_due=None,
        priority=None,
        status="done",
        note=None,
    )[2]
    assert done.result["status"] == "done"
    listed = _call(task_tools, ctx, "list_tasks", status="all", due=None, limit=None)[2]
    assert [t["task_id"] for t in listed.result["items"]] == [tid]


def test_task_delete_rules(ctx):
    ids = [_task(ctx, title=f"Việc {i}").result["task_id"] for i in range(3)]
    spec, model, out = _call(task_tools, ctx, "delete_task", task_ids=ids[:1], reason="xong")
    assert out.actions[0]["type"] == "undo"
    spec, model, out = _call(task_tools, ctx, "delete_task", task_ids=ids[1:], reason="dọn")
    assert out is None and len(spec.prepare(ctx, model).details) == 2
    spec.execute(ctx, {"task_ids": ids[1:]})
    left = _call(task_tools, ctx, "list_tasks", status=None, due=None, limit=None)[2]
    assert left.result["items"] == []
