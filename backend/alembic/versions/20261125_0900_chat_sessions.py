"""QĐ-51 bước 1: chat theo phiên đặt tên, mở lại phiên cũ, bỏ tách phiên 04:00.

Bỏ UQ (user_id, local_date): một ngày có thể nhiều phiên, một phiên kéo dài nhiều ngày. `local_date` giữ lại
(ngày mở phiên, cho bản app cũ). Phiên theo ngày hiện có thành phiên thường, tiêu đề tạm *Trò chuyện dd/mm/yyyy*.
`day_summary_done` đổi nghĩa: đã tóm cho lần phiên ngủ hiện tại (tin mới thì đặt lại false).

Revision ID: 0016_chat_sessions
Revises: 0015_inbox_account
Create Date: 2026-11-25 09:00
"""

from alembic import op

revision = "0016_chat_sessions"
down_revision = "0015_inbox_account"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tab_conversation DROP CONSTRAINT IF EXISTS uq_tab_conversation_user_id_local_date"
    )
    op.execute(
        "ALTER TABLE tab_conversation "
        "ADD COLUMN title text, "
        "ADD COLUMN title_source text NOT NULL DEFAULT 'auto' "
        "CONSTRAINT ck_tab_conversation_title_source CHECK (title_source IN ('auto','user')), "
        "ADD COLUMN pinned boolean NOT NULL DEFAULT false"
    )
    op.execute(
        "UPDATE tab_conversation SET title = 'Trò chuyện ' || to_char(local_date, 'DD/MM/YYYY'), "
        "last_message_at = coalesce(last_message_at, started_at)"
    )
    op.execute(
        "CREATE INDEX ix_tab_conversation_user_recent "
        "ON tab_conversation (user_id, pinned DESC, last_message_at DESC, id DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tab_conversation_user_recent")
    op.execute(
        "ALTER TABLE tab_conversation DROP COLUMN IF EXISTS pinned, DROP COLUMN IF EXISTS title_source, "
        "DROP COLUMN IF EXISTS title"
    )
    # Phiên cùng ngày (sinh ra sau khi bỏ tách 04:00) phải gộp trước khi đặt lại UQ: dồn tin vào phiên cũ nhất.
    op.execute(
        """
        WITH keep AS (
            SELECT user_id, local_date, min(id) AS id FROM tab_conversation GROUP BY user_id, local_date
        )
        UPDATE tab_message m SET conversation_id = k.id
        FROM tab_conversation c JOIN keep k ON k.user_id = c.user_id AND k.local_date = c.local_date
        WHERE m.conversation_id = c.id AND c.id <> k.id
        """
    )
    op.execute(
        """
        WITH keep AS (
            SELECT user_id, local_date, min(id) AS id FROM tab_conversation GROUP BY user_id, local_date
        )
        UPDATE tab_pending_action a SET conversation_id = k.id
        FROM tab_conversation c JOIN keep k ON k.user_id = c.user_id AND k.local_date = c.local_date
        WHERE a.conversation_id = c.id AND c.id <> k.id
        """
    )
    op.execute(
        """
        DELETE FROM tab_conversation c USING tab_conversation k
        WHERE k.user_id = c.user_id AND k.local_date = c.local_date AND k.id < c.id
        """
    )
    op.execute(
        "ALTER TABLE tab_conversation ADD CONSTRAINT uq_tab_conversation_user_id_local_date "
        "UNIQUE (user_id, local_date)"
    )
