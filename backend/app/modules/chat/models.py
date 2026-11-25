from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin


class Conversation(UserOwnedMixin, Base):
    """Phiên chat đặt tên (QĐ-51): mở lại được, không tách theo ngày. `local_date` là ngày mở phiên."""

    __tablename__ = "tab_conversation"
    __table_args__ = (
        CheckConstraint("title_source IN ('auto','user')", name="title_source"),
        Index(
            "ix_tab_conversation_user_recent",
            "user_id",
            text("pinned DESC"),
            text("last_message_at DESC"),
            text("id DESC"),
        ),
    )

    local_date: Mapped[date] = mapped_column(Date)
    title: Mapped[str | None] = mapped_column(Text)
    # auto: máy đặt (agent AI đặt lại được); user: người dùng đổi tên, máy không ghi đè.
    title_source: Mapped[str] = mapped_column(Text, server_default="auto")
    pinned: Mapped[bool] = mapped_column(Boolean, server_default="false")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str | None] = mapped_column(Text)
    summary_upto_id: Mapped[int | None] = mapped_column(BigInteger)
    last_prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    compacted_count: Mapped[int] = mapped_column(Integer, server_default="0")
    # Đã tóm cho lần phiên ngủ hiện tại (job summarize_idle_conversations); tin mới đặt lại false.
    day_summary_done: Mapped[bool] = mapped_column(Boolean, server_default="false")
    message_count: Mapped[int] = mapped_column(Integer, server_default="0")


class Message(UserOwnedMixin, Base):
    __tablename__ = "tab_message"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant','system')", name="role"),
        CheckConstraint("status IN ('complete','failed')", name="status"),
        Index("ix_tab_message_conversation", "conversation_id", "id"),
        Index(
            "uq_tab_message_client_id",
            "user_id",
            "client_message_id",
            unique=True,
            postgresql_where=text("client_message_id IS NOT NULL"),
        ),
        Index(
            "ix_tab_message_search",
            "search_vector",
            postgresql_using="gin",
            postgresql_where=text("hidden = false"),
        ),
        Index(
            "ix_tab_message_third_party",
            "created_at",
            postgresql_where=text("contains_third_party AND redacted_at IS NULL"),
        ),
    )

    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tab_conversation.id", ondelete="CASCADE")
    )
    turn_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True))
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[list] = mapped_column(JSONB)
    text: Mapped[str | None] = mapped_column(Text)
    hidden: Mapped[bool] = mapped_column(Boolean, server_default="false")
    model: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default="complete")
    client_message_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    attachment_file_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), server_default="{}")
    actions: Mapped[list | None] = mapped_column(JSONB)
    contains_third_party: Mapped[bool] = mapped_column(Boolean, server_default="false")
    # Lượt xong mà app đã ngắt SSE trước sự kiện kết thúc: notice `chat_done` báo cho máy (bản 0008).
    notify_done: Mapped[bool] = mapped_column(Boolean, server_default="false")
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ai_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_ai_run.id", ondelete="SET NULL")
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('troly_vn', coalesce(text,''))", persisted=True)
    )


class PendingAction(UserOwnedMixin, Base):
    __tablename__ = "tab_pending_action"
    __table_args__ = (
        CheckConstraint("status IN ('pending','done','failed','rejected','expired')", name="status"),
        Index("ix_tab_pending_action_user_status", "user_id", "status", text("created_at DESC")),
        Index(
            "ix_tab_pending_action_expiring",
            "expires_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    conversation_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_conversation.id", ondelete="SET NULL")
    )
    message_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_message.id", ondelete="SET NULL")
    )
    tool_name: Mapped[str] = mapped_column(Text)
    input: Mapped[dict] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    details: Mapped[list] = mapped_column(JSONB, server_default="[]")
    danger: Mapped[bool] = mapped_column(Boolean, server_default="false")
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
