"""QĐ-50: hộp tin với nhiều tài khoản Gmail (Gmail giả của agent Google)."""

import pytest

from app.integrations.google import service as google_service
from app.integrations.google import stores
from app.integrations.google.tests.conftest import GMAIL_SCOPES, connect_account, fake  # noqa: F401
from app.integrations.google.tests.test_accounts import WORK, _mail_account, add_mail
from app.modules.inbox import mail, service
from app.modules.inbox.models import GmailDraft, InboxMessage
from app.registry import register_integrations


@pytest.fixture
def two_accounts(db, user, fake):  # noqa: F811
    _, result = connect_account(db, user, fake, packs=("calendar", "tasks", "gmail"), scope=GMAIL_SCOPES)
    assert result.ket_qua == "ok"
    _, result = add_mail(db, user, fake)
    assert result.ket_qua == "ok"
    register_integrations()
    yield _mail_account(db, user)
    for register in ("register_mail_store", "register_calendar_store", "register_task_store"):
        getattr(stores, register)(None)
    if hasattr(stores, "register_booking_store"):
        stores.register_booking_store(None)


def _sync(db, user):
    class Job:
        user_id = user.user_id

    out = google_service.run_initial_sync(db, Job())
    db.flush()  # API chạy session riêng trên cùng kết nối: ghi hết thay đổi của worker trước
    return out


def test_messages_conversations_and_thread_carry_account(auth_client, db, user, fake, two_accounts):  # noqa: F811
    fake.gmail.add_mail(subject="Thư nhà", thread_id="th1")
    fake.mailbox("sub-2").add_mail(subject="Hợp đồng", thread_id="tw1", sender="Sếp <sep@congty.vn>")
    _sync(db, user)
    by_subject = {m.subject: m.account_email for m in db.query(InboxMessage).filter_by(source="gmail")}
    assert by_subject == {"Thư nhà": "dai.ca@gmail.com", "Hợp đồng": WORK}
    convs = service.list_conversations(db, user.user_id, {"app": "gmail"}, None)["items"]
    assert {c["title"]: c["account_email"] for c in convs} == {
        "Thư nhà": "dai.ca@gmail.com",
        "Hợp đồng": WORK,
    }
    [msg] = service.list_messages(db, user.user_id, "gmail:tw1", None)["items"]
    assert msg["account_email"] == WORK
    thread = auth_client.get("/api/v1/gmail/threads/tw1").json()["data"]
    assert thread["account_email"] == WORK and thread["account_id"] == two_accounts.id


def test_reply_draft_uses_thread_account_and_card_shows_sender(auth_client, db, user, fake, two_accounts):  # noqa: F811
    box2 = fake.mailbox("sub-2")
    box2.add_mail(subject="Hợp đồng", thread_id="tw1", sender="Sếp <sep@congty.vn>")
    _sync(db, user)
    resp = auth_client.post(
        "/api/v1/gmail/drafts", json={"to": ["sep@congty.vn"], "body": "Dạ em nhận.", "thread_ref": "tw1"}
    )
    assert resp.status_code == 201, resp.text
    d = resp.json()["data"]
    assert (d["account_id"], d["account_email"]) == (two_accounts.id, WORK)
    assert d["google_draft_id"] in box2.drafts and not fake.gmail.drafts
    edited = auth_client.patch(f"/api/v1/gmail/drafts/{d['id']}", json={"body": "Dạ em nhận, mai gửi."})
    assert edited.status_code == 200 and edited.json()["data"]["account_email"] == WORK
    card = auth_client.post(f"/api/v1/gmail/drafts/{d['id']}/send").json()["data"]["pending_action"]
    assert {"label": "Gửi từ", "value": WORK} in card["details"]
    from app.core.context import UserContext

    out = mail.send_approved(db, UserContext(user_id=user.user_id, timezone=user.timezone), d["id"])
    assert out["status"] == "sent" and len(box2.sent) == 1 and fake.gmail.sent == []
    # Thư mới chọn tài khoản gửi; bỏ trống thì tài khoản chính.
    chosen = auth_client.post(
        "/api/v1/gmail/drafts",
        json={"to": ["ban@example.com"], "subject": "Chào", "body": "x", "account_id": two_accounts.id},
    ).json()["data"]
    plain = auth_client.post(
        "/api/v1/gmail/drafts", json={"to": ["ban@example.com"], "subject": "Chào", "body": "x"}
    ).json()["data"]
    assert (chosen["account_email"], plain["account_email"]) == (WORK, "dai.ca@gmail.com")
    assert auth_client.delete(f"/api/v1/gmail/drafts/{chosen['id']}").status_code == 200
    assert chosen["google_draft_id"] not in box2.drafts


