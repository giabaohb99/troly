from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Text
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
