"""Nhiều tài khoản Google cho một người dùng (QĐ-50): tài khoản chính giữ Lịch, Việc, Drive; tài khoản thêm
chỉ có Gmail.

Revision ID: 0014_google_accounts
Revises: 0013_booking
Create Date: 2026-11-20 15:00
"""

from alembic import op

revision = "0014_google_accounts"
down_revision = "0013_booking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tab_google_account ADD COLUMN role text NOT NULL DEFAULT 'primary' "
        "CONSTRAINT ck_tab_google_account_role CHECK (role IN ('primary','mail'))"
    )
    op.execute("ALTER TABLE tab_google_account DROP CONSTRAINT uq_tab_google_account_user_id")
    op.execute(
        "CREATE UNIQUE INDEX uq_tab_google_account_primary ON tab_google_account (user_id) WHERE role = 'primary'"
    )
    op.execute(
        "ALTER TABLE tab_google_oauth_state ADD COLUMN role text NOT NULL DEFAULT 'primary' "
        "CONSTRAINT ck_tab_google_oauth_state_role CHECK (role IN ('primary','mail'))"
    )


def downgrade() -> None:
    op.execute("DELETE FROM tab_google_account WHERE role = 'mail'")
    op.execute("ALTER TABLE tab_google_oauth_state DROP COLUMN IF EXISTS role")
    op.execute("DROP INDEX IF EXISTS uq_tab_google_account_primary")
    op.execute("ALTER TABLE tab_google_account ADD CONSTRAINT uq_tab_google_account_user_id UNIQUE (user_id)")
    op.execute("ALTER TABLE tab_google_account DROP COLUMN IF EXISTS role")
