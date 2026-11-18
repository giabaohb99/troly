"""Giao diện giữa phần đồng bộ Google và bảng nghiệp vụ (tab_event, tab_task).

integrations không import ruột module: module calendar, task cài hai store dưới đây rồi đăng ký lúc import
(`register_calendar_store`, `register_task_store`). Trường dataclass theo tên cột của 11 mục 3.11.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from sqlalchemy.orm import Session


@dataclass
class LocalRef:
    id: int
    etag: str | None = None
    updated: datetime | None = None


@dataclass
class RemoteEvent:
    """Một sự kiện Google đã đổi sang tên cột của tab_event. Dòng bị hủy có `status = cancelled`."""

    google_event_id: str
    etag: str | None
    updated: datetime | None
    status: str
    title: str = ""
    description: str | None = None
    location: str | None = None
    all_day: bool = False
    start_at: datetime | None = None
    end_at: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None
    timezone: str | None = None
    recurrence: list[str] | None = None
    recurring_event_id: str | None = None
    original_start_at: datetime | None = None
    attendees: list[dict] = field(default_factory=list)
    organizer_self: bool = True
    reminders_use_default: bool = True
    reminder_minutes: list[int] = field(default_factory=list)
    html_link: str | None = None


@dataclass
class LocalEvent:
    """Trạng thái mới nhất của một dòng tab_event lúc đẩy lên Google."""

    id: int
    title: str
    google_event_id: str | None
    google_etag: str | None
    google_calendar_id: str | None = "primary"
    description: str | None = None
    location: str | None = None
    all_day: bool = False
    start_at: datetime | None = None
    end_at: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None
    timezone: str | None = None
    status: str = "confirmed"
    recurrence: list[str] | None = None
    recurring_event_id: str | None = None
    original_start_at: datetime | None = None
    attendees: list[dict] = field(default_factory=list)
    remind_minutes: list[int] = field(default_factory=list)
    remind_source: str = "app"
    deleted: bool = False


@dataclass
class LocalTask:
    id: int
    title: str
    note: str | None
    status: str  # todo, done, cancelled
    priority: str
    due_date: date | None
    due_at: datetime | None
    google_task_id: str | None
    google_tasklist_id: str | None
    google_etag: str | None
    deleted: bool = False


class CalendarStore(Protocol):
    def find_by_google_id(
        self, session: Session, user_id: int, calendar_id: str, google_event_id: str
    ) -> LocalRef | None: ...

    def write_remote(
        self,
        session: Session,
        user_id: int,
        account_id: int,
        calendar_id: str,
        event: RemoteEvent,
        local_id: int | None,
    ) -> int: ...

    def mark_remote_cancelled(self, session: Session, user_id: int, local_id: int) -> None: ...

    def snapshot(self, session: Session, user_id: int, local_id: int) -> dict: ...

    def restore_snapshot(self, session: Session, user_id: int, local_id: int, data: dict) -> None: ...

    def delete_remote_rows(
        self, session: Session, user_id: int, account_id: int, keep_ids: set[int]
    ) -> int: ...

    def get_for_push(self, session: Session, user_id: int, local_id: int) -> LocalEvent | None: ...

    def save_push_result(
        self,
        session: Session,
        user_id: int,
        local_id: int,
        google_event_id: str,
        etag: str | None,
        updated: datetime | None,
    ) -> None: ...

    def set_sync_status(
        self, session: Session, user_id: int, local_id: int, status: str, error: str | None = None
    ) -> None: ...

    def on_disconnect(self, session: Session, user_id: int, keep_data: bool) -> None: ...


class TaskStore(Protocol):
    def get_for_push(self, session: Session, user_id: int, local_id: int) -> LocalTask | None: ...

    def save_push_result(
        self,
        session: Session,
        user_id: int,
        local_id: int,
        google_task_id: str | None,
        tasklist_id: str | None,
        etag: str | None,
        updated: datetime | None,
    ) -> None: ...

    def find_by_google_id(self, session: Session, user_id: int, google_task_id: str) -> LocalRef | None: ...

    def apply_remote_status(
        self,
        session: Session,
        user_id: int,
        local_id: int,
        completed: bool,
        completed_at: datetime | None,
        etag: str | None,
        updated: datetime | None,
    ) -> None: ...

    def mark_remote_deleted(self, session: Session, user_id: int, local_id: int) -> None: ...

    def set_sync_status(
        self, session: Session, user_id: int, local_id: int, status: str, error: str | None = None
    ) -> None: ...

    def list_unlinked(self, session: Session, user_id: int) -> list[int]: ...

    def on_disconnect(self, session: Session, user_id: int, keep_data: bool) -> None: ...


_calendar_store: CalendarStore | None = None
_task_store: TaskStore | None = None


def register_calendar_store(store: CalendarStore | None) -> None:
    global _calendar_store
    _calendar_store = store


def register_task_store(store: TaskStore | None) -> None:
    global _task_store
    _task_store = store


def calendar_store() -> CalendarStore | None:
    return _calendar_store


def task_store() -> TaskStore | None:
    return _task_store
