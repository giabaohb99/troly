"""QĐ-50: nhiều tài khoản Google cho một người dùng. Tài khoản chính giữ Lịch, Việc, Drive; tài khoản thêm
chỉ có Gmail; đọc, gửi, gỡ từng tài khoản độc lập."""

from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from app.core.errors import ConflictError, NotFoundError
from app.integrations.google import gmail, oauth, service
from app.integrations.google.models import GoogleAccount, GoogleSyncState
from app.integrations.google.tests.conftest import GMAIL_SCOPES, connect_account

MAIL_SCOPES = (
    "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile "
    "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.compose"
)
WORK = "cong.viec@gmail.com"


@pytest.fixture
def primary(db, user, fake):
    acc, result = connect_account(db, user, fake, packs=("calendar", "tasks", "gmail"), scope=GMAIL_SCOPES)
    assert result.ket_qua == "ok"
    return acc


def add_mail(db, user, fake, sub="sub-2", email=WORK, scope=MAIL_SCOPES):
    url = oauth.start_connect(db, user.user_id, [], "mail")
    q = parse_qs(urlparse(url).query)
    result = oauth.finish_connect(db, fake.issue_code(sub=sub, email=email, scope=scope), q["state"][0], None)
    db.flush()
    return q, result


def _mail_account(db, user):
    return db.scalar(
        select(GoogleAccount).where(GoogleAccount.user_id == user.user_id, GoogleAccount.role == "mail")
    )


def _gmail_state(db, account):
    return db.scalar(
        select(GoogleSyncState).where(
            GoogleSyncState.google_account_id == account.id,
            GoogleSyncState.service == "gmail",
            GoogleSyncState.resource_id == "me",
        )
    )


def test_add_mail_account_asks_only_gmail_and_keeps_primary(db, user, fake, primary):
    q, result = add_mail(db, user, fake)
    scopes = q["scope"][0].split()
    assert any(s.endswith("gmail.compose") for s in scopes) and not any("calendar" in s for s in scopes)
    assert q["prompt"][0] == "consent select_account" and "login_hint" not in q
    assert (result.ket_qua, result.role) == ("ok", "mail")
    assert "tai-khoan=mail" in oauth.callback_html(result)
    extra = _mail_account(db, user)
    assert extra.email == WORK and extra.enabled_packs == ["base", "gmail"]
    assert oauth.get_account(db, user.user_id).id == primary.id  # Lịch, Việc vẫn ở tài khoản chính
    rows = service.list_accounts(db, user.user_id)
    assert [(r["email"], r["role"]) for r in rows] == [("dai.ca@gmail.com", "primary"), (WORK, "mail")]
    assert [s.service for s in db.scalars(select(GoogleSyncState).where(
        GoogleSyncState.google_account_id == extra.id))] == ["gmail"]  # fmt: skip


def test_primary_email_cannot_be_added_again(db, user, fake, primary):
    _, result = add_mail(db, user, fake, sub="sub-1", email="dai.ca@gmail.com")
    assert result.ket_qua == "da-co" and _mail_account(db, user) is None


def test_mail_account_without_gmail_scope(db, user, fake, primary):
    scope = "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile"
    _, result = add_mail(db, user, fake, scope=scope)
    assert result.ket_qua == "thieu-quyen" and _mail_account(db, user) is None


def test_access_denied_explains_test_users(db, user, fake, primary):
    url = oauth.start_connect(db, user.user_id, [], "mail")
    state = parse_qs(urlparse(url).query)["state"][0]
    result = oauth.finish_connect(db, None, state, "access_denied")
    assert result.ket_qua == "huy" and "Test users" in result.message and result.role == "mail"


def test_each_account_syncs_its_own_mailbox(db, user, fake, primary, mail_store):
    add_mail(db, user, fake)
    extra = _mail_account(db, user)
    fake.gmail.add_mail(subject="Thư nhà")
    fake.mailbox("sub-2").add_mail(subject="Thư công việc")

    class Job:
        user_id = user.user_id

    result = service.run_initial_sync(db, Job())
    assert result["gmail"] == 2
    by_subject = {m.subject: m.account_email for m in mail_store.mails.values()}
    assert by_subject == {"Thư nhà": "dai.ca@gmail.com", "Thư công việc": WORK}
    assert _gmail_state(db, extra).initial_sync_state == "done"


def test_reply_goes_from_account_that_received_thread(db, user, fake, primary):
    add_mail(db, user, fake)
    box2 = fake.mailbox("sub-2")
    box2.add_mail(subject="Hợp đồng", thread_id="tw1", sender="Sếp <sep@congty.vn>")
    t = gmail.get_thread(db, user.user_id, "tw1")
    assert t["account_email"] == WORK and t["reply"]["to"] == ["sep@congty.vn"]
    d = gmail.create_draft(
        db, user.user_id, to=["sep@congty.vn"], cc=[], subject="", body="Dạ em nhận.", thread_id="tw1"
    )
    assert d["account_email"] == WORK and d["google_draft_id"] in box2.drafts and not fake.gmail.drafts
    gmail.send_draft(db, user.user_id, d["google_draft_id"], d["body_hash"], account_id=d["account_id"])
    assert len(box2.sent) == 1 and fake.gmail.sent == []

    new = gmail.create_draft(db, user.user_id, to=["ban@example.com"], cc=[], subject="Chào", body="x")
    assert new["account_email"] == "dai.ca@gmail.com"  # thư mới mặc định tài khoản chính
    chosen = gmail.create_draft(db, user.user_id, to=["ban@example.com"], cc=[], subject="Chào", body="x",
                                account_email=WORK)  # fmt: skip
    assert chosen["account_id"] == d["account_id"]


