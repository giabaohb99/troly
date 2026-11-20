"""QĐ-50: nhiều tài khoản Gmail. Tin hộp tin và nháp ghi tài khoản Gmail (email).

Revision ID: 0015_inbox_account
Revises: 0014_google_accounts
Create Date: 2026-11-20 17:00
"""

from alembic import op

revision = "0015_inbox_account"
down_revision = "0014_google_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tab_inbox_message ADD COLUMN account_email citext")
    op.execute("ALTER TABLE tab_gmail_draft ADD COLUMN account_email citext")


def downgrade() -> None:
    op.execute("ALTER TABLE tab_gmail_draft DROP COLUMN IF EXISTS account_email")
    op.execute("ALTER TABLE tab_inbox_message DROP COLUMN IF EXISTS account_email")
