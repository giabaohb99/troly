"""QĐ-52: Zalo đầy đủ qua zalo-bridge. Tài khoản Zalo của người dùng, tin Zalo trong hộp tin.

`tab_inbox_message` thêm cột cho tin Zalo (`source = zalo`): `is_self` (tin mình gửi, từ app hay máy khác),
`media` (ảnh, video, tệp đã hoặc chưa tải về R2), `media_pending` (job còn phải tải), `recalled_at` (thu hồi),
`quote` (tin được trích). Khử trùng theo `msg_id` của Zalo qua `dedupe_hash`; chỉ mục theo `external_id`.

Revision ID: 0019_zalo
Revises: 0018_connectors
Create Date: 2026-11-25 18:00
"""

from alembic import op

revision = "0019_zalo"
down_revision = "0018_connectors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tab_zalo_account (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id bigint NOT NULL REFERENCES tab_user(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            state text NOT NULL DEFAULT 'logged_out',
            zalo_uid text,
            display_name text,
            last_event_at timestamptz,
            CONSTRAINT uq_tab_zalo_account_user_id UNIQUE (user_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_tab_zalo_account_user_id ON tab_zalo_account (user_id)")
    op.execute(
        "ALTER TABLE tab_inbox_message "
        "ADD COLUMN is_self boolean NOT NULL DEFAULT false, "
        "ADD COLUMN media jsonb, "
        "ADD COLUMN media_pending boolean NOT NULL DEFAULT false, "
        "ADD COLUMN recalled_at timestamptz, "
        "ADD COLUMN quote jsonb"
    )
    op.execute("ALTER TABLE tab_inbox_message DROP CONSTRAINT ck_tab_inbox_message_source")
    op.execute(
        "ALTER TABLE tab_inbox_message ADD CONSTRAINT ck_tab_inbox_message_source "
        "CHECK (source IN ('notification','gmail','zalo'))"
    )
    op.execute(
        "CREATE INDEX ix_tab_inbox_message_zalo_external ON tab_inbox_message (user_id, external_id) "
        "WHERE source = 'zalo'"
    )
    op.execute(
        "CREATE INDEX ix_tab_inbox_message_media_pending ON tab_inbox_message (id) WHERE media_pending"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tab_inbox_message_media_pending")
    op.execute("DROP INDEX IF EXISTS ix_tab_inbox_message_zalo_external")
    op.execute("DELETE FROM tab_inbox_message WHERE source = 'zalo'")
    op.execute("ALTER TABLE tab_inbox_message DROP CONSTRAINT ck_tab_inbox_message_source")
    op.execute(
        "ALTER TABLE tab_inbox_message ADD CONSTRAINT ck_tab_inbox_message_source "
        "CHECK (source IN ('notification','gmail'))"
    )
    op.execute(
        "ALTER TABLE tab_inbox_message DROP COLUMN IF EXISTS quote, DROP COLUMN IF EXISTS recalled_at, "
        "DROP COLUMN IF EXISTS media_pending, DROP COLUMN IF EXISTS media, DROP COLUMN IF EXISTS is_self"
    )
    op.execute("DROP TABLE IF EXISTS tab_zalo_account")
