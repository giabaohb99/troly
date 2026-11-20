"""Bảng module booking (QĐ-49). Migration 0013_booking."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    REAL,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin

KINDS = ("hotel", "flight", "bus", "train", "other")
STATUSES = ("confirmed", "changed", "cancelled")
CALENDAR_STATES = ("added", "undone", "none")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ",".join(f"'{v}'" for v in values) + ")"


class Booking(UserOwnedMixin, Base):
    """Một đặt chỗ đọc từ thư. `status` theo thư; `calendar_state` là việc app đã tự thêm vào Lịch hay chưa."""

    __tablename__ = "tab_booking"
    __table_args__ = (
        CheckConstraint(_in("kind", KINDS), name="kind"),
        CheckConstraint(_in("status", STATUSES), name="status"),
        CheckConstraint(_in("calendar_state", CALENDAR_STATES), name="calendar_state"),
        Index("ix_tab_booking_user_start", "user_id", "start_date", "start_at"),
        Index(
            "uq_tab_booking_ref",
            "user_id",
            "kind",
            "provider",
            "booking_ref",
            unique=True,
            postgresql_where=text("booking_ref IS NOT NULL"),
        ),
    )

    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    calendar_state: Mapped[str] = mapped_column(Text, server_default="none")
    title: Mapped[str] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    booking_ref: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    area: Mapped[str | None] = mapped_column(Text)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[date | None] = mapped_column(Date)
    guests: Mapped[int | None] = mapped_column(SmallInteger)
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(Text)
    cancellation: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(REAL)
    event_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tab_event.id", ondelete="SET NULL"))
    end_event_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_event.id", ondelete="SET NULL")
    )
    # Tiêu đề và giờ của sự kiện lúc app tạo, để Hoàn tác biết người dùng đã sửa hay chưa.
    event_snapshot: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    trip_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tab_trip.id", ondelete="SET NULL"))
    trip_stop_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_trip_stop.id", ondelete="SET NULL")
    )
    source_message_id: Mapped[str] = mapped_column(Text)
    source_thread_id: Mapped[str | None] = mapped_column(Text)


class BookingMail(UserOwnedMixin, Base):
    """Thư đã xét để không gọi Claude lại: là đặt chỗ hay không."""

    __tablename__ = "tab_booking_mail"
    __table_args__ = (
        UniqueConstraint("user_id", "message_id"),
        CheckConstraint("outcome IN ('booking','ignored')", name="outcome"),
    )

    message_id: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    booking_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_booking.id", ondelete="SET NULL")
    )
