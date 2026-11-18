"""Drive với drive.file (40 mục 8): thư mục Trợ lý, tải multipart và resumable, chia sẻ qua thẻ duyệt."""

import pytest
from sqlalchemy import select

from app.core.errors import ValidationError
from app.integrations.google import drive, outbox
from app.integrations.google.errors import GoogleNotConnected
from app.integrations.google.models import GoogleOutbox, GoogleSyncState
from app.integrations.google.tests.conftest import DRIVE_SCOPES, connect_account


@pytest.fixture
def drive_account(db, user, fake):
    acc, result = connect_account(db, user, fake, packs=("drive",), scope=DRIVE_SCOPES)
    assert result.ket_qua == "ok" and "drive" in acc.enabled_packs
    return acc


def test_request_upload_needs_drive_pack(db, user, fake, account, file_store):
    with pytest.raises(GoogleNotConnected):
        drive.request_upload(db, user.user_id, 1)


def test_upload_small_file_multipart_into_assistant_folder(db, fake, drive_account, file_store):
    file_store.add(1, b"%PDF-1.4 noi dung", name="Lich trinh.docx")
    assert drive.request_upload(db, drive_account.user_id, 1) == {"queued": True}
    outbox.push_due(db)
    assert db.scalar(select(GoogleOutbox)).status == "done"
    folder = next(
        f for f in fake.drive_files.values() if f["mimeType"] == "application/vnd.google-apps.folder"
    )
    assert folder["name"] == "Trợ lý"
    uploaded = next(f for f in fake.drive_files.values() if f["name"] == "Lich trinh.docx")
    assert uploaded["parents"] == [folder["id"]] and uploaded["size"] == len(b"%PDF-1.4 noi dung")
    assert file_store.files[1]["drive_file_id"] == uploaded["id"]
    assert file_store.files[1]["link"].startswith("https://drive.google.com/")
    state = db.scalar(select(GoogleSyncState).where(GoogleSyncState.service == "drive"))
    assert state.resource_id == folder["id"]


def test_large_file_uses_resumable_and_folder_reused(db, fake, drive_account, file_store):
    file_store.add(1, b"a" * (5 * 1024 * 1024 + 1))
    file_store.add(2, b"nho")
    drive.upload(db, drive_account, 1)
    drive.upload(db, drive_account, 2)
    assert fake.calls("POST", r"/upload/drive/v3/files") and fake.calls("PUT", r"/upload/drive/v3/files")
    folders = [f for f in fake.drive_files.values() if f["mimeType"] == "application/vnd.google-apps.folder"]
    assert len(folders) == 1


def test_already_on_drive_is_not_uploaded_again(db, fake, drive_account, file_store):
    file_store.add(1, b"x")
    first = drive.upload(db, drive_account, 1)
    count = len(fake.drive_files)
    again = drive.upload(db, drive_account, 1)
    assert again["id"] == first["id"] and len(fake.drive_files) == count


def test_share_uploads_then_grants_permission_with_email(db, fake, drive_account, file_store):
    file_store.add(1, b"bao cao", name="bao-cao.docx")
    result = drive.share_file(db, drive_account.user_id, 1, "ban@example.com", "writer", "Gửi bạn báo cáo")
    perm = fake.permissions[0]
    assert perm["emailAddress"] == "ban@example.com" and perm["role"] == "writer" and perm["type"] == "user"
    assert (
        perm["params"]["sendNotificationEmail"] == "true"
        and perm["params"]["emailMessage"] == "Gửi bạn báo cáo"
    )
    assert result["drive_file_id"] == perm["file_id"] and result["web_view_link"].startswith(
        "https://drive.google.com/"
    )


def test_share_rejects_bad_role_and_email(db, fake, drive_account, file_store):
    file_store.add(1, b"x")
    with pytest.raises(ValidationError):
        drive.share_file(db, drive_account.user_id, 1, "ban@example.com", "owner")
    with pytest.raises(ValidationError):
        drive.share_file(db, drive_account.user_id, 1, "khong-phai-email", "reader")


def test_upload_waits_when_file_store_missing(db, fake, drive_account):
    drive.request_upload(db, drive_account.user_id, 9)
    outbox.push_due(db)
    row = db.scalar(select(GoogleOutbox))
    assert row.status == "pending" and row.attempts == 0
