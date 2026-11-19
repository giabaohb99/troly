"""QĐ-42: hộp tin bỏ Telegram, Messenger; tắt hai app này cho người dùng hiện có.

Tin cũ không xóa, chỉ ẩn khỏi hộp tin (inbox.service lọc theo app đang bật). Hạ cấp thì bật lại.

Revision ID: 0010_inbox_apps
Revises: 0009_trip_archive
Create Date: 2026-11-19 19:30
"""

from alembic import op

revision = "0010_inbox_apps"
down_revision = "0009_trip_archive"
branch_labels = None
depends_on = None

PACKAGES = "('org.telegram.messenger', 'com.facebook.orca')"


def upgrade() -> None:
    op.execute(
        f"UPDATE tab_listened_app SET enabled = false, updated_at = now() WHERE package_name IN {PACKAGES}"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE tab_listened_app SET enabled = true, updated_at = now() WHERE package_name IN {PACKAGES}"
    )
