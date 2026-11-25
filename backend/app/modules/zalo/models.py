from datetime import datetime

from sqlalchemy import DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin


class ZaloAccount(UserOwnedMixin, Base):
    """Tài khoản Zalo đã nối qua zalo-bridge (QĐ-52). Bridge chạy một tài khoản: sự kiện vào người dùng này."""

    __tablename__ = "tab_zalo_account"
    __table_args__ = (UniqueConstraint("user_id"),)

    state: Mapped[str] = mapped_column(Text, server_default="logged_out")
    zalo_uid: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
