from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UserOwnedMixin

ACCOUNTS = ("vcb", "tcb", "momo", "cash", "card", "other")


class ExpenseCategory(UserOwnedMixin, Base):
    __tablename__ = "tab_expense_category"
    __table_args__ = (
        CheckConstraint("kind IN ('expense','income')", name="kind"),
        Index("uq_tab_expense_category_name", "user_id", text("lower(name)"), unique=True),
    )

    name: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    kind: Mapped[str] = mapped_column(Text, server_default="expense")
    sort_order: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    is_archived: Mapped[bool] = mapped_column(Boolean, server_default="false")


class Expense(UserOwnedMixin, Base):
    __tablename__ = "tab_expense"
    __table_args__ = (
        CheckConstraint("amount_vnd > 0", name="amount_positive"),
        CheckConstraint("kind IN ('expense','income','transfer')", name="kind"),
        CheckConstraint(f"account IN {ACCOUNTS}", name="account"),
        CheckConstraint(f"to_account IS NULL OR to_account IN {ACCOUNTS}", name="to_account"),
        CheckConstraint("account_last4 IS NULL OR account_last4 ~ '^[0-9]{4}$'", name="account_last4"),
        CheckConstraint(
            "to_account_last4 IS NULL OR to_account_last4 ~ '^[0-9]{4}$'", name="to_account_last4"
        ),
        CheckConstraint("kind <> 'transfer' OR to_account IS NOT NULL", name="transfer_target"),
        CheckConstraint("source IN ('chat','bank_notification','manual')", name="source"),
        CheckConstraint("parse_confidence IS NULL OR parse_confidence BETWEEN 0 AND 1", name="confidence"),
        Index(
            "uq_tab_expense_source_ref",
            "user_id",
            "source_ref",
            unique=True,
            postgresql_where=text("source_ref IS NOT NULL"),
        ),
        Index(
            "uq_tab_expense_peer_ref",
            "user_id",
            "transfer_peer_ref",
            unique=True,
            postgresql_where=text("transfer_peer_ref IS NOT NULL"),
        ),
        Index(
            "ix_tab_expense_spent",
            "user_id",
            text("spent_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_tab_expense_review", "user_id", postgresql_where=text("needs_review AND deleted_at IS NULL")
        ),
    )

    amount_vnd: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(Text)
    account: Mapped[str] = mapped_column(Text)
    account_last4: Mapped[str | None] = mapped_column(Text)
    to_account: Mapped[str | None] = mapped_column(Text)
    to_account_last4: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_expense_category.id", ondelete="SET NULL")
    )
    merchant: Mapped[str | None] = mapped_column(Text)
    place: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    spent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(Text)
    transfer_peer_ref: Mapped[str | None] = mapped_column(Text)
    device_event_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tab_device_event.id", ondelete="SET NULL")
    )
    parser: Mapped[str | None] = mapped_column(Text)
    parse_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    needs_review: Mapped[bool] = mapped_column(Boolean, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
