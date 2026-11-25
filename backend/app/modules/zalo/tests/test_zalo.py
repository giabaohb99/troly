"""QĐ-52: Zalo qua zalo-bridge (bridge giả bằng httpx.MockTransport, hợp đồng 50 mục 3.15)."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from moto import mock_aws

from app.core import storage
from app.core.config import get_settings
from app.integrations.zalo_bridge import client as bridge
from app.modules.inbox import service as inbox_service
from app.modules.inbox.models import InboxMessage
from app.modules.zalo import jobs
from app.modules.zalo import service as zalo_service

TOKEN = "zalo-bridge-token-thu"
T0 = datetime(2026, 11, 25, 3, 0, tzinfo=UTC)


class FakeBridge:
    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.state = "logged_in"
        self.send_error: tuple[int, dict] | None = None
        self.media = {"https://f.zdn.vn/a.jpg": (b"\xff\xd8anh", "image/jpeg", "a.jpg")}
        self.group_items: list[dict] = []
        self.next_msg = 9000
        self.contacts = [{"thread_id": "g1", "thread_type": "group", "name": "Nhà mình", "avatar": None}]

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401, json={"success": False, "data": {"code": "UNAUTHORIZED"}})
        path, body = request.url.path, json.loads(request.content or b"{}")
        if path == "/login/status":
            return self.ok({"state": self.state, "account": {"uid": "u-me", "name": "Gia Bảo"}})
        if path == "/login/qr":
            if self.state == "logged_in":
                return httpx.Response(409, json={"success": False, "data": {"code": "ALREADY_LOGGED_IN"}})
            return self.ok(
                {"state": "waiting_scan", "qr_png_base64": "iVBOR", "qr_expires_at": "2026-11-25T03:05:00Z"}
            )
        if path == "/logout":
            self.state = "logged_out"
            return self.ok({"state": "logged_out"})
        if path == "/conversations":
            return self.ok({"items": self.contacts})
        if path == "/conversations/g1/messages":
            return self.ok({"items": self.group_items})
        if path == "/sync/old-messages":
            return self.ok({"requested": True})
        if path == "/messages":
            if self.send_error:
                return httpx.Response(self.send_error[0], json={"success": False, "data": self.send_error[1]})
            self.next_msg += 1
            return self.ok(
                {"msg_ids": [str(self.next_msg)], "cli_msg_ids": [], "client_ref": body.get("client_ref")}
            )
        if path == "/media/fetch":
            data, mime, name = self.media[body["url"]]
            return httpx.Response(200, content=data, headers={"content-type": mime, "x-file-name": name})
        return httpx.Response(404, json={"success": False, "data": {"code": "THREAD_NOT_FOUND"}})

    @staticmethod
    def ok(data):
        return httpx.Response(200, json={"success": True, "message": "", "data": data})

    def sent(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.url.path == "/messages"]


@pytest.fixture
def fake(monkeypatch):
    fb = FakeBridge()
    monkeypatch.setenv("ZALO_BRIDGE_TOKEN", TOKEN)
    get_settings.cache_clear()
    bridge.set_transport(httpx.MockTransport(fb.handle))
    yield fb
    bridge.set_transport(None)
    get_settings.cache_clear()


def msg(msg_id, text="Mai đi cafe không", *, thread="u-lan", kind="user", from_name="Lan", is_self=False,
        at=T0, content=None, thread_name=None):  # fmt: skip
    return {
        "event_id": f"msg:{msg_id}",
        "kind": "message",
        "ts": at.isoformat().replace("+00:00", "Z"),
        "thread_id": thread,
        "thread_type": kind,
        "msg_id": msg_id,
        "cli_msg_id": f"c{msg_id}",
        "thread_name": thread_name or (from_name if kind == "user" else "Nhà mình"),
        "from_uid": "u-me" if is_self else f"uid-{from_name}",
        "from_name": "Gia Bảo" if is_self else from_name,
        "is_self": is_self,
        "content": content or {"type": "text", "text": text},
    }


def post_events(client, events, token=TOKEN):
    return client.post(
        "/api/v1/internal/zalo/events", json={"events": events}, headers={"Authorization": f"Bearer {token}"}
    )


def test_events_need_bridge_token(client, user, fake):
    assert post_events(client, [msg("1")], token="sai").status_code == 401
    assert client.post("/api/v1/internal/zalo/events", json={"events": []}).status_code == 401


def test_message_events_saved_deduped_and_bad_ones_rejected(client, auth_client, db, user, fake):
    events = [
        msg("1"),
        msg("1"),  # bridge gửi lại: bỏ trùng theo msg_id
        msg("2", "Ok 8h nhé", is_self=True, at=T0 + timedelta(minutes=1)),
        msg("3", "Mã xác thực của bạn là 482913", at=T0 + timedelta(minutes=2)),  # OTP: không lưu
        {"event_id": "x", "kind": "la"},
        {
            "event_id": "msg:4",
            "kind": "message",
            "ts": "khong-phai-ngay",
            "thread_id": "u-lan",
            "msg_id": "4",
        },
        {"event_id": "session:logged_in:1", "kind": "session", "state": "logged_in"},
        {
            "event_id": "seen:u-lan:2:x",
            "kind": "seen",
            "thread_id": "u-lan",
            "thread_type": "user",
            "msg_ids": ["2"],
        },
    ]
    out = post_events(client, events).json()["data"]
    assert out["accepted"] == 6 and [r["event_id"] for r in out["rejected"]] == ["x", "msg:4"]
    rows = db.query(InboxMessage).filter_by(source="zalo").order_by(InboxMessage.posted_at).all()
    assert [(r.text, r.is_self, r.status, r.conversation_key) for r in rows] == [
        ("Mai đi cafe không", False, "seen", "zalo:u:u-lan"),  # mình đã trả lời: coi như đã đọc
        ("Ok 8h nhé", True, "seen", "zalo:u:u-lan"),
    ]
    [conv] = auth_client.get("/api/v1/inbox/conversations", params={"app": "zalo"}).json()["data"]["items"]
    assert (conv["title"], conv["unread_count"]) == ("Lan", 0)
    items = auth_client.get("/api/v1/inbox/conversations/zalo:u:u-lan/messages").json()["data"]["items"]
    assert {m["text"]: (m["is_self"], m["sender"]) for m in items} == {
        "Ok 8h nhé": (True, None),
        "Mai đi cafe không": (False, "Lan"),
    }


def test_bridge_message_replaces_notification_copy_and_moves_history(client, db, user, fake):
    from app.core.context import UserContext

    u = UserContext(user_id=user.user_id, timezone=user.timezone)
    zalo = {"parser": "zalo", "app_package": "com.zing.zalo"}
    inbox_service.ingest_notification(db, u, **zalo, payload={"title": "Lan", "text": "Hôm qua vui ghê"},
                                      posted_at=T0 - timedelta(days=1))  # fmt: skip
    inbox_service.ingest_notification(db, u, **zalo, payload={"title": "Lan", "text": "Mai đi cafe không"},
                                      posted_at=T0 + timedelta(seconds=20))  # fmt: skip
    old_key = db.query(InboxMessage).filter_by(source="notification").first().conversation_key
    inbox_service.create_rule(db, user.user_id, "private_conversation", old_key, None)
    assert post_events(client, [msg("1")]).status_code == 200
    rows = db.query(InboxMessage).filter_by(user_id=user.user_id).order_by(InboxMessage.posted_at).all()
    assert [(r.source, r.text, r.conversation_key) for r in rows] == [
        ("notification", "Hôm qua vui ghê", "zalo:u:u-lan"),  # lịch sử cũ theo sang hội thoại Zalo thật
        ("zalo", "Mai đi cafe không", "zalo:u:u-lan"),  # bản thông báo trùng đã thay bằng tin bridge
    ]
    assert "zalo:u:u-lan" in inbox_service.private_keys(db, user.user_id)  # luật riêng tư đi theo
    # Thông báo về sau của cùng tin: bỏ.
    again = inbox_service.ingest_notification(db, u, **zalo, payload={"title": "Lan", "text": "Mai đi cafe không"},
                                              posted_at=T0 + timedelta(minutes=1))  # fmt: skip
    assert again["created"] == 0


def test_undo_recalls_message(client, auth_client, db, user, fake):
    post_events(client, [msg("1", "Gửi nhầm")])
    undo = {"event_id": "undo:1", "kind": "undo", "ts": "2026-11-25T03:01:00Z", "thread_id": "u-lan",
            "thread_type": "user", "msg_id": "1", "undo_msg_id": "1"}  # fmt: skip
    assert post_events(client, [undo]).json()["data"]["accepted"] == 1
    [m] = auth_client.get("/api/v1/inbox/conversations/zalo:u:u-lan/messages").json()["data"]["items"]
    assert m["text"] == "(Tin đã thu hồi)" and m["recalled_at"]


def test_media_fetched_to_r2_by_job(client, auth_client, db, user, fake, monkeypatch):
    import boto3

    image = {
        "type": "image",
        "text": "Ảnh quán",
        "media": {"url": "https://f.zdn.vn/a.jpg", "name": "a.jpg", "size": 6},
    }
    post_events(client, [msg("5", content=image)])
    row = db.query(InboxMessage).filter_by(external_id="5").one()
    assert row.media_pending and row.text == "[Ảnh] Ảnh quán"
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=get_settings().r2_bucket)
        monkeypatch.setattr(storage, "_client", lambda: s3)
        assert jobs.fetch_media_due() == 1
    db.expire_all()
    [m] = auth_client.get("/api/v1/inbox/conversations/zalo:u:u-lan/messages").json()["data"]["items"]
    [media] = m["media"]
    assert (media["status"], media["mime"], media["size"]) == ("done", "image/jpeg", 5) and media["file_id"]
    assert "url" not in media  # không trả link CDN của Zalo
    assert jobs.fetch_media_due() == 0


def test_status_login_logout_contacts(auth_client, fake):
    st = auth_client.get("/api/v1/zalo/status").json()["data"]
    assert st["state"] == "logged_in" and st["account"]["name"] == "Gia Bảo"
    assert auth_client.post("/api/v1/zalo/login").status_code == 409  # đã đăng nhập
    assert auth_client.post("/api/v1/zalo/logout").json()["data"]["state"] == "logged_out"
    qr = auth_client.post("/api/v1/zalo/login").json()["data"]
    assert qr["state"] == "waiting_scan" and qr["qr_png_base64"]
    [c] = auth_client.get("/api/v1/zalo/contacts").json()["data"]["items"]
    assert c["conversation_key"] == "zalo:g:g1"
    bridge.set_transport(httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("tắt"))))
    assert auth_client.get("/api/v1/zalo/status").json()["data"]["state"] == "unavailable"


def test_user_send_goes_straight_and_errors_are_vietnamese(auth_client, fake):
    resp = auth_client.post(
        "/api/v1/zalo/messages", json={"conversation_key": "zalo:u:u-lan", "text": "Dạ em tới"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["msg_ids"] == ["9001"]
    assert fake.sent()[-1] == {"thread_id": "u-lan", "thread_type": "user", "text": "Dạ em tới",
                               "client_ref": resp.json()["data"]["client_ref"]}  # fmt: skip
    fake.send_error = (429, {"code": "RATE_LIMITED", "retry_after": 30})
    limited = auth_client.post(
        "/api/v1/zalo/messages", json={"conversation_key": "zalo:u:u-lan", "text": "x"}
    )
    assert limited.status_code == 429 and "30 giây" in limited.json()["message"]
    fake.send_error = (409, {"code": "NOT_LOGGED_IN"})
    out = auth_client.post("/api/v1/zalo/messages", json={"conversation_key": "zalo:u:u-lan", "text": "x"})
    assert out.status_code == 409 and "quét mã QR" in out.json()["message"]
    assert (
        auth_client.post(
            "/api/v1/zalo/messages", json={"conversation_key": "gmail:t1", "text": "x"}
        ).status_code
        == 400
    )
    assert (
        auth_client.post("/api/v1/zalo/messages", json={"conversation_key": "zalo:u:u-lan"}).status_code
        == 400
    )


def test_bot_send_needs_approval_card(client, db, user, fake):
    from app.core.context import UserContext
    from app.modules.chat import service as chat_service

    u = UserContext(user_id=user.user_id, timezone=user.timezone)
    post_events(client, [msg("1")])
    card = zalo_service.request_send(db, u, conversation_key="zalo:u:u-lan", text="Dạ mai em tới")[
        "pending_action"
    ]
    assert card["tool_name"] == "send_zalo_message" and fake.sent() == []  # chưa duyệt thì chưa gửi
    assert {"label": "Gửi tới", "value": "Lan"} in card["details"]
    chat_service.decide_action(db, u, card["id"], approve=True)
    assert fake.sent()[-1]["text"] == "Dạ mai em tới"


def test_group_history_sync_and_user_request(auth_client, db, user, fake):
    fake.group_items = [
        {k: v for k, v in msg("g-1", "Chào cả nhà", thread="g1", kind="group", from_name="Mẹ").items()
         if k not in ("event_id", "kind")},
    ]  # fmt: skip
    out = auth_client.post("/api/v1/zalo/conversations/zalo:g:g1/sync").json()["data"]
    assert out == {"mode": "group_history", "saved": 1}
    row = db.query(InboxMessage).filter_by(external_id="g-1").one()
    assert (row.is_group, row.sender, row.conversation_title) == (True, "Mẹ", "Nhà mình")
    assert (
        auth_client.post("/api/v1/zalo/conversations/zalo:u:u-lan/sync").json()["data"]["mode"] == "requested"
    )


def test_notification_threads_linked_to_zalo_contacts_by_name(db, user, fake):
    """Cuộc Zalo đọc từ thông báo không gửi được (không có mã cuộc). Khớp tên với danh bạ Zalo: trùng đúng một người
    hoặc nhóm thì kéo cả cuộc sang khóa Zalo thật để nhắn được; tin thông báo về sau cũng vào khóa đó."""
    from app.core.context import UserContext

    u = UserContext(user_id=user.user_id, timezone=user.timezone)
    zalo = {"parser": "zalo", "app_package": "com.zing.zalo"}
    fake.contacts += [
        {"thread_id": "u-lan", "thread_type": "user", "name": "Lan", "avatar": None},
        {"thread_id": "u-minh1", "thread_type": "user", "name": "Minh", "avatar": None},
        {"thread_id": "u-minh2", "thread_type": "user", "name": "Minh", "avatar": None},
    ]
    for name in ("Lan", "Minh", "Hùng"):
        inbox_service.ingest_notification(db, u, **zalo, payload={"title": name, "text": f"Chào {name}"},
                                          posted_at=T0)  # fmt: skip
    keys = {r.sender: r.conversation_key for r in db.query(InboxMessage).filter_by(user_id=user.user_id)}
    assert zalo_service.link_thread(db, u, keys["Lan"]) == "zalo:u:u-lan"
    assert zalo_service.link_thread(db, u, keys["Minh"]) is None  # hai người cùng tên: không đoán
    assert zalo_service.link_thread(db, u, keys["Hùng"]) is None  # không có trong danh bạ
    assert zalo_service.link_thread(db, u, "zalo:u:u-lan") == "zalo:u:u-lan"  # đã là khóa thật
    lan = db.query(InboxMessage).filter_by(sender="Lan").one()
    assert lan.conversation_key == "zalo:u:u-lan"
    inbox_service.ingest_notification(db, u, **zalo, payload={"title": "Lan", "text": "Tối nay rảnh không"},
                                      posted_at=T0 + timedelta(hours=1))  # fmt: skip
    later = db.query(InboxMessage).filter_by(text="Tối nay rảnh không").one()
    assert later.conversation_key == "zalo:u:u-lan"
    assert zalo_service.link_all_threads(db, u) == {"linked": 0, "unmatched": 2}


def test_reading_or_replying_elsewhere_marks_thread_seen(client, db, user, fake):
    """Đọc trên Zalo PC, điện thoại: nhóm thì Zalo báo đã xem có mã của mình; một-một thì mình trả lời là đã đọc."""
    from app.modules.zalo.models import ZaloAccount

    assert post_events(client, [msg("1", "Tối nay rảnh không")]).status_code == 200
    db.query(ZaloAccount).update({"zalo_uid": "u-me"})
    db.commit()
    assert db.query(InboxMessage).filter_by(external_id="1").one().status == "new"
    post_events(client, [msg("2", "Rảnh nè", is_self=True, at=T0 + timedelta(minutes=1))])
    db.expire_all()
    assert db.query(InboxMessage).filter_by(external_id="1").one().status == "seen"

    group = msg("3", "Mai họp 8h", thread="g1", kind="group", from_name="Tuấn", at=T0 + timedelta(minutes=2))
    post_events(client, [group])
    seen = {"event_id": "seen:g1:3:x", "kind": "seen", "ts": (T0 + timedelta(minutes=3)).isoformat(),
            "thread_id": "g1", "thread_type": "group", "msg_ids": ["3"], "seen_uids": ["uid-Lan"]}  # fmt: skip
    post_events(client, [seen])
    db.expire_all()
    assert db.query(InboxMessage).filter_by(external_id="3").one().status == "new"  # người khác xem: không đổi
    post_events(client, [{**seen, "event_id": "seen:g1:3:me", "seen_uids": ["uid-Lan", "u-me"]}])
    db.expire_all()
    assert db.query(InboxMessage).filter_by(external_id="3").one().status == "seen"
