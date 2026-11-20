"""QĐ-38: báo giao dịch mới, tin quan trọng; nhắc sự kiện Google; nhắc mặc định không rơi vào quá khứ."""

from datetime import UTC, datetime, timedelta

import pytest

from app.integrations.google.stores import RemoteEvent
from app.modules.calendar import service as calendar_service
from app.modules.calendar.google_store import STORE
from app.modules.expense import service as expense_service
from app.modules.expense.tests.samples import sample
from app.modules.inbox import service as inbox_service
from app.modules.notice import service
from app.modules.setting import service as setting_service


def _bank(db, user, sample_id):
    s = sample(sample_id)
    return expense_service.ingest_bank_notification(
        db,
        user,
        bank=s["parser"],
        package=s["package"],
        title=s["title"],
        text=s["text"],
        posted_at=s["posted_at"],
    )


def test_notices_first_call_only_cursor_then_enabled_kinds(db, user, monkeypatch):
    from app.core import clock

    monkeypatch.setattr(clock, "now", lambda: datetime(2026, 12, 2, 5, tzinfo=UTC))
    _bank(db, user, "vcb-chi-001")
    first = service.list_notices(db, user.user_id, None)
    assert first["items"] == []

    _bank(db, user, "momo-tt-001")
    inbox_service.create_rule(db, user.user_id, "vip_sender", "Mẹ", None)
    inbox_service.ingest_notification(
        db,
        user,
        parser="zalo",
        app_package="com.zing.zalo",
        payload={"title": "Mẹ", "text": "Con về ăn cơm nhé"},
        posted_at=datetime(2026, 12, 2, 4, tzinfo=UTC),
    )
    # Mặc định: giao dịch tắt, tin quan trọng bật.
    out = service.list_notices(db, user.user_id, first["cursor"])
    assert [(i["kind"], i["title"], i["body"]) for i in out["items"]] == [
        ("important_message", "Mẹ", "Con về ăn cơm nhé")
    ]
    assert out["items"][0]["deep_link"].startswith("troly://hop-tin/")
    assert service.list_notices(db, user.user_id, out["cursor"])["items"] == []

    setting_service.update(db, user.user_id, {"notify.new_transaction": True})
    again = service.list_notices(db, user.user_id, first["cursor"])
    tx = [i for i in again["items"] if i["kind"] == "transaction"]
    assert [(i["title"], i["body"]) for i in tx] == [("Đã ghi chi 35.000 đ", "Highlands Coffee")]
    assert tx[0]["deep_link"].startswith("troly://chi-tieu?sua=")


def test_notices_api_needs_device_token(auth_client):
    assert auth_client.get("/api/v1/device/notices").status_code == 401
    token = auth_client.post("/api/v1/devices", json={"name": "S25+"}).json()["data"]["device_token"]
    resp = auth_client.get("/api/v1/device/notices", headers={"Authorization": f"Device {token}"})
    assert resp.status_code == 200 and resp.json()["data"]["cursor"] == "0.0.0.0"


