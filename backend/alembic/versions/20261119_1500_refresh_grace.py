"""Ân hạn 60 giây khi mã làm mới vừa xoay bị dùng lại (lỗi cài đè APK 19/11).

Revision ID: 0007_refresh_grace
Revises: 0006_meet_drive
Create Date: 2026-11-19 15:00
"""

from alembic import op

revision = "0007_refresh_grace"
down_revision = "0006_meet_drive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tab_auth_session ADD COLUMN previous_token_hash text, "
        "ADD COLUMN rotated_at timestamptz, ADD COLUMN current_token_enc bytea, "
        "ADD COLUMN current_token_key_version smallint"
    )
    op.execute(
        "CREATE INDEX ix_tab_auth_session_previous_token_hash ON tab_auth_session (previous_token_hash) "
        "WHERE previous_token_hash IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tab_auth_session_previous_token_hash")
    op.execute(
        "ALTER TABLE tab_auth_session DROP COLUMN IF EXISTS current_token_key_version, "
        "DROP COLUMN IF EXISTS current_token_enc, DROP COLUMN IF EXISTS rotated_at, "
        "DROP COLUMN IF EXISTS previous_token_hash"
    )
