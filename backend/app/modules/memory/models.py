from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin

PROFILE_MAX_CHARS = 8000


class ProfileMemory(UserOwnedMixin, Base):
    __tablename__ = "tab_profile_memory"
    __table_args__ = (
        UniqueConstraint("user_id"),
        CheckConstraint(f"char_length(content) <= {PROFILE_MAX_CHARS}", name="content_len"),
        CheckConstraint("updated_by IN ('user','ai')", name="updated_by"),
    )

    content: Mapped[str] = mapped_column(Text, server_default="")
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    updated_by: Mapped[str] = mapped_column(Text, server_default="user")


class ProfileMemoryRevision(Base):
    __tablename__ = "tab_profile_memory_revision"
    __table_args__ = (
        UniqueConstraint("user_id", "version"),
        CheckConstraint("changed_by IN ('user','ai')", name="changed_by"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tab_user.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Note(UserOwnedMixin, Base):
    __tablename__ = "tab_note"
    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title_len"),
        CheckConstraint("char_length(body) <= 20000", name="body_len"),
        CheckConstraint("source IN ('user','ai')", name="source"),
        Index("ix_tab_note_search", "search_vector", postgresql_using="gin"),
        Index("ix_tab_note_tags", "tags", postgresql_using="gin"),
    )

    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, server_default="")
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    source: Mapped[str] = mapped_column(Text, server_default="user")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('troly_vn', coalesce(title,'') || ' ' || coalesce(body,'') || ' ' "
            "|| troly_join_tags(tags))",
            persisted=True,
        ),
    )
