"""QĐ-43: nháp Gmail, gửi qua thẻ duyệt (11 mục 3.10).

Revision ID: 0011_gmail_draft
Revises: 0010_inbox_apps
Create Date: 2026-11-19 21:00
"""

from alembic import op

revision = "0011_gmail_draft"
down_revision = "0010_inbox_apps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tab_gmail_draft (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id bigint NOT NULL REFERENCES tab_user(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            google_account_id bigint NOT NULL REFERENCES tab_google_account(id) ON DELETE CASCADE,
            google_draft_id text,
            thread_ref text,
            to_addrs citext[] NOT NULL,
            cc_addrs citext[] NOT NULL DEFAULT '{}',
            subject text NOT NULL,
            body text NOT NULL,
            body_hash text NOT NULL,
            status text NOT NULL DEFAULT 'draft' CONSTRAINT ck_tab_gmail_draft_status
                CHECK (status IN ('draft','sending','sent','discarded')),
            pending_action_id bigint REFERENCES tab_pending_action(id) ON DELETE SET NULL,
            approved_at timestamptz,
            sent_at timestamptz,
            sent_message_id text
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_gmail_draft_user_id ON tab_gmail_draft (user_id)")
    op.execute("CREATE INDEX ix_tab_gmail_draft_status ON tab_gmail_draft (user_id, status, updated_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tab_gmail_draft")
