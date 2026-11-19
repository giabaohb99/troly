"""Chạy việc hộp tin đã duyệt (QĐ-43): gửi nháp Gmail.

send_gmail_draft: `{draft_id}` (id của tab_gmail_draft). Nháp trên Gmail bị sửa sau khi tạo thẻ thì
409 `ACTION_PAYLOAD_CHANGED` (*Nháp đã bị sửa, hãy xem lại*), nháp giữ trạng thái `draft`.
"""

from sqlalchemy.orm import Session

from app.core.context import UserContext
from app.modules.inbox import mail


def send_gmail_draft(session: Session, user: UserContext, input_: dict) -> dict:
    return mail.send_approved(session, user, int(input_["draft_id"]))


EXECUTORS = {"send_gmail_draft": send_gmail_draft}
