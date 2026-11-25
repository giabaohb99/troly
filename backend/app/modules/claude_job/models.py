from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin

STATUSES = ("queued", "running", "waiting", "done", "failed", "cancelled")


class ClaudeJob(UserOwnedMixin, Base):
    """Việc giao cho Claude Code chạy trên VPS (QĐ-60). Lệnh lấy nguyên văn câu người dùng gõ; kết quả, câu hỏi báo
    về đoạn chat `conversation_id`."""

    __tablename__ = "tab_claude_job"
    __table_args__ = (
        CheckConstraint(f"status IN {STATUSES}", name="status"),
        Index("ix_tab_claude_job_status", "status", "id"),
    )

    conversation_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_conversation.id", ondelete="SET NULL")
    )
    request_text: Mapped[str] = mapped_column(Text)
    context_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    # Lượt tiếp theo người dùng trả lời câu hỏi của Claude (status queued + answer_text) thì chạy --resume.
    answer_text: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(Text)
    question: Mapped[str | None] = mapped_column(Text)
    result_text: Mapped[str | None] = mapped_column(Text)
    error_text: Mapped[str | None] = mapped_column(Text)
    runs: Mapped[int] = mapped_column(Integer, server_default="0")
    turns: Mapped[int] = mapped_column(Integer, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
