"""Bảng kết nối MCP chung (QĐ-56). Migration 0018_connectors."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UserOwnedMixin

AUTHS = ("oauth", "api_key", "none")
STATUSES = ("not_connected", "connected", "reauth_required", "error")


class ConnectorClient(TimestampMixin, Base):
    """Bảng hệ thống: client đăng ký động (RFC 7591) một lần cho mỗi máy chủ ủy quyền và redirect_uri."""

    __tablename__ = "tab_connector_client"
    __table_args__ = (UniqueConstraint("issuer", "redirect_uri"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    issuer: Mapped[str] = mapped_column(Text)
    redirect_uri: Mapped[str] = mapped_column(Text)
    client_id: Mapped[str] = mapped_column(Text)
    client_secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    key_version: Mapped[int | None] = mapped_column(SmallInteger)
    auth_method: Mapped[str] = mapped_column(Text)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Connector(UserOwnedMixin, Base):
    __tablename__ = "tab_connector"
    __table_args__ = (
        UniqueConstraint("user_id", "url"),
        CheckConstraint("auth IN ('oauth','api_key','none')", name="auth"),
        CheckConstraint("status IN ('not_connected','connected','reauth_required','error')", name="status"),
    )

    name: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    auth: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="not_connected")
    account_label: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    # Công cụ ghi người dùng đã bật (mặc định rỗng); bot gọi công cụ ghi luôn qua thẻ duyệt.
    write_tools_enabled: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    tools_count: Mapped[int | None] = mapped_column(Integer)
    issuer: Mapped[str | None] = mapped_column(Text)
    as_metadata: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'"))
    client_row_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_connector_client.id", ondelete="SET NULL")
    )
    scope: Mapped[str | None] = mapped_column(Text)
    access_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    api_key_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    key_version: Mapped[int | None] = mapped_column(SmallInteger)
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConnectorOAuthState(UserOwnedMixin, Base):
    """State dùng một lần, 10 phút; lưu hash."""

    __tablename__ = "tab_connector_oauth_state"

    connector_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tab_connector.id", ondelete="CASCADE"))
    state_hash: Mapped[str] = mapped_column(Text, unique=True)
    code_verifier_enc: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(SmallInteger)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
