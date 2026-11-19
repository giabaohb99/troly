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


def test_turn_finishes_when_app_disconnects_and_notice_lists_it(db, user, fake_claude, monkeypatch):
    """QĐ-41: app ngắt giữa chừng thì lượt vẫn chạy hết, tin được lưu, máy nhận notice chat_done."""
    import time

    from app.modules.notice import service as notice_service

    monkeypatch.setattr(service, "DELIVERY_GRACE_SECONDS", 0.2)
    cursor = notice_service.list_notices(db, user.user_id, None)["cursor"]
    fake_claude.script.append(text_reply("Em đã tổng hợp xong chi tiêu tháng 11."))
    prepared = service.prepare_turn(db, user, "tổng hợp chi tiêu tháng này", None, uuid.uuid4(), [])
    stream = service.stream_turn(prepared)
    assert next(stream).startswith("event: message.created")
    # App ngắt: không đọc tiếp luồng SSE nữa; luồng nền vẫn chạy hết lượt rồi bật notify_done.
    answer = None
    for _ in range(100):
        answer = db.scalar(select(Message).where(Message.role == "assistant", Message.notify_done.is_(True)))
        if answer is not None:
            break
        time.sleep(0.1)
    assert answer is not None and answer.text == "Em đã tổng hợp xong chi tiêu tháng 11."
    notices = notice_service.list_notices(db, user.user_id, cursor)["items"]
    done = [n for n in notices if n["kind"] == "chat_done"]
    assert done and done[0]["message_id"] == answer.id
    stream.close()


def test_no_chat_done_when_stream_delivered_or_json(auth_client, db, user, fake_claude, monkeypatch):
    """Lỗi thật 19/11: đang chat trong màn Trợ lý vẫn nhận thông báo. SSE giao trọn hoặc lượt JSON: không báo."""
    import time

    from app.modules.notice import service as notice_service

    monkeypatch.setattr(service, "DELIVERY_GRACE_SECONDS", 0.2)
    cursor = notice_service.list_notices(db, user.user_id, None)["cursor"]
    fake_claude.script.append(text_reply("Ghi rồi."))
    assert send(auth_client, "cơm trưa 45k", stream=True).status_code == 200
    fake_claude.script.append(text_reply("Ghi tiếp."))
    assert send(auth_client, "cà phê 30k").status_code == 200
    time.sleep(0.5)
    assert db.scalars(select(Message).where(Message.notify_done.is_(True))).all() == []
    notices = notice_service.list_notices(db, user.user_id, cursor)["items"]
    assert [n for n in notices if n["kind"] == "chat_done"] == []


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


# ---------- Thẻ duyệt không kẹt (lỗi thật S25+: chuyến bị xóa tay trước khi duyệt) ----------


def _card(db, user, tool_name="delete_trip", conversation_id=None):
    out = service.create_pending_action(
        db,
        user.user_id,
        tool_name,
        {"trip_id": 999},
        title="Xóa chuyến Vũng Tàu",
        summary="Xóa hẳn chuyến",
        details=[],
        danger=True,
        conversation_id=conversation_id,
    )
    return out["pending_action"]["id"] if "pending_action" in out else out["id"]


def _gone_executor(monkeypatch):
    from app import registry
    from app.core.errors import NotFoundError

    def gone(session, user, input_):
        raise NotFoundError()

    monkeypatch.setattr(registry, "approval_executor", lambda name: gone)


def test_approving_delete_of_vanished_item_is_done(db, user, monkeypatch):
    _gone_executor(monkeypatch)
    out = service.decide_action(db, user, _card(db, user), approve=True)
    assert out["action"]["status"] == "done" and out["result_text"] == "Đã không còn, không cần xóa."


def test_failed_card_can_be_dismissed_and_repeats_are_idempotent(db, user, monkeypatch):
    from app.modules.chat.models import PendingAction

    action_id = _card(db, user, tool_name="share_drive_file")
    row = db.get(PendingAction, action_id)
    row.status, row.error = "failed", "Chưa nối Google Drive."
    again = service.decide_action(db, user, action_id, approve=True)  # bấm Thử lại: không 409
    assert again["action"]["status"] == "failed" and again["result_text"] == "Chưa nối Google Drive."
    dismissed = service.decide_action(db, user, action_id, approve=False)
    assert dismissed["action"]["status"] == "rejected"
    repeat = service.decide_action(db, user, action_id, approve=False)
    assert repeat["action"]["status"] == "rejected" and repeat["result_text"] == "Đã bỏ."


