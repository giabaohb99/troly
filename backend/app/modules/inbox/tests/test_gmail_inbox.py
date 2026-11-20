"""QĐ-43: thư Gmail vào hộp tin, nháp và gửi qua thẻ duyệt (Gmail giả của agent Google)."""

from datetime import UTC, datetime

import pytest

from app.integrations.google import gmail, stores
from app.integrations.google.tests.conftest import GMAIL_SCOPES, connect_account, fake  # noqa: F401
from app.modules.device import service as device_service
from app.modules.inbox import mail, service
from app.modules.inbox.models import GmailDraft, InboxMessage
from app.registry import register_integrations


@pytest.fixture
def gmail_user(db, user, fake):  # noqa: F811
    acc, result = connect_account(db, user, fake, packs=("gmail",), scope=GMAIL_SCOPES)
    assert result.ket_qua == "ok"
    register_integrations()
    yield acc
    stores.register_mail_store(None)
    stores.register_calendar_store(None)
    stores.register_task_store(None)


def remote(mid, subject, snippet="Chào đại ca", important=False, sender=("Lan", "lan@example.com")):
    return gmail.RemoteMail(
        message_id=mid,
        thread_id=f"t-{mid}",
        from_name=sender[0],
        from_email=sender[1],
        subject=subject,
        snippet=snippet,
        date=datetime(2026, 11, 19, 1, tzinfo=UTC),
        labels=["INBOX", "IMPORTANT"] if important else ["INBOX"],
        important=important,
    )


def test_store_filters_otp_rules_and_duplicates(db, user):
    service.create_rule(db, user.user_id, "muted_sender", "spam@example.com", None)
    mails = [
        remote("m1", "Hẹn cà phê", important=True),
        remote("m2", "Mã xác minh", snippet="Mã OTP của bạn là 482913"),
        remote("m3", "Quảng cáo", sender=("Shop", "spam@example.com")),
        remote("m1", "Hẹn cà phê"),
    ]
    assert mail.save_gmail_messages(db, user.user_id, mails) == 1
    assert mail.save_gmail_messages(db, user.user_id, [remote("m1", "Hẹn cà phê")]) == 0
    [row] = db.query(InboxMessage).all()
    assert (row.source, row.app, row.conversation_key, row.conversation_title) == (
        "gmail",
        "gmail",
        "gmail:t-m1",
        "Hẹn cà phê",
    )
    assert (row.sender, row.external_id, row.thread_ref, row.importance) == ("Lan", "m1", "t-m1", "important")
    [conv] = service.list_conversations(db, user.user_id, {"app": "gmail"}, None)["items"]
    assert conv["title"] == "Hẹn cà phê"


def test_sync_job_writes_through_real_store(db, user, fake, gmail_user):  # noqa: F811
    from sqlalchemy import select

    from app.integrations.google.models import GoogleSyncState

    fake.gmail.add_mail(subject="Thư từ mẹ", labels=("INBOX", "CATEGORY_PERSONAL"))
    state = db.scalar(
        select(GoogleSyncState).where(
            GoogleSyncState.google_account_id == gmail_user.id, GoogleSyncState.service == "gmail"
        )
    )
    assert gmail.sync_gmail(db, gmail_user, state) == 1
    assert db.query(InboxMessage).filter(InboxMessage.source == "gmail").one().subject == "Thư từ mẹ"


def test_draft_send_only_after_approval_and_unchanged(auth_client, db, user, fake, gmail_user):  # noqa: F811
    created = auth_client.post(
        "/api/v1/gmail/drafts", json={"to": ["ban@example.com"], "subject": "Hẹn", "body": "Mai gặp nhé"}
    )
    assert created.status_code == 201, created.text
    draft = created.json()["data"]
    assert draft["status"] == "draft" and draft["google_draft_id"] in fake.gmail.drafts

    send = auth_client.post(f"/api/v1/gmail/drafts/{draft['id']}/send")
    assert send.status_code == 202
    pending = send.json()["data"]["pending_action"]
    assert pending["tool_name"] == "send_gmail_draft" and fake.gmail.sent == []

    ok = auth_client.post(f"/api/v1/chat/actions/{pending['id']}/approve")
    assert ok.status_code == 200, ok.text
    row = db.get(GmailDraft, draft["id"])
    db.refresh(row)
    assert row.status == "sent" and row.sent_at is not None and len(fake.gmail.sent) == 1


