"""QĐ-60: việc giao cho Claude Code chạy trên VPS (tab_claude_job).

Revision ID: 0022_claude_job
Revises: 0021_ai_memory_extract
Create Date: 2026-11-25 23:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0022_claude_job"
down_revision = "0021_ai_memory_extract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tab_claude_job",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=True),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("context_note", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("runs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("turns", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 4), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'waiting', 'done', 'failed', 'cancelled')",
            name=op.f("ck_tab_claude_job_status"),
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["tab_conversation.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["tab_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tab_claude_job_user_id", "tab_claude_job", ["user_id"])
    op.create_index("ix_tab_claude_job_status", "tab_claude_job", ["status", "id"])


def downgrade() -> None:
    op.drop_table("tab_claude_job")
