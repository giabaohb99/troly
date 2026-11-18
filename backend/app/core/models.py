"""Bảng của core (11 mục 3.3)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UserOwnedMixin


class User(TimestampMixin, Base):
    __tablename__ = "tab_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, server_default="Asia/Ho_Chi_Minh")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(UserOwnedMixin, Base):
    __tablename__ = "tab_auth_session"
    __table_args__ = (
        Index(
            "ix_tab_auth_session_previous_token_hash",
            "previous_token_hash",
            postgresql_where=text("previous_token_hash IS NOT NULL"),
        ),
    )

    refresh_token_hash: Mapped[str] = mapped_column(Text, unique=True)
    label: Mapped[str | None] = mapped_column(Text)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Ân hạn khi mã vừa xoay bị dùng lại (core/auth.refresh): hash mã liền trước, lúc xoay, và mã hiện tại
    # mã hóa Fernet để trả lại đúng cặp kế tiếp. Ngoài cửa sổ ân hạn thì mã cũ là 401 như cũ.
    previous_token_hash: Mapped[str | None] = mapped_column(Text)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    current_token_key_version: Mapped[int | None] = mapped_column(SmallInteger)


class JobQueue(UserOwnedMixin, Base):
    __tablename__ = "tab_job_queue"
    __table_args__ = (
        CheckConstraint("status IN ('pending','processing','done','failed','cancelled')", name="status"),
        Index(
            "ix_tab_job_queue_pending",
            "status",
            "next_attempt_at",
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "uq_tab_job_queue_dedupe",
            "user_id",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status IN ('pending','processing')"),
        ),
    )

    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    max_attempts: Mapped[int] = mapped_column(SmallInteger, server_default="3")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str | None] = mapped_column(Text)


class JobSchedule(Base):
    __tablename__ = "tab_job_schedule"
    __table_args__ = (CheckConstraint("last_status IN ('ok','error','skipped')", name="last_status"),)

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_duration_ms: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )


class JobRun(Base):
    __tablename__ = "tab_job_run"
    __table_args__ = (
        CheckConstraint("status IN ('running','ok','error')", name="status"),
        Index("ix_tab_job_run_name_started", "job_name", text("started_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text)
    items_processed: Mapped[int] = mapped_column(Integer, server_default="0")
    detail: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)


class ClientLog(Base):
    """Lỗi giao diện và lỗi gọi API do app gửi về (QĐ-30), giữ 30 ngày.

    user_id rỗng được: app báo cả lỗi xảy ra trước khi đăng nhập.
    """

    __tablename__ = "tab_client_log"
    __table_args__ = (
        CheckConstraint("level IN ('error','warn','info')", name="level"),
        Index("ix_tab_client_log_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tab_user.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    device_id: Mapped[int | None] = mapped_column(BigInteger)
    level: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    screen: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSONB)
    app_version: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