def test_removing_account_can_delete_its_messages(auth_client, db, user, fake, two_accounts):  # noqa: F811
    fake.gmail.add_mail(subject="Thư nhà")
    fake.mailbox("sub-2").add_mail(subject="Hợp đồng")
    _sync(db, user)
    auth_client.post(
        "/api/v1/gmail/drafts",
        json={"to": ["a@example.com"], "subject": "Chào", "body": "x", "account_id": two_accounts.id},
    )
    resp = auth_client.delete(f"/api/v1/google/accounts/{two_accounts.id}?delete_messages=true")
    assert resp.status_code == 200, resp.text
    left = [m.subject for m in db.query(InboxMessage).filter_by(source="gmail")]
    assert left == ["Thư nhà"]
    assert db.query(GmailDraft).count() == 0  # nháp của tài khoản theo khóa ngoại


def test_removing_account_keeps_messages_by_default(db, user, fake, two_accounts):  # noqa: F811
    fake.mailbox("sub-2").add_mail(subject="Hợp đồng")
    _sync(db, user)
    assert mail.remove_account_messages(db, user.user_id, WORK, False) == 0
    assert db.query(InboxMessage).filter_by(account_email=WORK).count() == 1


def test_create_draft_by_sender_email(db, user, fake, two_accounts):  # noqa: F811
    d = mail.create_draft(
        db,
        user.user_id,
        {"to": ["ban@example.com"], "subject": "Chào", "body": "x", "account_email": WORK.upper()},
    )
    assert (d["account_id"], d["account_email"]) == (two_accounts.id, WORK)
    assert mail.get_draft(db, user.user_id, d["id"])["account_email"] == WORK
    assert d["google_draft_id"] in fake.mailbox("sub-2").drafts


def test_conversations_newest_first_filter_by_account(auth_client, db, user, fake, two_accounts):  # noqa: F811
    fake.gmail.add_mail(subject="Thư nhà cũ", thread_id="th1", at_ms=1795000000000)
    fake.mailbox("sub-2").add_mail(subject="Thư công việc mới", thread_id="tw1", at_ms=1795000900000)
    _sync(db, user)
    # Thư cũ của tài khoản chính được Gmail đánh dấu quan trọng vẫn không chen lên trước thư mới hơn.
    db.query(InboxMessage).filter_by(thread_ref="th1").update({"importance": "important"})
    data = auth_client.get("/api/v1/inbox/conversations", params={"app": "gmail"}).json()["data"]
    assert [c["title"] for c in data["items"]] == ["Thư công việc mới", "Thư nhà cũ"]
    assert data["accounts"] == ["cong.viec@gmail.com", "dai.ca@gmail.com"]
    only = auth_client.get("/api/v1/inbox/conversations", params={"account_email": WORK.upper()}).json()[
        "data"
    ]
    assert [c["title"] for c in only["items"]] == ["Thư công việc mới"]
    alias = auth_client.get("/api/v1/inbox/conversations", params={"app": "gmail", "account": WORK}).json()[
        "data"
    ]
    assert [c["title"] for c in alias["items"]] == ["Thư công việc mới"]
    # Con trỏ cũ ba phần vẫn nhận.
    first = data["items"][0]
    old = f"0|{first['last_posted_at']}|{first['conversation_key']}"
    rest = auth_client.get("/api/v1/inbox/conversations", params={"app": "gmail", "cursor": old}).json()[
        "data"
    ]
    assert [c["title"] for c in rest["items"]] == ["Thư nhà cũ"]
