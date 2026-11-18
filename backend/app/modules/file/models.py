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
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin

PURPOSES = ("chat_attachment", "voice", "document", "trip_source", "trip_export", "report_export", "other")


class File(UserOwnedMixin, Base):
    __tablename__ = "tab_file"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint(f"purpose IN {PURPOSES}", name="purpose"),
        CheckConstraint("status IN ('pending_upload','ready','deleted')", name="status"),
        CheckConstraint(
            "extract_status IN ('none','pending','done','failed','skipped')", name="extract_status"
        ),
        Index(
            "ix_tab_file_ready",
            "user_id",
            "purpose",
            text("created_at DESC"),
            postgresql_where=text("status = 'ready'"),
        ),
        Index(
            "ix_tab_file_extract_pending",
            "extract_status",
            postgresql_where=text("extract_status = 'pending'"),
        ),
    )

    r2_key: Mapped[str] = mapped_column(Text, unique=True)
    original_name: Mapped[str | None] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending_upload")
    extract_status: Mapped[str] = mapped_column(Text, server_default="none")
    drive_file_id: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FileText(Base):
    __tablename__ = "tab_file_text"
    __table_args__ = (
        CheckConstraint("method IN ('docx','pdf_text','ai_ocr','plain')", name="method"),
        Index("ix_tab_file_text_search", "search_vector", postgresql_using="gin"),
    )

    file_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tab_file.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tab_user.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('troly_vn', content)", persisted=True)
    )
