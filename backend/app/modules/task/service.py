"""Việc (11 mục 3.11, 12 mục 5.5). Hàm công khai dùng chung cho API và công cụ AI.

Việc không giờ (`due_date` hoặc không hạn) đi Google Tasks; việc có giờ (`due_at`) sinh một sự kiện
lịch qua module calendar, nhắc theo sự kiện đó. Google Tasks báo xong thì `done`; báo xóa thì
`remote_deleted`, người dùng chọn giữ hay xóa (QĐ-21, K11).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, func, literal, or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.context import UserContext
from app.core.errors import NotFoundError, ValidationError
from app.modules.calendar import service as calendar_service
from app.modules.task.models import Task

UNDO_DAYS = 30
PRIORITIES = ("low", "normal", "high")


def _far() -> datetime:
    return datetime(9999, 12, 31, tzinfo=UTC)


def _outbox():
    try:
        from app.integrations.google import outbox
    except ModuleNotFoundError:
        return None
    return outbox


def enqueue(session: Session, user_id: int, op: str, t: Task) -> bool:
    """Chỉ việc không giờ đi Google Tasks; việc vừa có giờ cũng đẩy để phần đồng bộ gỡ khỏi Tasks."""
    if t.due_at is not None and not t.google_task_id:
        t.sync_status = "local_only"
        return False
    ob = _outbox()
    queued = bool(ob) and ob.enqueue(session, user_id, "tasks", op, "task", t.id)
    if queued:
        t.sync_status = "pending"
    elif t.google_task_id is None:
        t.sync_status = "local_only"
    return queued


def serialize(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "note": t.note,
        "status": t.status,
        "priority": t.priority,
        "due_date": t.due_date,
        "due_at": t.due_at,
        "completed_at": t.completed_at,
        "completed_source": t.completed_source,
        "event_id": t.event_id,
        "sync_status": t.sync_status,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


def _get(session: Session, user_id: int, task_id: int, include_deleted: bool = False) -> Task:
    stmt = select(Task).where(Task.id == task_id, Task.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(Task.deleted_at.is_(None))
    t = session.scalar(stmt)
    if t is None:
        raise NotFoundError("Không tìm thấy việc.")
    return t


def get_task(session: Session, user: UserContext, task_id: int) -> dict:
    return serialize(_get(session, user.user_id, task_id))


def _check(data: dict) -> None:
    if "title" in data and not (data["title"] or "").strip():
        raise ValidationError(fields={"title": "Nhập tên việc."})
    if len(data.get("title") or "") > 1024:
        raise ValidationError(fields={"title": "Tên việc tối đa 1.024 ký tự."})
    if len(data.get("note") or "") > 8000:
        raise ValidationError(fields={"note": "Ghi chú tối đa 8.000 ký tự."})
    if data.get("priority") is not None and data["priority"] not in PRIORITIES:
        raise ValidationError(fields={"priority": "Ưu tiên là low, normal hoặc high."})
    if data.get("due_date") is not None and data.get("due_at") is not None:
        raise ValidationError(fields={"due_at": "Chọn một: hạn theo ngày hoặc hạn có giờ."})
    due_at = data.get("due_at")
    if due_at is not None and due_at.tzinfo is None:
        raise ValidationError(fields={"due_at": "Giờ cần có múi giờ."})


def create_task(session: Session, user: UserContext, data: dict, source: str = "app") -> dict:
    """`data`: title, note, priority, due_date hoặc due_at, remind_minutes (chỉ khi có giờ)."""
    _check({**data, "title": data.get("title") or ""})
    t = Task(
        user_id=user.user_id,
        title=data["title"].strip(),
        note=data.get("note"),
        status="todo",
        priority=data.get("priority") or "normal",
        due_date=data.get("due_date"),
        due_at=data.get("due_at"),
        source=source,
        sync_status="local_only",
    )
    session.add(t)
    session.flush()
    if t.due_at is not None:
        t.event_id = calendar_service.create_task_event(
            session, user, t.id, t.title, t.due_at, data.get("remind_minutes")
        )
    enqueue(session, user.user_id, "insert", t)
    session.flush()
    return serialize(t)


def update_task(session: Session, user: UserContext, task_id: int, changes: dict) -> dict:
    t = _get(session, user.user_id, task_id)
    _check({"due_date": t.due_date if "due_date" not in changes else changes["due_date"], **changes})
    # Đặt một loại hạn thì bỏ loại kia.
    if changes.get("due_at") is not None:
        changes.setdefault("due_date", None)
    if changes.get("due_date") is not None:
        changes.setdefault("due_at", None)
    for key in ("title", "note", "priority", "due_date", "due_at"):
        if key in changes:
            setattr(t, key, changes[key].strip() if key == "title" else changes[key])
    session.flush()
    if t.due_at is not None and t.event_id is None:
        t.event_id = calendar_service.create_task_event(
            session, user, t.id, t.title, t.due_at, changes.get("remind_minutes")
        )
    elif t.due_at is not None:
        calendar_service.update_task_event(
            session,
            user,
            t.event_id,
            title=t.title,
            due_at=t.due_at,
            remind_minutes=changes.get("remind_minutes"),
        )
    elif t.event_id is not None:
        calendar_service.delete_task_event(session, user, t.event_id)
        t.event_id = None
    enqueue(session, user.user_id, "patch", t)
    session.flush()
    return serialize(t)


def complete_task(session: Session, user: UserContext, task_id: int, source: str = "app") -> dict:
    t = _get(session, user.user_id, task_id)
    if t.status != "done":
        t.status, t.completed_at, t.completed_source = "done", clock.now(), source
        session.flush()
        if source == "app":
            enqueue(session, user.user_id, "patch", t)
    return serialize(t)


def reopen_task(session: Session, user: UserContext, task_id: int) -> dict:
    t = _get(session, user.user_id, task_id)
    if t.status != "todo":
        t.status, t.completed_at, t.completed_source = "todo", None, None
        session.flush()
        enqueue(session, user.user_id, "patch", t)
    return serialize(t)


def delete_task(session: Session, user: UserContext, task_id: int) -> None:
    t = _get(session, user.user_id, task_id)
    t.deleted_at = clock.now()
    if t.event_id is not None:
        calendar_service.delete_task_event(session, user, t.event_id)
    session.flush()
    if t.google_task_id:
        enqueue(session, user.user_id, "delete", t)


def restore_task(session: Session, user: UserContext, task_id: int) -> dict:
    t = _get(session, user.user_id, task_id, include_deleted=True)
    if t.deleted_at is None:
        return serialize(t)
    if t.deleted_at < clock.now() - timedelta(days=UNDO_DAYS):
        raise NotFoundError("Việc đã xóa quá 30 ngày, không khôi phục được.")
    t.deleted_at = None
    t.google_task_id = t.google_etag = t.google_updated_at = None
    if t.event_id is not None:
        calendar_service.restore_event(session, user, t.event_id)
    elif t.due_at is not None:
        t.event_id = calendar_service.create_task_event(session, user, t.id, t.title, t.due_at, None)
    session.flush()
    enqueue(session, user.user_id, "insert", t)
    return serialize(t)


def resolve_remote_delete(session: Session, user: UserContext, task_id: int, keep: bool) -> dict | None:
    """Google Tasks báo đã xóa: giữ thì đẩy lại thành việc mới, không thì xóa trong app (K11)."""
    t = _get(session, user.user_id, task_id)
    if t.sync_status != "remote_deleted":
        raise ValidationError(fields={"keep": "Việc này không bị xóa trên Google."})
    if not keep:
        t.deleted_at = clock.now()
        t.sync_status = "local_only"
        if t.event_id is not None:
            calendar_service.delete_task_event(session, user, t.event_id)
        session.flush()
        return None
    t.google_task_id = t.google_etag = t.google_updated_at = None
    t.sync_status = "local_only"
    session.flush()
    enqueue(session, user.user_id, "insert", t)
    return serialize(t)


def list_tasks(
    session: Session,
    user: UserContext,
    *,
    status: str | None = "todo",
    due: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> dict:
    tz = user.timezone
    sort = func.coalesce(
        Task.due_at,
        func.timezone(tz, Task.due_date + literal(timedelta(hours=23, minutes=59))),
        literal(_far()),
    ).label("sort")
    stmt: Select = select(Task, sort).where(Task.user_id == user.user_id, Task.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Task.status == status)
    now = clock.now()
    today = clock.to_local(now, tz).date()
    if due == "overdue":
        stmt = stmt.where(or_(Task.due_at < now, Task.due_date < today))
    elif due == "today":
        lo, hi = clock.period_range("day", today, tz)
        stmt = stmt.where(
            or_(Task.due_at.between(lo, hi - timedelta(microseconds=1)), Task.due_date == today)
        )
    elif due == "week":
        hi = clock.local_day_start(today + timedelta(days=7), tz)
        stmt = stmt.where(or_(Task.due_at < hi, Task.due_date < today + timedelta(days=7)))
    elif due == "none":
        stmt = stmt.where(Task.due_at.is_(None), Task.due_date.is_(None))
    elif due is not None:
        raise ValidationError(fields={"due": "Lọc hạn là overdue, today, week hoặc none."})
    if cursor:
        try:
            at, tid = cursor.rsplit("|", 1)
            at_dt, tid_int = datetime.fromisoformat(at), int(tid)
        except ValueError as exc:
            raise ValidationError(fields={"cursor": "Con trỏ trang không hợp lệ."}) from exc
        stmt = stmt.where(or_(sort > at_dt, (sort == at_dt) & (Task.id > tid_int)))
    rows = session.execute(stmt.order_by(sort, Task.id).limit(limit + 1)).all()
    items = [serialize(t) for t, _ in rows[:limit]]
    next_cursor = None
    if len(rows) > limit:
        last_task, last_sort = rows[limit - 1]
        next_cursor = f"{last_sort.isoformat()}|{last_task.id}"
    return {"items": items, "next_cursor": next_cursor}


def complete_from_reminder(session: Session, user: UserContext, task_id: int) -> dict | None:
    """Nút Xong trên thông báo nhắc (sự kiện `reminder_action`); việc đã xóa thì bỏ qua."""
    try:
        return complete_task(session, user, task_id)
    except NotFoundError:
        return None