def test_draft_changed_on_gmail_blocks_send(auth_client, db, user, fake, gmail_user):  # noqa: F811
    draft = auth_client.post(
        "/api/v1/gmail/drafts", json={"to": ["ban@example.com"], "subject": "Báo giá", "body": "Giá 10 triệu"}
    ).json()["data"]
    pending = auth_client.post(f"/api/v1/gmail/drafts/{draft['id']}/send").json()["data"]["pending_action"]
    fake.gmail.edit_draft(draft["google_draft_id"], "Giá 1 tỷ")
    resp = auth_client.post(f"/api/v1/chat/actions/{pending['id']}/approve")
    assert resp.status_code == 200 and resp.json()["data"]["action"]["status"] == "failed"
    assert "Nháp đã bị sửa" in resp.json()["data"]["result_text"]
    row = db.get(GmailDraft, draft["id"])
    db.refresh(row)
    assert row.status == "draft" and fake.gmail.sent == []


def test_patch_discard_and_config_hides_gmail_app(auth_client, db, user, fake, gmail_user):  # noqa: F811
    draft = auth_client.post(
        "/api/v1/gmail/drafts", json={"to": ["a@example.com"], "subject": "Thử", "body": "Nháp"}
    ).json()["data"]
    patched = auth_client.patch(f"/api/v1/gmail/drafts/{draft['id']}", json={"body": "Nháp đã sửa"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["body"] == "Nháp đã sửa"
    assert auth_client.delete(f"/api/v1/gmail/drafts/{draft['id']}").status_code == 200
    assert draft["google_draft_id"] not in fake.gmail.drafts
    assert auth_client.get("/api/v1/gmail/drafts").json()["data"]["items"] == []

    device_service.create_listened_app(
        db,
        user.user_id,
        {"package_name": "com.google.android.gm", "label": "Gmail", "purpose": "inbox", "parser": "generic"},
    )
    packages = [a["package_name"] for a in device_service.device_config(db, user.user_id)["listened_apps"]]
    assert "com.google.android.gm" not in packages


def test_drafts_need_gmail_connected(auth_client):
    resp = auth_client.post("/api/v1/gmail/drafts", json={"to": ["a@example.com"], "body": "x"})
    assert resp.status_code == 409


# ---------- Mục Gmail vào hộp tin (gmail.categories) ----------


def test_gmail_categories_setting_store_and_rescan(db, user, gmail_user, monkeypatch):
    from app.core.errors import ValidationError
    from app.integrations.google.models import GoogleSyncState
    from app.modules.inbox.google_store import STORE
    from app.modules.setting import service as setting_service

    assert STORE.gmail_categories(db, user.user_id) == "primary_updates"  # mặc định
    with pytest.raises(ValidationError):
        setting_service.update(db, user.user_id, {"gmail.categories": "promotions"})
    calls = []
    monkeypatch.setattr(gmail, "rescan_inbox", lambda s, u, days: calls.append((u, days)))
    setting_service.update(db, user.user_id, {"gmail.categories": "all"})
    assert STORE.gmail_categories(db, user.user_id) == "all" and calls == [(user.user_id, 7)]
    setting_service.update(db, user.user_id, {"gmail.categories": "all"})  # không đổi: không quét lại
    assert calls == [(user.user_id, 7)]
    monkeypatch.undo()
    # Hàm thật: lượt đồng bộ sau quét lại 7 ngày.
    setting_service.update(db, user.user_id, {"gmail.categories": "primary"})
    state = db.query(GoogleSyncState).filter(GoogleSyncState.service == "gmail").one()
    assert state.history_id is None and state.needs_sync


def test_gmail_categories_change_without_gmail_is_saved(db, user):
    from app.modules.inbox import google_store  # noqa: F401  (đăng ký việc quét lại)
    from app.modules.setting import service as setting_service

    out = setting_service.update(db, user.user_id, {"gmail.categories": "primary"})
    assert out["gmail.categories"] == "primary"
