import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.ai import client as ai_client
from app.ai.tests.fake_claude import FakeClaude, text_reply
from app.core import clock
from app.modules.chat import repo, service
from app.modules.chat.models import Message


def vn(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=UTC) - timedelta(hours=7)


@pytest.fixture
def fake_claude(monkeypatch):
    from app.ai.models import DbRunRecorder

    fake = FakeClaude()
    monkeypatch.setattr(ai_client, "_client", ai_client.ClaudeClient(sdk=fake, recorder=DbRunRecorder()))
    return fake


def send(client, text, cid=None, stream=False):
    body = {"client_message_id": str(cid or uuid.uuid4()), "text": text}
    headers = {"accept": "text/event-stream"} if stream else {}
    return client.post("/api/v1/chat/messages", json=body, headers=headers)


def test_json_turn_saves_user_system_and_answer(auth_client, db, fake_claude):
    fake_claude.script.append(text_reply("Chào đại ca, em đây."))

    resp = send(auth_client, "chào em")

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["assistant_message"]["text"] == "Chào đại ca, em đây."
    assert data["assistant_message"]["model"]
    roles = [(m.role, m.hidden) for m in db.scalars(select(Message).order_by(Message.id))]
    assert roles == [("user", False), ("system", True), ("assistant", False)]
    today = auth_client.get("/api/v1/chat/today").json()["data"]
    assert [m["role"] for m in today["messages"]] == ["user", "assistant"]


def test_sse_event_order(auth_client, fake_claude):
    fake_claude.script.append(text_reply("Ghi rồi."))

    resp = send(auth_client, "cơm trưa 45k", stream=True)

    assert resp.status_code == 200
    events = [line.split(": ", 1)[1] for line in resp.text.splitlines() if line.startswith("event: ")]
    assert events[0] == "message.created"
    assert "text.delta" in events
    assert events[-1] == "message.completed"


def test_resend_same_client_id_replays_without_calling_claude(auth_client, fake_claude):
    cid = uuid.uuid4()
    fake_claude.script.append(text_reply("Một lần thôi."))
    first = send(auth_client, "hỏi", cid).json()["data"]

    again = send(auth_client, "hỏi", cid)

    assert again.status_code == 200
    assert again.json()["data"]["assistant_message"]["id"] == first["assistant_message"]["id"]
    assert len(fake_claude.requests) == 1


def test_missing_key_returns_ai_unavailable(auth_client, monkeypatch):
    monkeypatch.setattr(
        ai_client,
        "_client",
        ai_client.ClaudeClient(
            settings=ai_client.get_ai_settings().model_copy(update={"anthropic_api_key": ""})
        ),
    )

    resp = send(auth_client, "chào")

    assert resp.status_code == 502
    assert resp.json()["data"]["code"] == "AI_UNAVAILABLE"


def _yesterday_with_message(db, user, last_at):
    conv = repo.get_or_create_conversation(db, user.user_id, clock.chat_day(last_at, user.timezone), last_at)
    for role, text in (("user", "đi Trà Vinh không"), ("assistant", "Đi được đại ca")):
        db.add(
            Message(
                user_id=user.user_id,
                conversation_id=conv.id,
                turn_id=uuid.uuid4(),
                role=role,
                content=[{"type": "text", "text": text}],
                text=text,
            )
        )
    conv.last_message_at = last_at
    db.flush()


def test_prev_tail_joined_when_under_three_hours(db, user, monkeypatch):
    _yesterday_with_message(db, user, vn(2026, 11, 19, 2, 30))  # phiên ngày 18 (trước 04:00)
    monkeypatch.setattr(clock, "now", lambda: vn(2026, 11, 19, 4, 30))  # đã sang phiên ngày 19

    prepared = service.prepare_turn(db, user, "tiếp nha", None, uuid.uuid4(), [])
    service._release(user.user_id)

    assert [p.text for p in prepared.prev_tail] == ["đi Trà Vinh không", "Đi được đại ca"]


def test_prev_tail_empty_when_over_three_hours(db, user, monkeypatch):
    _yesterday_with_message(db, user, vn(2026, 11, 19, 1, 0))
    monkeypatch.setattr(clock, "now", lambda: vn(2026, 11, 19, 4, 30))

    prepared = service.prepare_turn(db, user, "chào", None, uuid.uuid4(), [])
    service._release(user.user_id)

    assert prepared.prev_tail == []


def test_message_before_4am_stays_in_previous_day(db, user, monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: vn(2026, 11, 19, 1, 0))

    prepared = service.prepare_turn(db, user, "khuya rồi", None, uuid.uuid4(), [])
    service._release(user.user_id)

    conv = repo.get_conversation(db, user.user_id, prepared.conversation_id)
    assert conv.local_date.isoformat() == "2026-11-18"


def test_failed_turn_left_out_of_next_history(auth_client, fake_claude, monkeypatch):
    from app.ai.schemas import AiError

    fake_claude.script.append(AiError("AI_UNAVAILABLE", "lỗi thử"))
    assert send(auth_client, "lượt hỏng").status_code == 502
    fake_claude.script.append(text_reply("Ổn rồi."))

    assert send(auth_client, "lượt sau").status_code == 200

    sent = fake_claude.requests[-1]["messages"]
    texts = [b.get("text") for m in sent if isinstance(m["content"], list) for b in m["content"]]
    assert "lượt hỏng" not in texts
    assert "lượt sau" in texts


def test_turn_finishes_when_app_disconnects_and_notice_lists_it(db, user, fake_claude):
    """QĐ-41: app ngắt giữa chừng thì lượt vẫn chạy hết, tin được lưu, máy nhận notice chat_done."""
    import time

    from app.modules.notice import service as notice_service

    cursor = notice_service.list_notices(db, user.user_id, None)["cursor"]
    fake_claude.script.append(text_reply("Em đã tổng hợp xong chi tiêu tháng 11."))
    prepared = service.prepare_turn(db, user, "tổng hợp chi tiêu tháng này", None, uuid.uuid4(), [])
    stream = service.stream_turn(prepared)
    assert next(stream).startswith("event: message.created")
    # App ngắt: không đọc tiếp luồng SSE nữa; luồng nền vẫn chạy hết lượt.
    answer = None
    for _ in range(100):
        answer = db.scalar(select(Message).where(Message.role == "assistant", Message.status == "complete"))
        if answer is not None:
            break
        time.sleep(0.1)
    assert answer is not None and answer.text == "Em đã tổng hợp xong chi tiêu tháng 11."
    notices = notice_service.list_notices(db, user.user_id, cursor)["items"]
    done = [n for n in notices if n["kind"] == "chat_done"]
    assert done and done[0]["message_id"] == answer.id
    stream.close()


def test_exported_file_shows_as_assistant_attachment():
    msg = Message(
        role="assistant",
        text="Em đã xuất báo cáo.",
        attachment_file_ids=None,
        actions=[
            {
                "id": "a1",
                "type": "file",
                "label": "Bao-cao.pdf",
                "file_id": 9,
                "name": "Bao-cao.pdf",
                "mime": "application/pdf",
                "size_bytes": 2048,
            },
            {"id": "a2", "type": "open_screen", "label": "Mở Báo cáo", "screen": "report", "params": {}},
        ],
    )
    assert service.serialize_message(msg)["attachments"] == [
        {"file_id": 9, "mime": "application/pdf", "name": "Bao-cao.pdf", "size_bytes": 2048}
    ]
