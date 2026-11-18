from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin


class Task(UserOwnedMixin, Base):
    """Việc không giờ đi Google Tasks; việc có giờ sinh sự kiện lịch qua `event_id` (11 mục 3.11)."""

    __tablename__ = "tab_task"
    __table_args__ = (
        CheckConstraint("char_length(title) <= 1024", name="title_len"),
        CheckConstraint("note IS NULL OR char_length(note) <= 8000", name="note_len"),
        CheckConstraint("status IN ('todo','done','cancelled')", name="status"),
        CheckConstraint("priority IN ('low','normal','high')", name="priority"),
        CheckConstraint("due_date IS NULL OR due_at IS NULL", name="due_one"),
        CheckConstraint(
            "completed_source IS NULL OR completed_source IN ('app','google')", name="completed_source"
        ),
        CheckConstraint("source IN ('app','chat')", name="source"),
        CheckConstraint(
            "sync_status IN ('local_only','pending','synced','remote_deleted','error')", name="sync_status"
        ),
        Index(
            "uq_tab_task_google",
            "user_id",
            "google_task_id",
            unique=True,
            postgresql_where=text("google_task_id IS NOT NULL"),
        ),
        Index("ix_tab_task_open", "user_id", "status", postgresql_where=text("deleted_at IS NULL")),
    )

    title: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="todo")
    priority: Mapped[str] = mapped_column(Text, server_default="normal")
    due_date: Mapped[date | None] = mapped_column(Date)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_source: Mapped[str | None] = mapped_column(Text)
    event_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tab_event.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(Text, server_default="app")
    google_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_google_account.id", ondelete="SET NULL")
    )
    google_tasklist_id: Mapped[str | None] = mapped_column(Text)
    google_task_id: Mapped[str | None] = mapped_column(Text)
    google_etag: Mapped[str | None] = mapped_column(Text)
    google_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[str] = mapped_column(Text, server_default="local_only")
    sync_error: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
