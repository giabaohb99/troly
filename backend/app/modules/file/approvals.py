"""Chạy việc tệp đã duyệt (QĐ-38): chia sẻ tệp Drive cho người khác.

share_drive_file: `{file_id, email, role (reader, commenter, writer; mặc định reader), message}`.
Tệp chưa có trên Drive thì phần Google tải lên trước rồi chia sẻ.
"""

from sqlalchemy.orm import Session

from app.core.context import UserContext
from app.core.errors import AppError


def share_drive_file(session: Session, user: UserContext, input_: dict) -> dict:
    try:
        from app.integrations.google import drive
    except ModuleNotFoundError as exc:
        raise AppError("Chưa nối Google Drive.", code="GOOGLE_NOT_CONNECTED", status=409) from exc
    return drive.share_file(
        session,
        user.user_id,
        int(input_["file_id"]),
        input_["email"],
        role=input_.get("role") or "reader",
        message=input_.get("message"),
    )


EXECUTORS = {"share_drive_file": share_drive_file}
