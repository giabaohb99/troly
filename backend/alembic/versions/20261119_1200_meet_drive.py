"""Meet trong sự kiện lịch, link Drive của tệp (5-01).

Revision ID: 0006_meet_drive
Revises: 0005_trip
Create Date: 2026-11-19 12:00
"""

from alembic import op

revision = "0006_meet_drive"
down_revision = "0005_trip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tab_event ADD COLUMN meet_url text")
    op.execute("ALTER TABLE tab_file ADD COLUMN drive_web_view_link text")


def downgrade() -> None:
    op.execute("ALTER TABLE tab_file DROP COLUMN IF EXISTS drive_web_view_link")
    op.execute("ALTER TABLE tab_event DROP COLUMN IF EXISTS meet_url")
