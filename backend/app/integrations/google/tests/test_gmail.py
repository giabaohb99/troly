"""Gmail (40 mục 6, QĐ-43): quét hộp Chính, đọc luồng, nháp, gửi chỉ khi nháp còn đúng như lúc duyệt."""

import base64
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core import clock
from app.core.errors import ValidationError
from app.integrations.google import gmail, service
from app.integrations.google.errors import GoogleNotConnected
from app.integrations.google.models import GoogleSyncState
from app.integrations.google.tests.conftest import GMAIL_SCOPES, connect_account


@pytest.fixture
def gmail_account(db, user, fake):
    acc, result = connect_account(db, user, fake, packs=("gmail",), scope=GMAIL_SCOPES)
    assert result.ket_qua == "ok" and "gmail" in acc.enabled_packs
    return acc


def _state(db, account) -> GoogleSyncState:
    return db.scalar(
        select(GoogleSyncState).where(
            GoogleSyncState.google_account_id == account.id, GoogleSyncState.service == "gmail"
        )
    )


def test_connect_gmail_creates_sync_state(db, gmail_account):
    state = _state(db, gmail_account)
    assert state.resource_id == "me" and state.initial_sync_state == "pending"


def test_first_sync_keeps_primary_inbox_only(db, fake, gmail_account, mail_store):
    box = fake.gmail
    keep = box.add_mail(subject="Hẹn cà phê", labels=("INBOX", "CATEGORY_PERSONAL", "IMPORTANT"))
    box.add_mail(subject="Giảm giá 50%", labels=("INBOX", "CATEGORY_PROMOTIONS"))
    box.add_mail(subject="Ai đó like ảnh", labels=("INBOX", "CATEGORY_SOCIAL"))
    box.add_mail(subject="Rác", labels=("SPAM",))
    box.add_mail(subject="Thư mình gửi", labels=("SENT",))
    state = _state(db, gmail_account)
    assert gmail.sync_gmail(db, gmail_account, state) == 1
    mail = mail_store.mails[keep]
    assert mail.subject == "Hẹn cà phê" and mail.from_email == "lan@example.com" and mail.from_name == "Lan"
    assert mail.important is True and mail.thread_id.startswith("t")
    assert state.history_id == str(box.history_id)
    assert state.next_sync_at - clock.now() <= timedelta(minutes=5)
    meta = fake.calls("GET", r"/messages/m")[0].url.params
    assert meta["format"] == "metadata"  # chỉ metadata, không đọc nội dung khi quét


def test_incremental_sync_reads_history_only(db, fake, gmail_account, mail_store):
    state = _state(db, gmail_account)
    fake.gmail.add_mail(subject="Thư cũ")
    gmail.sync_gmail(db, gmail_account, state)
    lists = len(fake.calls("GET", r"/gmail/v1/users/me/messages$"))
    new = fake.gmail.add_mail(subject="Thư mới")
    assert gmail.sync_gmail(db, gmail_account, state) == 1
    assert new in mail_store.mails
    assert len(fake.calls("GET", r"/gmail/v1/users/me/messages$")) == lists  # không liệt kê lại
    assert fake.calls("GET", r"/history$")[-1].url.params["labelId"] == "INBOX"


def test_history_404_falls_back_to_full_scan(db, fake, gmail_account, mail_store):
    state = _state(db, gmail_account)
    first = fake.gmail.add_mail(subject="Một")
    gmail.sync_gmail(db, gmail_account, state)
    later = fake.gmail.add_mail(subject="Hai")
    fake.gmail.min_history = fake.gmail.history_id + 1
    assert gmail.sync_gmail(db, gmail_account, state) == 1  # thư một không ghi trùng
    assert set(mail_store.mails) == {first, later}


def test_initial_sync_and_due_job_run_gmail(db, fake, user, gmail_account, mail_store):
    fake.gmail.add_mail(subject="Chào đại ca")

    class Job:
        user_id = user.user_id

    assert service.run_initial_sync(db, Job())["gmail"] == 1
    state = _state(db, gmail_account)
    assert state.initial_sync_state == "done"
    fake.gmail.add_mail(subject="Thư sau")
    state.next_sync_at = clock.now() - timedelta(seconds=1)
    state.last_sync_at = clock.now() - timedelta(minutes=6)
    assert service.sync_due(db, "gmail", 300) == 1


def test_needs_gmail_pack(db, user, fake, account):
    with pytest.raises(GoogleNotConnected):
        gmail.search(db, user.user_id, "from:lan")


def test_search_returns_metadata(db, fake, gmail_account):
    fake.gmail.add_mail(subject="Báo giá tour", sender="Hùng <hung@tour.vn>")
    fake.gmail.add_mail(subject="Chuyện khác")
    [hit] = gmail.search(db, gmail_account.user_id, "from:hung@tour.vn")
    assert hit["subject"] == "Báo giá tour" and hit["from_email"] == "hung@tour.vn" and hit["thread_id"]
    with pytest.raises(ValidationError):
        gmail.search(db, gmail_account.user_id, "  ")


