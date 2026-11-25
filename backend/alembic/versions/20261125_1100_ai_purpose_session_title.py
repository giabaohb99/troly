"""QĐ-51: lượt AI đặt tên phiên chat (`session_title`, Haiku) ghi vào tab_ai_run.

Revision ID: 0017_ai_session_title
Revises: 0016_chat_sessions
Create Date: 2026-11-25 11:00
"""

from alembic import op

revision = "0017_ai_session_title"
down_revision = "0016_chat_sessions"
branch_labels = None
depends_on = None

OLD = "'chat','compaction','bank_extract','file_extract','trip_extract','trip_evaluate','eval'"


def upgrade() -> None:
    op.execute("ALTER TABLE tab_ai_run DROP CONSTRAINT ck_tab_ai_run_purpose")
    op.execute(
        f"ALTER TABLE tab_ai_run ADD CONSTRAINT ck_tab_ai_run_purpose CHECK (purpose IN ({OLD},'session_title'))"
    )


def downgrade() -> None:
    op.execute("DELETE FROM tab_ai_run WHERE purpose = 'session_title'")
    op.execute("ALTER TABLE tab_ai_run DROP CONSTRAINT ck_tab_ai_run_purpose")
    op.execute(f"ALTER TABLE tab_ai_run ADD CONSTRAINT ck_tab_ai_run_purpose CHECK (purpose IN ({OLD}))")
