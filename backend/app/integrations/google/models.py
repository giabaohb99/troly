"""Bảng Google (11 mục 3.12). Migration 0003_google."""

import uuid
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
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin

PACKS = ("base", "calendar", "tasks", "gmail", "contacts", "drive")
SERVICES = ("calendar", "tasks", "gmail", "contacts", "drive", "sheets")


class GoogleAccount(UserOwnedMixin, Base):
    __tablename__ = "tab_google_account"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_tab_google_account_user_id"),
        CheckConstraint("status IN ('active','reauth_required','revoked')", name="status"),
    )

    google_sub: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(CITEXT)
    granted_scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    enabled_packs: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{base}")
    refresh_token_enc: Mapped[bytes] = mapped_column(LargeBinary)
    access_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    key_version: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    last_error: Mapped[str | None] = mapped_column(Text)
    invalid_grant_count: Mapped[int] = mapped_column(Integer, server_default="0")
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GoogleOAuthState(UserOwnedMixin, Base):
    __tablename__ = "tab_google_oauth_state"

    state_hash: Mapped[str] = mapped_column(Text, unique=True)
    packs: Mapped[list[str]] = mapped_column(ARRAY(Text))
    code_verifier_enc: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(SmallInteger)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GoogleSyncState(UserOwnedMixin, Base):
    __tablename__ = "tab_google_sync_state"
    __table_args__ = (
        UniqueConstraint("google_account_id", "service", "resource_id"),
        CheckConstraint(
            "service IN ('calendar','tasks','gmail','contacts','drive','sheets')", name="service"
        ),
        CheckConstraint(
            "initial_sync_state IN ('pending','running','done','failed')", name="initial_sync_state"
        ),
        CheckConstraint("status IN ('ok','error','disabled')", name="status"),
        Index("ix_tab_google_sync_state_next_sync_at", "next_sync_at"),
        Index("ix_tab_google_sync_state_channel_expires_at", "channel_expires_at"),
    )

    google_account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tab_google_account.id", ondelete="CASCADE")
    )
    service: Mapped[str] = mapped_column(Text)
    resource_id: Mapped[str] = mapped_column(Text)
    sync_token: Mapped[str | None] = mapped_column(Text)
    history_id: Mapped[str | None] = mapped_column(Text)
    updated_min: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    needs_sync: Mapped[bool] = mapped_column(server_default=text("true"))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_full_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    initial_sync_state: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="ok")
    last_error: Mapped[str | None] = mapped_column(Text)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    channel_resource_id: Mapped[str | None] = mapped_column(Text)
    channel_token_hash: Mapped[str | None] = mapped_column(Text)
    channel_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GoogleOutbox(UserOwnedMixin, Base):
    __tablename__ = "tab_google_outbox"
    __table_args__ = (
        CheckConstraint("service IN ('calendar','tasks','gmail','drive','sheets')", name="service"),
        CheckConstraint(
            "op IN ('insert','patch','delete','draft_create','draft_send','file_upload','sheet_write')",
            name="op",
        ),
        CheckConstraint("local_type IN ('event','task','gmail_draft','file','export')", name="local_type"),
        CheckConstraint("status IN ('pending','processing','done','failed','conflict')", name="status"),
        Index(
            "uq_tab_google_outbox_waiting",
            "local_type",
            "local_id",
            "op",
            unique=True,
            postgresql_where=text("status IN ('pending','processing')"),
        ),
        Index(
            "ix_tab_google_outbox_pending",
            "status",
            "next_attempt_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    google_account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tab_google_account.id", ondelete="CASCADE")
    )
    service: Mapped[str] = mapped_column(Text)
    op: Mapped[str] = mapped_column(Text)
    local_type: Mapped[str] = mapped_column(Text)
    local_id: Mapped[int] = mapped_column(BigInteger)
    payload: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
