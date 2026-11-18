"""Công cụ Drive của module file (QĐ-38, việc 5-02): lưu lên Drive không duyệt, chia sẻ luôn qua thẻ duyệt."""

from datetime import UTC, datetime

import pytest

from app.ai.schemas import AiError, ToolContext
from app.core.errors import AppError
from app.modules.file import service, tools

NOW = datetime(2026, 11, 18, 5, tzinfo=UTC)
FILE = {"id": 7, "original_name": "Lich-trinh-Phuoc-Hai.docx", "status": "ready"}


@pytest.fixture
def ctx(db, user, monkeypatch):
    monkeypatch.setattr(service, "get_file", lambda session, user_id, file_id: {**FILE, "id": file_id})
    return ToolContext(session=db, user=user, conversation_id=None, now=NOW)


def _spec(name):
    return next(t for t in tools.TOOLS if t.name == name)


def test_save_to_drive_queues_upload(ctx, monkeypatch):
    calls = []
    monkeypatch.setattr(
        service, "request_drive_upload", lambda s, uid, fid: calls.append((uid, fid)) or {"queued": True}
    )
    spec = _spec("save_file_to_drive")
    out = spec.run(ctx, spec.input_model.model_validate({"file_id": 7}))
    assert calls == [(ctx.user.user_id, 7)] and out.result["trang_thai"] == "dang_luu_len_drive"
    assert spec.needs_approval is None


def test_save_to_drive_without_google_offers_settings(ctx, monkeypatch):
    def not_connected(*a):
        raise AppError("Chưa nối Google Drive.", code="GOOGLE_NOT_CONNECTED", status=409)

    monkeypatch.setattr(service, "request_drive_upload", not_connected)
    spec = _spec("save_file_to_drive")
    out = spec.run(ctx, spec.input_model.model_validate({"file_id": 7}))
    assert out.result["trang_thai"] == "chua_noi_google"
    assert out.actions[0]["screen"] == "settings_google"


def test_share_always_needs_approval_with_recipient_and_role(ctx):
    spec = _spec("share_drive_file")
    data = spec.input_model.model_validate(
        {"file_id": 7, "email": " chi.hanh@example.com ", "role": "writer", "message": "Em gửi lịch trình"}
    )
    assert spec.run is None and spec.needs_approval(data) is True
    draft = spec.prepare(ctx, data)
    labels = {d["label"]: d["value"] for d in draft.details}
    assert labels["Người nhận"] == "chi.hanh@example.com" and labels["Quyền"] == "Được sửa"
    assert labels["Tệp"] == "Lich-trinh-Phuoc-Hai.docx" and "Em gửi" in labels["Lời nhắn"]
    assert draft.input == {
        "file_id": 7,
        "email": "chi.hanh@example.com",
        "role": "writer",
        "message": "Em gửi lịch trình",
    }


def test_share_rejects_bad_email(ctx):
    spec = _spec("share_drive_file")
    data = spec.input_model.model_validate({"file_id": 7, "email": "chị Hạnh", "role": "reader"})
    with pytest.raises(AiError):
        spec.prepare(ctx, data)


def test_share_default_role_and_commenter(ctx):
    spec = _spec("share_drive_file")
    plain = spec.prepare(ctx, spec.input_model.model_validate({"file_id": 7, "email": "a@example.com"}))
    assert plain.input["role"] == "reader" and plain.input["message"] is None
    data = spec.input_model.model_validate({"file_id": 7, "email": "a@example.com", "role": "commenter"})
    labels = {d["label"]: d["value"] for d in spec.prepare(ctx, data).details}
    assert labels["Quyền"] == "Được nhận xét"


def test_approved_share_runs_module_executor():
    from app.modules.file import approvals
    from app.registry import approval_executor

    assert approval_executor("share_drive_file") is approvals.share_drive_file
