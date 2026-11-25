"""QĐ-60: tệp thành phẩm của việc Claude trên VPS (tab_claude_job.files).

Revision ID: 0023_claude_job_files
Revises: 0022_claude_job
Create Date: 2026-11-25 23:30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023_claude_job_files"
down_revision = "0022_claude_job"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tab_claude_job",
        sa.Column("files", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("tab_claude_job", "files")