def test_search_covers_all_accounts(db, user, fake, primary):
    add_mail(db, user, fake)
    fake.gmail.add_mail(subject="Hóa đơn điện", at_ms=1795000000000)
    fake.mailbox("sub-2").add_mail(subject="Hóa đơn công ty", at_ms=1795000100000)
    hits = gmail.search(db, user.user_id, "Hóa")
    assert [(h["subject"], h["account_email"]) for h in hits] == [
        ("Hóa đơn công ty", WORK),
        ("Hóa đơn điện", "dai.ca@gmail.com"),
    ]


def test_remove_extra_account_revokes_only_its_token(db, user, fake, primary, mail_store):
    removed: list = []
    mail_store.on_account_removed = lambda s, uid, email, delete: removed.append((email, delete))
    add_mail(db, user, fake)
    extra = _mail_account(db, user)
    extra_token = oauth._decrypt(extra, extra.refresh_token_enc)
    assert service.remove_account(db, user.user_id, extra.id, delete_messages=True) == {"ok": True}
    assert fake.revoked == [extra_token] and removed == [(WORK, True)]
    assert _mail_account(db, user) is None
    assert oauth.access_token(db, primary, force_refresh=True)  # tài khoản chính vẫn chạy
    with pytest.raises(ConflictError):
        service.remove_account(db, user.user_id, primary.id)
    with pytest.raises(NotFoundError):
        service.remove_account(db, user.user_id, extra.id)


def test_only_mail_account_has_gmail(db, user, fake, account):
    """Tài khoản chính không bật Gmail, Gmail nằm ở tài khoản thêm: đọc, soạn dùng tài khoản thêm."""
    add_mail(db, user, fake)
    fake.mailbox("sub-2").add_mail(subject="Chỉ ở công việc", thread_id="t9")
    assert gmail.get_thread(db, user.user_id, "t9")["account_email"] == WORK
    d = gmail.create_draft(db, user.user_id, to=["a@example.com"], cc=[], subject="A", body="b")
    assert d["account_email"] == WORK


def test_api_accounts_and_mail_connect(auth_client, db, user, fake, primary):
    r = auth_client.post("/api/v1/google/connect", json={"role": "mail"})
    assert r.status_code == 200 and "select_account" in r.json()["data"]["auth_url"]
    assert auth_client.post("/api/v1/google/connect", json={"role": "khac"}).status_code == 400
    items = auth_client.get("/api/v1/google/accounts").json()["data"]["items"]
    assert items[0]["role"] == "primary" and items[0]["email"] == "dai.ca@gmail.com"
    assert auth_client.delete(f"/api/v1/google/accounts/{primary.id}").status_code == 409


def _ms(days_ago: float) -> int:
    from datetime import UTC, datetime, timedelta

    return int((datetime.now(UTC) - timedelta(days=days_ago)).timestamp() * 1000)


def test_new_account_first_sync_reads_30_days(db, user, fake, primary, mail_store):
    add_mail(db, user, fake)
    box = fake.mailbox("sub-2")
    box.add_mail(subject="25 ngày trước", at_ms=_ms(25))
    box.add_mail(subject="40 ngày trước", at_ms=_ms(40))
    box.add_mail(
        subject="Quảng cáo", labels=("INBOX", "CATEGORY_PROMOTIONS"), at_ms=_ms(2)
    )  # theo gmail.categories

    class Job:
        user_id = user.user_id

    service.run_initial_sync(db, Job())
    assert {m.subject for m in mail_store.mails.values() if m.account_email == WORK} == {"25 ngày trước"}
    q = [r.url.params["q"] for r in fake.calls("GET", r"/gmail/v1/users/me/messages$")]
    assert "in:inbox newer_than:30d" in q


def test_first_sync_capped_at_300(db, user, fake, primary, mail_store, monkeypatch):
    monkeypatch.setattr(gmail, "FIRST_MAX", 5)
    add_mail(db, user, fake)
    for i in range(8):
        fake.mailbox("sub-2").add_mail(subject=f"Thư {i}", at_ms=_ms(i + 1))

    class Job:
        user_id = user.user_id

    service.run_initial_sync(db, Job())
    assert len([m for m in mail_store.mails.values() if m.account_email == WORK]) == 5
    assert gmail.FIRST_MAX == 5 and gmail.FIRST_DAYS == 30


def test_rescan_one_account_reads_back_30_days(auth_client, db, user, fake, primary, mail_store):
    add_mail(db, user, fake)
    extra = _mail_account(db, user)

    class Job:
        user_id = user.user_id

    service.run_initial_sync(db, Job())
    db.flush()
    r = auth_client.post(f"/api/v1/google/accounts/{extra.id}/rescan", json={})
    assert r.status_code == 202
    db.expire_all()
    state, main = _gmail_state(db, extra), _gmail_state(db, primary)
    assert state.history_id is None and state.needs_sync is True
    assert main.history_id is not None  # tài khoản chính không bị quét lại
    from datetime import UTC, datetime, timedelta

    assert datetime.now(UTC) - state.updated_min > timedelta(days=29)
