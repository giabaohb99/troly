"""Lưu trữ chuyến đi (QĐ-42): chuyến đã đi nằm ở mục Đã đi.

Revision ID: 0009_trip_archive
Revises: 0008_chat_notify
Create Date: 2026-11-19 19:00
"""

from alembic import op

revision = "0009_trip_archive"
down_revision = "0008_chat_notify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tab_trip ADD COLUMN archived_at timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE tab_trip DROP COLUMN IF EXISTS archived_at")
