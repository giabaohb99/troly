"""QĐ-56: ghi máy chủ MCP gắn vào từng lượt gọi Claude để đo chi phí (`c<connector_id>`).

Revision ID: 0020_ai_run_mcp
Revises: 0019_zalo
Create Date: 2026-11-25 20:00
"""

from alembic import op

revision = "0020_ai_run_mcp"
down_revision = "0019_zalo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tab_ai_run ADD COLUMN mcp_servers_used text[]")


def downgrade() -> None:
    op.execute("ALTER TABLE tab_ai_run DROP COLUMN IF EXISTS mcp_servers_used")
