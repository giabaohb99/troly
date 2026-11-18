from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin

APPS = ("zalo", "telegram", "messenger", "sms", "gmail", "other")
RULE_KINDS = (
    "vip_sender",
    "urgent_keyword",
    "muted_sender",
    "muted_keyword",
    "muted_app",
    "private_conversation",
)


class InboxMessage(UserOwnedMixin, Base):
    __tablename__ = "tab_inbox_message"
    __table_args__ = (
        CheckConstraint("source IN ('notification','gmail')", name="source"),
        CheckConstraint(f"app IN {APPS}", name="app"),
        CheckConstraint("status IN ('new','seen','done')", name="status"),
        CheckConstraint("importance IN ('normal','important')", name="importance"),
        CheckConstraint("char_length(text) <= 4000", name="text_len"),
        Index("uq_tab_inbox_message_dedupe", "user_id", "dedupe_hash", unique=True),
        Index(
            "uq_tab_inbox_message_external",
            "user_id",
            "external_id",
            unique=True,
            postgresql_where=text("source = 'gmail'"),
        ),
        Index("ix_tab_inbox_message_conversation", "user_id", "conversation_key", text("posted_at DESC")),
        Index("ix_tab_inbox_message_status", "user_id", "status", "importance", text("posted_at DESC")),
        Index("ix_tab_inbox_message_search", "search_vector", postgresql_using="gin"),
    )

    source: Mapped[str] = mapped_column(Text)
    app: Mapped[str] = mapped_column(Text)
    app_package: Mapped[str | None] = mapped_column(Text)
    device_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_device.id", ondelete="SET NULL")
    )
    device_event_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_device_event.id", ondelete="SET NULL")
    )
    sender: Mapped[str | None] = mapped_column(Text)
    sender_key: Mapped[str] = mapped_column(Text)
    conversation_key: Mapped[str] = mapped_column(Text)
    conversation_title: Mapped[str | None] = mapped_column(Text)
    is_group: Mapped[bool] = mapped_column(Boolean, server_default="false")
    subject: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    hidden_content: Mapped[bool] = mapped_column(Boolean, server_default="false")
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="new")
    importance: Mapped[str] = mapped_column(Text, server_default="normal")
    importance_reason: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)
    thread_ref: Mapped[str | None] = mapped_column(Text)
    labels: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    dedupe_hash: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('troly_vn', coalesce(sender,'') || ' ' || coalesce(conversation_title,'') || ' ' "
            "|| coalesce(subject,'') || ' ' || text)",
            persisted=True,
        ),
    )


class InboxRule(UserOwnedMixin, Base):
    __tablename__ = "tab_inbox_rule"
    __table_args__ = (
        CheckConstraint(f"kind IN {RULE_KINDS}", name="kind"),
        Index(
            "uq_tab_inbox_rule_value",
            "user_id",
            "kind",
            text("lower(value)"),
            text("coalesce(app, '')"),
            unique=True,
        ),
    )

    kind: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    app: Mapped[str | None] = mapped_column(Text)
