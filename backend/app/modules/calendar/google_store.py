"""Cài CalendarStore của integrations/google/stores.py trên tab_event (registry.register_integrations)."""

from datetime import UTC, date, datetime

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.core import clock
from app.integrations.google.stores import LocalEvent, LocalRef, RemoteEvent
from app.modules.calendar.models import Event

SNAPSHOT_FIELDS = (
    "title",
    "description",
    "location",
    "all_day",
    "start_at",
    "end_at",
    "start_date",
    "end_date",
    "status",
    "attendees",
    "remind_minutes",
    "remind_source",
    "deleted_at",
)


def _utc(at: datetime | None) -> datetime | None:
    if at is None:
        return None
    return (at if at.tzinfo else at.replace(tzinfo=UTC)).astimezone(UTC)


def _row(session: Session, user_id: int, local_id: int) -> Event | None:
    return session.scalar(select(Event).where(Event.id == local_id, Event.user_id == user_id))


class CalendarStore:
    def find_by_google_id(self, session, user_id, calendar_id, google_event_id):
        e = session.scalar(
            select(Event).where(
                Event.user_id == user_id,
                Event.google_calendar_id == calendar_id,
                Event.google_event_id == google_event_id,
            )
        )
        return LocalRef(e.id, e.google_etag, e.google_updated_at) if e else None

    def write_remote(self, session, user_id, account_id, calendar_id, event: RemoteEvent, local_id):
        """Google thắng: ghi đè nội dung, bỏ `deleted_at` (dòng sống lại khi Google còn giữ)."""
        e = _row(session, user_id, local_id) if local_id is not None else None
        if e is None:
            e = Event(user_id=user_id, source="google", remind_source="google")
            session.add(e)
        original = _utc(event.original_start_at)
        start_at, end_at = _utc(event.start_at), _utc(event.end_at)
        start_date, end_date, all_day = event.start_date, event.end_date, event.all_day
        if event.status == "cancelled" and not (start_at or start_date):
            # Ngoại lệ hủy chỉ có giờ gốc: giữ dòng để lần lặp đó biến mất khi trải.
            start_at = end_at = original or clock.now()
            all_day, start_date, end_date = False, None, None
        if all_day and end_date is None and start_date is not None:
            end_date = date.fromordinal(start_date.toordinal() + 1)
        if not all_day and end_at is None:
            end_at = start_at
        e.title = (event.title or "").strip()[:1024] or "(Không tiêu đề)"
        e.description, e.location = event.description, event.location
        e.all_day, e.start_at, e.end_at, e.start_date, e.end_date = (
            all_day,
            start_at,
            end_at,
            start_date,
            end_date,
        )
        e.timezone = event.timezone or e.timezone
        e.status = event.status if event.status in ("confirmed", "tentative", "cancelled") else "confirmed"
        e.recurrence = event.recurrence or None
        e.recurring_event_id, e.original_start_at = event.recurring_event_id, original
        e.attendees = event.attendees or []
        e.is_organizer = event.organizer_self
        if e.remind_source == "google":
            e.remind_minutes = [] if event.reminders_use_default else sorted(set(event.reminder_minutes))[:5]
        e.google_account_id, e.google_calendar_id, e.google_event_id = (
            account_id,
            calendar_id,
            event.google_event_id,
        )
        e.google_etag, e.google_updated_at = event.etag, event.updated
        e.google_html_link = event.html_link or e.google_html_link
        e.sync_status, e.sync_error, e.deleted_at = "synced", None, None
        session.flush()
        if e.task_id is not None and not e.all_day and e.status != "cancelled":
            session.execute(
                text(
                    "UPDATE tab_task SET due_at = :at, title = :t, updated_at = now() WHERE id = :tid AND event_id = :eid"
                ),
                {"at": e.start_at, "t": e.title, "tid": e.task_id, "eid": e.id},
            )
        return e.id

    def mark_remote_cancelled(self, session, user_id, local_id):
        e = _row(session, user_id, local_id)
        if e is None:
            return
        if e.recurring_event_id:
            e.status = "cancelled"
        else:
            e.deleted_at = e.deleted_at or clock.now()
        e.sync_status, e.sync_error = "synced", None
        session.flush()

    def snapshot(self, session, user_id, local_id):
        e = _row(session, user_id, local_id)
        if e is None:
            return {}
        out = {}
        for key in SNAPSHOT_FIELDS:
            value = getattr(e, key)
            out[key] = value.isoformat() if isinstance(value, (datetime, date)) else value
        return out

    def restore_snapshot(self, session, user_id, local_id, data):
        e = _row(session, user_id, local_id)
        if e is None:
            return
        for key in SNAPSHOT_FIELDS:
            if key not in data:
                continue
            value = data[key]
            if key in ("start_at", "end_at", "deleted_at") and isinstance(value, str):
                value = datetime.fromisoformat(value)
            elif key in ("start_date", "end_date") and isinstance(value, str):
                value = date.fromisoformat(value)
            setattr(e, key, value)
        if data.get("deleted"):
            e.deleted_at = clock.now()
        session.flush()

    def delete_remote_rows(self, session, user_id, account_id, keep_ids):
        """Đồng bộ lại toàn bộ (410): dòng nguồn Google không còn trên Google thì xóa mềm."""
        stmt = (
            update(Event)
            .where(
                Event.user_id == user_id,
                Event.google_account_id == account_id,
                Event.source == "google",
                Event.deleted_at.is_(None),
            )
            .values(deleted_at=clock.now())
        )
        if keep_ids:
            stmt = stmt.where(Event.id.not_in(keep_ids))
        return session.execute(stmt).rowcount or 0

    def get_for_push(self, session, user_id, local_id):
        e = _row(session, user_id, local_id)
        if e is None:
            return None
        return LocalEvent(
            id=e.id,
            title=e.title,
            google_event_id=e.google_event_id,
            google_etag=e.google_etag,
            google_calendar_id=e.google_calendar_id or "primary",
            description=e.description,
            location=e.location,
            all_day=e.all_day,
            start_at=e.start_at,
            end_at=e.end_at,
            start_date=e.start_date,
            end_date=e.end_date,
            timezone=e.timezone,
            status=e.status,
            recurrence=e.recurrence,
            recurring_event_id=e.recurring_event_id,
            original_start_at=e.original_start_at,
            attendees=e.attendees or [],
            remind_minutes=list(e.remind_minutes or []),
            remind_source=e.remind_source,
            deleted=e.deleted_at is not None or (bool(e.recurring_event_id) and e.status == "cancelled"),
        )

    def save_push_result(self, session, user_id, local_id, google_event_id, etag, updated):
        session.execute(
            update(Event)
            .where(Event.id == local_id, Event.user_id == user_id)
            .values(
                google_event_id=google_event_id,
                google_etag=etag,
                google_updated_at=updated,
                sync_status="synced",
                sync_error=None,
            )
        )

    def set_sync_status(self, session, user_id, local_id, status, error=None):
        session.execute(
            update(Event)
            .where(Event.id == local_id, Event.user_id == user_id)
            .values(sync_status=status, sync_error=error)
        )

    def on_disconnect(self, session, user_id, keep_data):
        """Ngắt Google: giữ thì mọi dòng thành bản trong app; không giữ thì xóa mềm dòng nguồn Google."""
        if not keep_data:
            session.execute(
                update(Event)
                .where(Event.user_id == user_id, Event.source == "google", Event.deleted_at.is_(None))
                .values(deleted_at=clock.now())
            )
        session.execute(
            update(Event)
            .where(Event.user_id == user_id, Event.google_account_id.is_not(None))
            .values(sync_status="local_only", sync_error=None, google_account_id=None)
        )


STORE = CalendarStore()
