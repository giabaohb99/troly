from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin


class Event(UserOwnedMixin, Base):
    """Google Calendar làm gốc; sự kiện lặp lưu bản gốc có `recurrence` cộng ngoại lệ (11 mục 3.11)."""

    __tablename__ = "tab_event"
    __table_args__ = (
        CheckConstraint("status IN ('confirmed','tentative','cancelled')", name="status"),
        CheckConstraint("remind_source IN ('app','google')", name="remind_source"),
        CheckConstraint("source IN ('app','google')", name="source"),
        CheckConstraint(
            "sync_status IN ('local_only','pending','synced','conflict','error')", name="sync_status"
        ),
        CheckConstraint(
            "(all_day AND start_date IS NOT NULL AND end_date > start_date) "
            "OR (NOT all_day AND start_at IS NOT NULL AND end_at >= start_at)",
            name="time_range",
        ),
        Index("ix_tab_event_start", "user_id", "start_at", postgresql_where=text("deleted_at IS NULL")),
        Index(
            "ix_tab_event_recurring",
            "user_id",
            postgresql_where=text("recurrence IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index("ix_tab_event_recurring_event_id", "user_id", "recurring_event_id"),
        Index(
            "uq_tab_event_google",
            "user_id",
            "google_calendar_id",
            "google_event_id",
            unique=True,
            postgresql_where=text("google_event_id IS NOT NULL"),
        ),
    )

    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    all_day: Mapped[bool] = mapped_column(Boolean, server_default="false")
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    timezone: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="confirmed")
    recurrence: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    recurring_event_id: Mapped[str | None] = mapped_column(Text)
    original_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attendees: Mapped[list] = mapped_column(JSONB, server_default="[]")
    remind_minutes: Mapped[list[int]] = mapped_column(ARRAY(Integer), server_default="{}")
    remind_source: Mapped[str] = mapped_column(Text, server_default="app")
    is_alarm: Mapped[bool] = mapped_column(Boolean, server_default="false")
    # Google `organizer.self`; sự kiện người khác mời chỉ đổi được nguồn nhắc (31).
    is_organizer: Mapped[bool] = mapped_column(Boolean, server_default="true")
    source: Mapped[str] = mapped_column(Text, server_default="app")
    task_id: Mapped[int | None] = mapped_column(BigInteger)
    google_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_google_account.id", ondelete="SET NULL")
    )
    google_calendar_id: Mapped[str | None] = mapped_column(Text)
    google_event_id: Mapped[str | None] = mapped_column(Text)
    google_etag: Mapped[str | None] = mapped_column(Text)
    google_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    google_html_link: Mapped[str | None] = mapped_column(Text)
    sync_status: Mapped[str] = mapped_column(Text, server_default="local_only")
    sync_error: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
