"""Địa phương của điểm dừng và tọa độ từ OpenStreetMap (sửa lỗi dẫn đường tới quán trùng tên ở tỉnh khác).

Revision ID: 0012_trip_stop_area
Revises: 0011_gmail_draft
Create Date: 2026-11-20 09:00
"""

from alembic import op

revision = "0012_trip_stop_area"
down_revision = "0011_gmail_draft"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tab_trip_stop ADD COLUMN area text")
    op.execute("ALTER TABLE tab_trip_stop DROP CONSTRAINT ck_tab_trip_stop_coord_source")
    op.execute(
        "ALTER TABLE tab_trip_stop ADD CONSTRAINT ck_tab_trip_stop_coord_source "
        "CHECK (coord_source IN ('user','google','osm'))"
    )


def downgrade() -> None:
    op.execute("UPDATE tab_trip_stop SET coord_source = 'user' WHERE coord_source = 'osm'")
    op.execute("ALTER TABLE tab_trip_stop DROP CONSTRAINT ck_tab_trip_stop_coord_source")
    op.execute(
        "ALTER TABLE tab_trip_stop ADD CONSTRAINT ck_tab_trip_stop_coord_source "
        "CHECK (coord_source IN ('user','google'))"
    )
    op.execute("ALTER TABLE tab_trip_stop DROP COLUMN IF EXISTS area")
