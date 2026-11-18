"""Google Drive với scope drive.file (40 mục 8): thư mục *Trợ lý*, tải tệp lên, chia sẻ cho email.

drive.file chỉ thấy tệp do app tạo, nên mọi tệp lên Drive đều nằm trong thư mục *Trợ lý* do app tạo.
Tải lên chạy nền qua hàng chờ (op file_upload); chia sẻ chạy khi người dùng duyệt thẻ (share_drive_file,
QĐ-27), tự tải lên trước nếu tệp chưa có trên Drive.
"""

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.integrations.google import oauth, outbox, stores
from app.integrations.google.client import GoogleApi
from app.integrations.google.models import GoogleAccount, GoogleOutbox, GoogleSyncState

log = logging.getLogger("troly.google")

DRIVE = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER_NAME = "Trợ lý"
FOLDER_MIME = "application/vnd.google-apps.folder"
MULTIPART_MAX = 5 * 1024 * 1024  # tới 5 MB tải multipart, lớn hơn tải resumable (40 mục 8)
ROLES = ("reader", "commenter", "writer")


def _require_store() -> stores.FileStore:
    store = stores.file_store()
    if store is None:
        raise outbox.StoreMissing()
    return store


def request_upload(session: Session, user_id: int, file_id: int) -> dict:
    """POST /files/{id}/drive, công cụ save_file_to_drive: đặt lệnh tải lên chạy nền."""
    oauth.require_account(session, user_id, "drive")
    outbox.enqueue(session, user_id, "drive", "file_upload", "file", file_id)
    return {"queued": True}


def ensure_folder(session: Session, account: GoogleAccount) -> str:
    """Thư mục *Trợ lý*; mã lưu ở tab_google_sync_state (service drive, resource_id)."""
    state = session.scalar(
        select(GoogleSyncState).where(
            GoogleSyncState.google_account_id == account.id, GoogleSyncState.service == "drive"
        )
    )
    if state is not None and state.resource_id:
        return state.resource_id
    data = GoogleApi(session, account).request(
        "POST", f"{DRIVE}/files", params={"fields": "id"}, json={"name": FOLDER_NAME, "mimeType": FOLDER_MIME}
    )
    if state is None:
        state = GoogleSyncState(
            user_id=account.user_id,
            google_account_id=account.id,
            service="drive",
            resource_id=data["id"],
            needs_sync=False,
            initial_sync_state="done",
        )
        session.add(state)
    else:
        state.resource_id = data["id"]
    session.flush()
    return data["id"]


def _multipart(metadata: dict, data: bytes, mime: str) -> tuple[bytes, str]:
    boundary = f"troly-{uuid.uuid4().hex}"
    head = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata, ensure_ascii=False)}\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n"
    ).encode()
    return head + data + f"\r\n--{boundary}--\r\n".encode(), f"multipart/related; boundary={boundary}"


def upload(session: Session, account: GoogleAccount, file_id: int) -> dict:
    """Tải một tệp của app lên thư mục *Trợ lý*; trả {id, webViewLink}. Đã có trên Drive thì trả luôn."""
    store = _require_store()
    existing = store.drive_file_id(session, account.user_id, file_id)
    api = GoogleApi(session, account)
    if existing:
        return api.request("GET", f"{DRIVE}/files/{existing}", params={"fields": "id,webViewLink"})
    data, mime, name = store.file_bytes(session, account.user_id, file_id)
    folder = ensure_folder(session, account)
    metadata = {"name": name or f"tep-{file_id}", "parents": [folder]}
    fields = {"fields": "id,webViewLink"}
    if len(data) <= MULTIPART_MAX:
        body, content_type = _multipart(metadata, data, mime)
        result = api.request(
            "POST",
            UPLOAD,
            params={"uploadType": "multipart", **fields},
            content=body,
            headers={"Content-Type": content_type},
        )
    else:
        session_url = api.request(
            "POST",
            UPLOAD,
            params={"uploadType": "resumable", **fields},
            json=metadata,
            headers={"X-Upload-Content-Type": mime, "X-Upload-Content-Length": str(len(data))},
            return_location=True,
        )
        result = api.request("PUT", session_url, content=data, headers={"Content-Type": mime}, ok=(200, 201))
    store.save_drive_result(session, account.user_id, file_id, result["id"], result.get("webViewLink"))
    return result


def push_upload(session: Session, account: GoogleAccount, row: GoogleOutbox) -> None:
    upload(session, account, row.local_id)


def share_file(
    session: Session,
    user_id: int,
    file_id: int,
    email: str,
    role: str = "reader",
    message: str | None = None,
) -> dict:
    """Chạy khi người dùng duyệt thẻ share_drive_file: tải lên nếu chưa có, cấp quyền, Google gửi thư báo."""
    if role not in ROLES:
        raise ValidationError(fields={"role": "Chỉ nhận reader, commenter hoặc writer."})
    if "@" not in (email or ""):
        raise ValidationError(fields={"email": "Email không hợp lệ."})
    account = oauth.require_account(session, user_id, "drive")
    uploaded = upload(session, account, file_id)
    params: dict = {"sendNotificationEmail": "true", "fields": "id"}
    if message:
        params["emailMessage"] = message[:1000]
    GoogleApi(session, account).request(
        "POST",
        f"{DRIVE}/files/{uploaded['id']}/permissions",
        params=params,
        json={"type": "user", "role": role, "emailAddress": email.strip()},
    )
    return {"drive_file_id": uploaded["id"], "web_view_link": uploaded.get("webViewLink")}