def test_get_thread_strips_html_and_suggests_reply(db, fake, gmail_account):
    box = fake.gmail
    box.add_mail(subject="Lịch họp", text="Thứ 5 họp nhé", thread_id="th1", sender="Lan <lan@example.com>")
    box.add_mail(
        subject="Re: Lịch họp",
        thread_id="th1",
        sender="Gia Bảo <dai.ca@gmail.com>",
        to="lan@example.com",
        text="Ok",
        at_ms=1795000100000,
    )
    box.add_mail(
        subject="Re: Lịch họp",
        thread_id="th1",
        sender="Lan <lan@example.com>",
        html="<p>Dời sang <b>9h</b></p><script>x()</script>",
        at_ms=1795000200000,
        message_id_header="<cuoi@mail.example.com>",
    )
    t = gmail.get_thread(db, gmail_account.user_id, "th1")
    assert t["subject"] == "Lịch họp" and [m["text"] for m in t["messages"]][-1] == "Dời sang 9h"
    assert t["reply"] == {
        "to": ["lan@example.com"],
        "cc": [],
        "subject": "Re: Lịch họp",
        "in_reply_to": "<cuoi@mail.example.com>",
    }


def test_get_thread_caps_text_keeping_newest(db, fake, gmail_account):
    fake.gmail.add_mail(thread_id="th2", text="a" * 3000)
    fake.gmail.add_mail(thread_id="th2", text="b" * 3000, at_ms=1795000100000)
    t = gmail.get_thread(db, gmail_account.user_id, "th2")
    texts = [m["text"] for m in t["messages"]]
    assert sum(len(x) for x in texts) <= gmail.THREAD_TEXT_MAX and texts[1] == "b" * 3000


def test_reply_draft_threads_and_hash_matches_gmail(db, fake, gmail_account):
    fake.gmail.add_mail(subject="Lịch họp", thread_id="th1", message_id_header="<goc@mail.example.com>")
    d = gmail.create_draft(
        db,
        gmail_account.user_id,
        to=["Lan@Example.com"],
        cc=[],
        subject="",
        body="Được nhé.",
        thread_id="th1",
    )
    assert d["subject"] == "Re: Lịch họp" and d["to"] == ["lan@example.com"] and d["thread_id"] == "th1"
    raw = fake.gmail.draft_text(d["google_draft_id"])
    assert "In-Reply-To: <goc@mail.example.com>" in raw and "References: <goc@mail.example.com>" in raw
    assert fake.gmail.drafts[d["google_draft_id"]]["threadId"] == "th1"
    assert gmail.read_draft(db, gmail_account.user_id, d["google_draft_id"])["body_hash"] == d["body_hash"]


def test_send_only_when_draft_unchanged(db, fake, gmail_account):
    d = gmail.create_draft(
        db, gmail_account.user_id, to=["lan@example.com"], cc=["hung@tour.vn"], subject="Hỏi", body="Chào Lan"
    )
    sent = gmail.send_draft(db, gmail_account.user_id, d["google_draft_id"], d["body_hash"])
    assert sent["message_id"] and len(fake.gmail.sent) == 1

    d2 = gmail.create_draft(
        db, gmail_account.user_id, to=["lan@example.com"], cc=[], subject="Hai", body="Một"
    )
    fake.gmail.edit_draft(d2["google_draft_id"], "Nội dung khác")
    with pytest.raises(gmail.DraftChanged) as exc:
        gmail.send_draft(db, gmail_account.user_id, d2["google_draft_id"], d2["body_hash"])
    assert exc.value.code == "ACTION_PAYLOAD_CHANGED" and len(fake.gmail.sent) == 1


def test_update_and_delete_draft(db, fake, gmail_account):
    d = gmail.create_draft(db, gmail_account.user_id, to=["lan@example.com"], cc=[], subject="A", body="Một")
    u = gmail.update_draft(
        db,
        gmail_account.user_id,
        d["google_draft_id"],
        to=["lan@example.com"],
        cc=[],
        subject="A",
        body="Hai",
    )
    assert u["body_hash"] != d["body_hash"] and "Hai" in fake.gmail.draft_text(d["google_draft_id"])
    gmail.delete_draft(db, gmail_account.user_id, d["google_draft_id"])
    gmail.delete_draft(db, gmail_account.user_id, d["google_draft_id"])  # mất rồi vẫn ổn
    assert not fake.gmail.drafts
    with pytest.raises(gmail.DraftChanged):
        gmail.send_draft(db, gmail_account.user_id, d["google_draft_id"], u["body_hash"])


def test_draft_validation(db, fake, gmail_account):
    with pytest.raises(ValidationError):
        gmail.create_draft(db, gmail_account.user_id, to=[], cc=[], subject="A", body="x")
    with pytest.raises(ValidationError):
        gmail.create_draft(db, gmail_account.user_id, to=["khong-phai-email"], cc=[], subject="A", body="x")
    with pytest.raises(ValidationError):
        gmail.create_draft(db, gmail_account.user_id, to=["lan@example.com"], cc=[], subject=" ", body="x")


def test_vietnamese_body_round_trips(db, fake, gmail_account):
    body = "Chào Lan,\nTuần sau đi Phước Hải nhé.\n"
    d = gmail.create_draft(
        db, gmail_account.user_id, to=["lan@example.com"], cc=[], subject="Đi chơi", body=body
    )
    got = gmail.read_draft(db, gmail_account.user_id, d["google_draft_id"])
    assert got["body"].rstrip() == body.rstrip() and got["subject"] == "Đi chơi"
    raw = base64.urlsafe_b64decode(fake.gmail.drafts[d["google_draft_id"]]["raw"] + "==")
    assert b"Subject:" in raw
