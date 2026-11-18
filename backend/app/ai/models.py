"""Bảng tab_ai_run: mỗi lần gọi Claude một dòng (11 mục 3.7, 20 mục 4).

Tên Base và SessionLocal theo core/db.py của agent kiến trúc; migration do agent kiến trúc tạo.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.ai.client import RunRecord
from app.core.db import Base, SessionLocal


class AiRun(Base):
    __tablename__ = "tab_ai_run"
    __table_args__ = (
        Index("ix_tab_ai_run_user_created", "user_id", "created_at"),
        Index("ix_tab_ai_run_created", "created_at"),
        CheckConstraint(
            "purpose IN ('chat','compaction','bank_extract','file_extract',"
            "'trip_extract','trip_evaluate','eval')",
            name="purpose",
        ),
        CheckConstraint("mode IN ('chat','think','research','summary')", name="mode"),
        CheckConstraint("rate_card IN ('le_100k','gt_100k')", name="rate_card"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tab_user.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    mode: Mapped[str | None] = mapped_column(Text)
    effort: Mapped[str | None] = mapped_column(Text)
    conversation_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_conversation.id", ondelete="SET NULL")
    )
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_5m_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_1h_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    web_search_requests: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    rate_card: Mapped[str | None] = mapped_column(Text)
    stop_reason: Mapped[str | None] = mapped_column(Text)
    refusal_category: Mapped[str | None] = mapped_column(Text)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DbRunRecorder:
    """Ghi tab_ai_run bằng phiên DB riêng, commit ngay (không dính giao dịch của lượt chat)."""

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    def record(self, rec: RunRecord) -> int | None:
        u = rec.usage
        with self.session_factory() as session:
            row = AiRun(
                user_id=rec.user_id,
                purpose=rec.purpose,
                model=rec.model,
                mode=rec.mode,
                effort=rec.effort,
                conversation_id=rec.conversation_id,
                input_tokens=u.input_tokens,
                cache_write_5m_tokens=u.cache_write_5m_tokens,
                cache_write_1h_tokens=u.cache_write_1h_tokens,
                cache_read_tokens=u.cache_read_tokens,
                output_tokens=u.output_tokens,
                web_search_requests=u.web_search_requests,
                cost_usd=rec.cost_usd,
                rate_card=rec.rate_card,
                stop_reason=rec.stop_reason,
                refusal_category=rec.refusal_category,
                fallback_used=rec.fallback_used,
                latency_ms=rec.latency_ms,
                request_id=rec.request_id,
                error_code=rec.error_code,
            )
            session.add(row)
            session.commit()
            return row.id