def test_app_can_remind_google_events_when_enabled(db, user):
    start = datetime.now(UTC) + timedelta(days=1)
    remote = RemoteEvent(
        google_event_id="g1",
        etag="e",
        updated=None,
        status="confirmed",
        title="Lịch Google",
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    STORE.write_remote(db, user.user_id, None, "primary", remote, None)
    now = datetime.now(UTC)
    off = calendar_service.list_reminders(db, user, now, 3)
    assert off["items"] == []
    setting_service.update(db, user.user_id, {"calendar.app_reminds_google": True})
    on = calendar_service.list_reminders(db, user, now, 3)
    assert [i["fire_at"] for i in on["items"]] == [start - timedelta(minutes=15)]
    assert on["revision"] != off["revision"]


@pytest.mark.parametrize(("minutes_ahead", "expected"), [(3, [0]), (30, [15]), (120, [15])])
def test_default_reminder_never_lands_in_the_past(db, user, minutes_ahead, expected):
    start = datetime.now(UTC) + timedelta(minutes=minutes_ahead)
    e = calendar_service.create_event(db, user, {"title": "Uống nước", "start_at": start})["event"]
    assert e["remind_minutes"] == expected
    explicit = calendar_service.create_event(
        db, user, {"title": "x", "start_at": start, "remind_minutes": [15]}
    )
    assert explicit["event"]["remind_minutes"] == [15]


def test_chat_done_reports_final_answer_and_exported_files(db, user):
    import uuid
    from datetime import date

    from app.modules.chat.models import Conversation, Message
    from app.modules.file.models import File

    start = service.list_notices(db, user.user_id, None)["cursor"]
    conv = Conversation(user_id=user.user_id, local_date=date(2026, 11, 19), started_at=datetime.now(UTC))
    db.add(conv)
    db.flush()
    f = File(
        user_id=user.user_id,
        r2_key="files/u/x.pdf",
        original_name="bao-cao.pdf",
        mime="application/pdf",
        size_bytes=10,
        purpose="document",
        status="ready",
    )
    db.add(f)
    db.flush()
    turn = uuid.uuid4()

    def msg(role, hidden, text_=None, content=None, notify_done=False):
        db.add(
            Message(
                user_id=user.user_id,
                conversation_id=conv.id,
                turn_id=turn,
                role=role,
                hidden=hidden,
                text=text_,
                content=content or [{"type": "text", "text": text_ or ""}],
                notify_done=notify_done,
            )
        )
        db.flush()

    msg("user", False, "Xuất báo cáo chi tiêu tháng này ra PDF")
    msg("assistant", True, "Đang xuất")
    msg(
        "user",
        True,
        content=[{"type": "tool_result", "content": f'{{"file_id": {f.id}, "name": "bao-cao.pdf"}}'}],
    )
    msg("assistant", False, "Em đã xuất báo cáo tháng 11. Tổng chi là 3.465.000 đ.", notify_done=True)

    out = service.list_notices(db, user.user_id, start)
    [item] = [i for i in out["items"] if i["kind"] == "chat_done"]
    assert item["created_at"] is not None and item["created_at"].tzinfo is not None
    assert item["body"] == "Em đã xuất báo cáo tháng 11." and item["file_ids"] == [f.id]
    assert item["conversation_id"] == conv.id and item["file_id"] == f.id
    assert item["deep_link"] == f"troly://?phien={conv.id}&tin={item['message_id']}"
    assert [
        i for i in service.list_notices(db, user.user_id, out["cursor"])["items"] if i["kind"] == "chat_done"
    ] == []

    setting_service.update(db, user.user_id, {"notify.chat_done": False})
    assert [
        i for i in service.list_notices(db, user.user_id, start)["items"] if i["kind"] == "chat_done"
    ] == []
    # Con trỏ cũ hai phần vẫn nhận, phần chat tính từ hiện tại.
    assert service.list_notices(db, user.user_id, "0.0")["cursor"].count(".") == 3


# ---------- QĐ-49: đặt chỗ tự thêm vào Lịch ----------

BOOKING_DDL = (
    "CREATE TEMP TABLE tab_booking (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint NOT NULL, "
    "created_at timestamptz NOT NULL DEFAULT now(), status text NOT NULL DEFAULT 'confirmed', "
    "calendar_state text NOT NULL, title text, start_at timestamptz, start_date date, event_id bigint, "
    "trip_id bigint) ON COMMIT DROP"
)


def _booking(db, user, state="added", event_id=41, title="Khách sạn Cửu Long", start_date=None):
    from sqlalchemy import text

    return db.execute(
        text(
            "INSERT INTO tab_booking (user_id, calendar_state, title, start_at, start_date, event_id) "
            "VALUES (:u, :s, :t, :at, :d, :e) RETURNING id"
        ),
        {
            "u": user.user_id,
            "s": state,
            "t": title,
            "at": None if start_date else datetime(2026, 11, 21, 7, tzinfo=UTC),
            "d": start_date,
            "e": event_id,
        },
    ).scalar_one()


def test_booking_added_notice_once_and_setting_off(db, user):
    from sqlalchemy import text

    assert service.list_notices(db, user.user_id, None)["cursor"].endswith(".0")  # chưa có bảng: phần 4 là 0
    db.execute(text(BOOKING_DDL))
    start = service.list_notices(db, user.user_id, None)["cursor"]
    bid = _booking(db, user)
    _booking(db, user, state="undone", event_id=42)  # đã hoàn tác: không báo
    _booking(db, user, state="none", event_id=None)  # thư hủy, thiếu ngày: không vào Lịch nên không báo
    _booking(db, user, event_id=None)  # chưa vào Lịch: không báo
    out = service.list_notices(db, user.user_id, start)
    [item] = [i for i in out["items"] if i["kind"] == "booking_added"]
    assert item == {
        "id": f"booking:{bid}",
        "kind": "booking_added",
        "created_at": item["created_at"],
        "title": "Đã thêm đặt chỗ vào Lịch",
        "body": "Khách sạn Cửu Long, T7 21/11 14:00",  # 07:00 UTC theo giờ Việt Nam
        "deep_link": "troly://lich/su-kien/41",
        "booking_id": bid,
        "event_id": 41,
    }
    assert [i for i in service.list_notices(db, user.user_id, out["cursor"])["items"]] == []
    from datetime import date

    _booking(db, user, event_id=43, title="Vé xe Phương Trang", start_date=date(2026, 11, 22))
    [day_only] = service.list_notices(db, user.user_id, out["cursor"])["items"]
    assert day_only["body"] == "Vé xe Phương Trang, CN 22/11"
    # Con trỏ cũ ba phần: phần đặt chỗ tính từ hiện tại, không báo dồn.
    old = ".".join(start.split(".")[:3])
    assert not [
        i for i in service.list_notices(db, user.user_id, old)["items"] if i["kind"] == "booking_added"
    ]
    setting_service.update(db, user.user_id, {"notify.booking_added": False})
    assert not [
        i for i in service.list_notices(db, user.user_id, start)["items"] if i["kind"] == "booking_added"
    ]


def test_undo_route_needs_device_token_and_calls_google_layer(auth_client, user, monkeypatch):
    import sys
    import types

    calls = []
    from app.core.errors import ConflictError

    def undo_booking(session, u, booking_id):
        calls.append((u.user_id, booking_id))
        if booking_id == 8:
            raise ConflictError("Sự kiện đã được sửa, hãy xóa trong Lịch nếu muốn.", code="BOOKING_EDITED")
        return {"undone": True}

    pkg = types.ModuleType("app.modules.booking")
    fake = types.ModuleType("app.modules.booking.service")
    fake.undo_booking = undo_booking
    pkg.service = fake
    monkeypatch.setitem(sys.modules, "app.modules.booking", pkg)
    monkeypatch.setitem(sys.modules, "app.modules.booking.service", fake)
    assert auth_client.post("/api/v1/device/bookings/7/undo").status_code == 401  # JWT không đủ, cần mã máy
    token = auth_client.post("/api/v1/devices", json={"name": "S25+"}).json()["data"]["device_token"]
    resp = auth_client.post("/api/v1/device/bookings/7/undo", headers={"Authorization": f"Device {token}"})
    assert resp.status_code == 200 and resp.json()["data"] == {"undone": True}
    edited = auth_client.post("/api/v1/device/bookings/8/undo", headers={"Authorization": f"Device {token}"})
    assert edited.status_code == 409 and edited.json()["data"]["code"] == "BOOKING_EDITED"
    assert calls == [(user.user_id, 7), (user.user_id, 8)]
