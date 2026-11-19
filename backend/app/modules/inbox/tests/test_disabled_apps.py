"""QĐ-42: hộp tin bỏ Telegram, Messenger. Tin cũ không xóa, chỉ ẩn; bật lại thì hiện."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from app.core import clock
from app.modules.device import service as device_service
from app.modules.inbox import service
from app.modules.inbox.models import InboxMessage
from app.modules.notice import service as notice_service
from app.modules.search import service as search

AT = datetime(2026, 11, 19, 3, 0, tzinfo=UTC)


def ingest(db, user, parser, package, sender, body):
    return service.ingest_notification(
        db, user, parser=parser, app_package=package, payload={"title": sender, "text": body}, posted_at=AT
    )


def test_defaults_turn_off_telegram_and_messenger(db, user):
    apps = {a["package_name"]: a["enabled"] for a in device_service.list_listened_apps(db, user.user_id)}
    assert apps["org.telegram.messenger"] is False and apps["com.facebook.orca"] is False
    assert apps["com.zing.zalo"] is True and apps["sms_default"] is True


def test_old_messages_hidden_everywhere_and_back_when_enabled(db, user):
    device_service.ensure_listened_apps(db, user.user_id)
    # Tin đã lưu trước QĐ-42 (lúc hai app còn bật).
    ingest(db, user, "telegram", "org.telegram.messenger", "Nam", "Họp dự án lúc 9 giờ")
    ingest(db, user, "messenger", "com.facebook.orca", "Hoa", "Họp lớp cuối tuần")
    ingest(db, user, "zalo", "com.zing.zalo", "Lan", "Họp gia đình tối nay")
    db.execute(text("UPDATE tab_inbox_message SET importance = 'important'"))
    assert db.query(InboxMessage).count() == 3

    convs = service.list_conversations(db, user.user_id, {}, None)["items"]
    assert [c["app"] for c in convs] == ["zalo"]
    assert [m["app"] for m in service.list_messages_for_ai(db, user.user_id)["items"]] == ["zalo"]
    assert {h["title"] for h in search.search(db, user.user_id, "hop", ["inbox"])} == {"Lan"}
    tg_key = db.query(InboxMessage.conversation_key).filter(InboxMessage.app == "telegram").scalar()
    assert service.list_messages(db, user.user_id, tg_key, None)["items"] == []
    notices = notice_service.list_notices(db, user.user_id, "0.0.0")["items"]
    assert [n["title"] for n in notices if n["kind"] == "important_message"] == ["Lan"]

    tg = next(a for a in device_service.list_listened_apps(db, user.user_id) if a["parser"] == "telegram")
    device_service.update_listened_app(db, user.user_id, tg["id"], {"enabled": True})
    assert sorted(c["app"] for c in service.list_conversations(db, user.user_id, {}, None)["items"]) == [
        "telegram",
        "zalo",
    ]


def test_events_from_disabled_apps_are_rejected(auth_client):
    token = auth_client.post("/api/v1/devices", json={"name": "S25+"}).json()["data"]["device_token"]
    event = {
        "client_event_id": str(uuid.uuid4()),
        "kind": "notification",
        "app_package": "org.telegram.messenger",
        "posted_at": clock.now().isoformat(),
        "payload": {"title": "Nam", "text": "chào"},
    }
    resp = auth_client.post(
        "/api/v1/device/events", json={"events": [event]}, headers={"Authorization": f"Device {token}"}
    )
    assert resp.json()["data"]["rejected"][0]["code"] == "APP_NOT_LISTENED"