def test_history_shows_current_card_state(auth_client, db, user, fake_claude, monkeypatch):
    from app.ai.tests.fake_claude import tool_call

    _gone_executor(monkeypatch)
    fake_claude.script.extend(
        [
            tool_call("delete_trip", {"trip_id": 999, "reason": "không đi nữa"}),
            text_reply("Em đã soạn thẻ xóa, đại ca bấm Duyệt."),
        ]
    )
    monkeypatch.setattr(
        "app.modules.trip.tools.service.get_trip",
        lambda s, u, tid: {"title": "Vũng Tàu", "start_date": None, "days": []},
    )
    resp = send(auth_client, "xóa chuyến Vũng Tàu")
    assert resp.status_code == 200, resp.text
    card = next(a for a in resp.json()["data"]["assistant_message"]["actions"] if a["type"] == "confirm")
    ok = auth_client.post(f"/api/v1/chat/actions/{card['pending_action_id']}/approve")
    assert ok.status_code == 200 and ok.json()["data"]["action"]["status"] == "done"
    assert auth_client.post(f"/api/v1/chat/actions/{card['pending_action_id']}/approve").status_code == 200
    today = auth_client.get("/api/v1/chat/today").json()["data"]
    shown = [a for m in today["messages"] for a in m["actions"] if a["type"] == "confirm"]
    assert (
        shown and shown[0]["status"] == "done" and shown[0]["result_text"] == "Đã không còn, không cần xóa."
    )
    assert shown[0]["decided_at"] == ok.json()["data"]["action"]["decided_at"]


def test_user_attachments_get_file_meta_and_card_shows_error(db, user):
    from app.modules.chat.models import PendingAction
    from app.modules.file.models import File

    f = File(
        user_id=user.user_id,
        r2_key="files/u/x.docx",
        original_name="Lich-trinh.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=4096,
        purpose="chat_attachment",
        status="ready",
    )
    db.add(f)
    db.flush()
    msgs = service.with_file_meta(db, user.user_id, [{"attachments": [{"file_id": f.id}], "actions": []}])
    assert msgs[0]["attachments"] == [
        {"file_id": f.id, "mime": f.mime, "name": "Lich-trinh.docx", "size_bytes": 4096}
    ]
    action_id = _card(db, user, tool_name="share_drive_file")
    row = db.get(PendingAction, action_id)
    row.status, row.error = "failed", "Chưa nối Google Drive."
    assert service.serialize_pending(row)["error"] == "Chưa nối Google Drive."


def test_compaction_failure_does_not_block_turn(auth_client, db, fake_claude, monkeypatch):
    from app.ai import compaction
    from app.ai.schemas import AiError

    def broken(*a, **k):
        raise AiError("AI_UNAVAILABLE", "JSON tóm tắt hỏng")

    monkeypatch.setattr(compaction, "should_compact", lambda *a, **k: True)
    monkeypatch.setattr(compaction, "choose_cut", lambda messages: 1)
    monkeypatch.setattr(compaction, "summarize", broken)
    fake_claude.script.append(text_reply("Chào đại ca."))
    send(auth_client, "chào em")  # có lịch sử để có thứ cần nén
    fake_claude.script.append(text_reply("Vẫn trả lời được."))
    resp = send(auth_client, "hôm nay thế nào")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["assistant_message"]["text"] == "Vẫn trả lời được."


def test_ok_after_trip_plan_turn_stays_on_sonnet(auth_client, fake_claude):
    """Lỗi thật S25+: bot đề nghị tìm thêm, người dùng *Oke*, lượt sau rơi về Haiku và hứa suông."""
    fake_claude.script.append(text_reply("Đại ca đi ngày nào, xuất phát từ đâu?"))
    assert send(auth_client, "tạo lịch trình đi Vũng Tàu 2 ngày").status_code == 200
    fake_claude.script.append(text_reply("Em đã dựng xong chuyến."))
    assert send(auth_client, "Oke").status_code == 200
    assert [r["model"] for r in fake_claude.requests] == ["claude-sonnet-5-5", "claude-sonnet-5-5"]
    fake_claude.script.append(text_reply("Dạ."))
    assert send(auth_client, "cảm ơn em").status_code == 200
    assert fake_claude.requests[-1]["model"] == "claude-haiku-5-5"  # bot không còn chờ đáp: về Haiku


def test_pasted_api_key_never_stored_or_sent(auth_client, db, fake_claude):
    """QĐ-46: tin có khóa AIza giả thì DB và yêu cầu gửi Claude không chứa khóa; lượt có luật nhắc đổi khóa."""
    from app.ai.prompt import SECRET_RULES
    from app.ai.redact import KEY_MASK

    key = "AIza" + "SyD3mo0nlyFakeKeyForTests0000000000"
    fake_claude.script.append(
        text_reply("Em không lưu khóa qua chat; đại ca tạo khóa mới rồi nhập ở Cài đặt nhé.")
    )
    resp = send(auth_client, f"đây là khóa gemini của anh {key} lưu giúp em")
    assert resp.status_code == 200, resp.text
    assert key not in resp.text and KEY_MASK in resp.json()["data"]["user_message"]["text"]
    rows = db.scalars(select(Message)).all()
    assert all(key not in (m.text or "") and key not in str(m.content) for m in rows)
    sent = str(fake_claude.requests[0])
    assert key not in sent and KEY_MASK in sent and SECRET_RULES in sent
