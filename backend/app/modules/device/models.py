from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin


class Device(UserOwnedMixin, Base):
    __tablename__ = "tab_device"
    __table_args__ = (CheckConstraint("platform IN ('android')", name="platform"),)

    name: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(Text, server_default="android")
    manufacturer: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    os_version: Mapped[str | None] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    token_prefix: Mapped[str] = mapped_column(Text)
    app_version_code: Mapped[int | None] = mapped_column(Integer)
    app_version_name: Mapped[str | None] = mapped_column(Text)
    default_sms_package: Mapped[str | None] = mapped_column(Text)
    notification_access: Mapped[bool | None] = mapped_column(Boolean)
    listener_connected: Mapped[bool | None] = mapped_column(Boolean)
    notifications_enabled: Mapped[bool | None] = mapped_column(Boolean)
    exact_alarm_allowed: Mapped[bool | None] = mapped_column(Boolean)
    battery_optimization_ignored: Mapped[bool | None] = mapped_column(Boolean)
    queue_size: Mapped[int | None] = mapped_column(Integer)
    otp_blocked_today: Mapped[int | None] = mapped_column(Integer)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    silent_warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ListenedApp(UserOwnedMixin, Base):
    __tablename__ = "tab_listened_app"
    __table_args__ = (
        UniqueConstraint("user_id", "package_name"),
        CheckConstraint("purpose IN ('expense','inbox')", name="purpose"),
        CheckConstraint(
            "parser IN ('vcb','tcb','momo','zalo','telegram','messenger','sms','generic')", name="parser"
        ),
    )

    package_name: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    parser: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    is_default: Mapped[bool] = mapped_column(Boolean, server_default="false")


class DeviceEvent(UserOwnedMixin, Base):
    __tablename__ = "tab_device_event"
    __table_args__ = (
        UniqueConstraint("device_id", "client_event_id"),
        CheckConstraint("kind IN ('notification','reminder_action')", name="kind"),
        CheckConstraint("status IN ('pending','processing','done','ignored','failed')", name="status"),
        CheckConstraint(
            "result_kind IN ('expense','inbox_message','transfer_merged','task_updated','none')",
            name="result_kind",
        ),
        CheckConstraint("kind <> 'notification' OR app_package IS NOT NULL", name="app_package"),
        Index(
            "ix_tab_device_event_pending",
            "status",
            "next_attempt_at",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_tab_device_event_received", "user_id", text("received_at DESC")),
    )

    device_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tab_device.id", ondelete="CASCADE"))
    client_event_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(Text)
    app_package: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_kind: Mapped[str | None] = mapped_column(Text)
    result_id: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)
