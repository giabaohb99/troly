"""Thông báo *Trợ lý đã trả lời* chỉ cho lượt app chưa nhận hết (lỗi báo trùng 19/11, bản ad60033).

`tab_message.notify_done` bật khi luồng SSE ngắt trước sự kiện kết thúc mà lượt vẫn chạy xong ở luồng nền.
Notice `chat_done` chỉ đọc tin có cờ này.

Revision ID: 0008_chat_notify
Revises: 0007_refresh_grace
Create Date: 2026-11-19 17:00
"""

from alembic import op

revision = "0008_chat_notify"
down_revision = "0007_refresh_grace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tab_message ADD COLUMN notify_done boolean NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE tab_message DROP COLUMN IF EXISTS notify_done")
