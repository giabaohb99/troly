"""QĐ-59: lượt AI rút trí nhớ sau mỗi câu trả lời (`memory_extract`, Haiku) ghi vào tab_ai_run.

Revision ID: 0021_ai_memory_extract
Revises: 0020_ai_run_mcp
Create Date: 2026-11-25 22:00
"""

from alembic import op

revision = "0021_ai_memory_extract"
down_revision = "0020_ai_run_mcp"
branch_labels = None
depends_on = None

OLD = "'chat','compaction','bank_extract','file_extract','trip_extract','trip_evaluate','eval','session_title'"


def upgrade() -> None:
    op.execute("ALTER TABLE tab_ai_run DROP CONSTRAINT ck_tab_ai_run_purpose")
    op.execute(
        f"ALTER TABLE tab_ai_run ADD CONSTRAINT ck_tab_ai_run_purpose CHECK (purpose IN ({OLD},'memory_extract'))"
    )


def downgrade() -> None:
    op.execute("DELETE FROM tab_ai_run WHERE purpose = 'memory_extract'")
    op.execute("ALTER TABLE tab_ai_run DROP CONSTRAINT ck_tab_ai_run_purpose")
    op.execute(f"ALTER TABLE tab_ai_run ADD CONSTRAINT ck_tab_ai_run_purpose CHECK (purpose IN ({OLD}))")
