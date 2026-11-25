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


def _old_conversation(db, user, last_at, title=None):
    conv = repo.create_conversation(db, user.user_id, clock.chat_day(last_at, user.timezone), last_at, title)
    turn = uuid.uuid4()
    for role, text in (("user", "đi Trà Vinh không"), ("assistant", "Đi được đại ca")):
        db.add(
            Message(
                user_id=user.user_id,
                conversation_id=conv.id,
                turn_id=turn,
                role=role,
                content=[{"type": "text", "text": text}],
                text=text,
            )
        )
    conv.last_message_at, conv.message_count = last_at, 2
    db.flush()
    return conv


def test_no_split_at_4am_next_message_joins_latest_conversation(db, user, monkeypatch):
    """QĐ-51: không tách phiên lúc 04:00; tin không chỉ phiên vào phiên hoạt động gần nhất."""
    conv = _old_conversation(db, user, vn(2026, 11, 19, 1, 0))
    monkeypatch.setattr(clock, "now", lambda: vn(2026, 11, 20, 9, 0))

    prepared = service.prepare_turn(db, user, "tiếp nha", None, uuid.uuid4(), [])
    service._release(user.user_id)

    assert prepared.conversation_id == conv.id and prepared.prev_tail == []
    texts = [m["content"][0]["text"] for m in prepared.history if m["role"] == "user"]
    assert texts[:1] == ["đi Trà Vinh không"]  # phiên mở lại nạp lịch sử của chính nó


def test_send_to_chosen_old_conversation_and_unknown_is_404(auth_client, db, user, fake_claude):
    old = _old_conversation(db, user, vn(2026, 11, 10, 9), title="Chuyến Trà Vinh")
    newer = _old_conversation(db, user, vn(2026, 11, 18, 9))
    fake_claude.script.append(text_reply("Dạ, tiếp chuyện Trà Vinh."))
    body = {"client_message_id": str(uuid.uuid4()), "text": "nhắc lại giúp em", "conversation_id": old.id}
    resp = auth_client.post("/api/v1/chat/messages", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["user_message"]["conversation_id"] == old.id
    listed = auth_client.get("/api/v1/chat/conversations").json()["data"]["items"]
    assert [c["id"] for c in listed][:2] == [old.id, newer.id]  # phiên vừa chat lên đầu
    assert listed[0]["title"] == "Chuyến Trà Vinh"
    missing = {"client_message_id": str(uuid.uuid4()), "text": "x", "conversation_id": 999999}
    assert auth_client.post("/api/v1/chat/messages", json=missing).status_code == 404


def test_conversation_list_pin_rename_search_and_paging(auth_client, db, user):
    a = _old_conversation(db, user, vn(2026, 11, 1, 9), title="Hợp đồng nhà")
    b = _old_conversation(db, user, vn(2026, 11, 5, 9))
    c = _old_conversation(db, user, vn(2026, 11, 9, 9))  # chưa tên: máy đặt được
    assert auth_client.patch(f"/api/v1/chat/conversations/{a.id}", json={"pinned": True}).json()["data"][
        "pinned"
    ]
    page1 = auth_client.get("/api/v1/chat/conversations", params={"limit": 2}).json()["data"]
    assert [x["id"] for x in page1["items"]] == [a.id, c.id] and page1["next_cursor"]
    page2 = auth_client.get(
        "/api/v1/chat/conversations", params={"limit": 2, "cursor": page1["next_cursor"]}
    ).json()["data"]
    assert [x["id"] for x in page2["items"]] == [b.id] and page2["next_cursor"] is None
    # Tìm theo tiêu đề (không dấu) và theo nội dung tin.
    by_title = auth_client.get("/api/v1/chat/conversations", params={"q": "hop dong"}).json()["data"]["items"]
    assert [x["id"] for x in by_title] == [a.id]
    by_text = auth_client.get("/api/v1/chat/conversations", params={"q": "Trà Vinh"}).json()["data"]["items"]
    assert {x["id"] for x in by_text} == {a.id, b.id, c.id}
    renamed = auth_client.patch(f"/api/v1/chat/conversations/{b.id}", json={"title": "  Đi   Cần Thơ "})
    assert (
        renamed.json()["data"]["title"] == "Đi Cần Thơ" and renamed.json()["data"]["title_source"] == "user"
    )
    assert service.set_auto_title(db, user.user_id, b.id, "Tên máy đặt") is False  # không đè tên người đặt
    assert service.set_auto_title(db, user.user_id, c.id, "Mua xe máy mới") is True
    assert auth_client.patch(f"/api/v1/chat/conversations/{b.id}", json={"title": ""}).status_code == 400
    assert auth_client.patch("/api/v1/chat/conversations/999999", json={"pinned": True}).status_code == 404


def test_new_conversation_reuses_empty_one_and_today_returns_latest(auth_client, db, user):
    old = _old_conversation(db, user, vn(2026, 11, 1, 9))
    first = auth_client.post("/api/v1/chat/conversations", json={})
    assert first.status_code == 201
    again = auth_client.post("/api/v1/chat/conversations").json()["data"]
    assert again["id"] == first.json()["data"]["id"] != old.id  # phiên trống chưa tên: dùng lại
    named = auth_client.post("/api/v1/chat/conversations", json={"title": "Kế hoạch Tết"}).json()["data"]
    assert named["id"] == again["id"] and named["title"] == "Kế hoạch Tết"
    # Bản app cũ: /chat/today trả phiên hoạt động gần nhất, đúng dạng cũ.
    today = auth_client.get("/api/v1/chat/today").json()["data"]
    assert today["conversation"]["id"] == named["id"] and today["messages"] == []
    assert {"id", "local_date", "summary", "message_count"} <= set(today["conversation"])


def test_old_app_without_conversation_id_keeps_chatting_in_latest(auth_client, db, user, fake_claude):
    fake_claude.script += [text_reply("Một."), text_reply("Hai.")]
    first = send(auth_client, "câu một").json()["data"]
    second = send(auth_client, "câu hai").json()["data"]
    assert first["user_message"]["conversation_id"] == second["user_message"]["conversation_id"]
    today = auth_client.get("/api/v1/chat/today").json()["data"]
    assert [m["text"] for m in today["messages"] if m["role"] == "user"] == ["câu một", "câu hai"]


def test_idle_conversation_summarized_keeping_tail(db, user, monkeypatch):
    from app.ai import compaction
    from app.modules.chat import jobs

    conv = repo.create_conversation(db, user.user_id, clock.chat_day(vn(2026, 11, 1, 9), user.timezone),
                                    vn(2026, 11, 1, 9))  # fmt: skip
    for i in range(6):
        turn = uuid.uuid4()
        for role in ("user", "assistant"):
            db.add(Message(user_id=user.user_id, conversation_id=conv.id, turn_id=turn, role=role,
                           content=[{"type": "text", "text": f"{role} {i}"}], text=f"{role} {i}"))  # fmt: skip
    conv.last_message_at, conv.message_count = vn(2026, 11, 1, 10), 12
    fresh = _old_conversation(db, user, clock.now())  # còn thức: không tóm
    db.commit()
    seen = []
    monkeypatch.setattr(compaction, "summarize", lambda msgs, prev, ctx: seen.append(len(msgs)) or "Tóm tắt")

    assert jobs.summarize_idle_conversations() == 1
    db.expire_all()
    conv = repo.get_conversation(db, user.user_id, conv.id)
    assert conv.summary == "Tóm tắt" and conv.day_summary_done
    kept = repo.list_history(db, user.user_id, conv.id, conv.summary_upto_id)
    assert seen == [12 - len(kept)] and len(kept) >= compaction.KEEP_MESSAGES  # đuôi còn nguyên
    assert jobs.summarize_idle_conversations() == 0  # đã tóm cho lần ngủ này
    assert repo.get_conversation(db, user.user_id, fresh.id).summary is None


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


# ---------- QĐ-51: đặt tên tự động, mở phiên, tìm trong phiên cũ ----------


@pytest.fixture
def titles(monkeypatch):
    """Hàm đặt tên giả (agent AI giữ app.ai.session_title); việc nền chạy thẳng trong bài."""
    import sys
    import types

    import app.ai as ai_pkg

    calls = []

    def suggest_title(user_id, question, answer, *, client=None):
        calls.append((question, answer))
        return "Đi Trà Vinh cuối tuần."

    try:
        from app.ai import session_title as real

        monkeypatch.setattr(real, "suggest_title", suggest_title)
    except ImportError:
        fake = types.ModuleType("app.ai.session_title")
        fake.suggest_title = suggest_title
        monkeypatch.setitem(sys.modules, "app.ai.session_title", fake)
        monkeypatch.setattr(ai_pkg, "session_title", fake, raising=False)
    monkeypatch.setattr(service, "AUTO_TITLE_IN_TESTS", True)
    monkeypatch.setattr(service, "AUTO_TITLE_BACKGROUND", False)  # chạy thẳng trong bài
    return calls


def test_first_answer_names_untitled_conversation_once(auth_client, db, user, fake_claude, titles):
    fake_claude.script += [text_reply("Dạ đi Trà Vinh được, đường 2 tiếng."), text_reply("Dạ.")]
    first = send(auth_client, "cuối tuần đi Trà Vinh được không").json()["data"]
    cid = first["user_message"]["conversation_id"]
    conv = auth_client.get(f"/api/v1/chat/conversations/{cid}").json()["data"]["conversation"]
    assert conv["title"] == "Đi Trà Vinh cuối tuần." and conv["title_source"] == "auto"
    assert titles == [("cuối tuần đi Trà Vinh được không", "Dạ đi Trà Vinh được, đường 2 tiếng.")]
    send(auth_client, "cảm ơn")
    assert len(titles) == 1  # đã có tên: không gọi lại


def test_user_title_never_overwritten_by_auto_name(auth_client, db, user, fake_claude, titles):
    conv = auth_client.post("/api/v1/chat/conversations", json={"title": "Việc nhà"}).json()["data"]
    fake_claude.script.append(text_reply("Dạ."))
    body = {
        "client_message_id": str(uuid.uuid4()),
        "text": "nhắc em đóng tiền điện",
        "conversation_id": conv["id"],
    }
    assert auth_client.post("/api/v1/chat/messages", json=body).status_code == 200
    assert titles == []
    page = auth_client.get(f"/api/v1/chat/conversations/{conv['id']}").json()["data"]
    assert page["conversation"]["title"] == "Việc nhà" and page["conversation"]["last_preview"] == "Dạ."
    assert [m["text"] for m in page["messages"]] == ["nhắc em đóng tiền điện", "Dạ."]
    assert auth_client.get("/api/v1/chat/conversations/999999").status_code == 404


def test_search_history_finds_old_messages_newest_first(db, user):
    old = _old_conversation(db, user, vn(2026, 11, 2, 9), title="Chuyến miền Tây")
    newer = _old_conversation(db, user, vn(2026, 11, 8, 9))
    hits = service.search_history(db, user, "Trà Vinh")
    assert [h["conversation_id"] for h in hits] == [newer.id, old.id]
    assert hits[-1]["conversation_title"] == "Chuyến miền Tây" and "Trà Vinh" in hits[-1]["snippet"]
    assert {h["role"] for h in hits} == {"user"}
    answers = service.search_history(db, user, "đại ca")
    assert [(h["conversation_id"], h["role"]) for h in answers] == [
        (newer.id, "assistant"),
        (old.id, "assistant"),
    ]
    only_old = service.search_history(db, user, "Trà Vinh", exclude_conversation_id=newer.id)
    assert {h["conversation_id"] for h in only_old} == {old.id}
    assert service.search_history(db, user, "  ") == []


# ---------- Phản hồi 1.1.1: không còn phiên rỗng ----------


def test_today_without_sessions_creates_nothing(auth_client, db, user):
    from app.modules.chat.models import Conversation

    today = auth_client.get("/api/v1/chat/today").json()["data"]
    assert today["conversation"] is None and today["messages"] == []
    assert db.query(Conversation).filter_by(user_id=user.user_id).count() == 0


def test_list_hides_empty_sessions_except_just_created(auth_client, db, user):
    from app.modules.chat.models import Conversation

    old_empty = repo.create_conversation(db, user.user_id, clock.chat_day(vn(2026, 11, 21, 9), user.timezone),
                                         vn(2026, 11, 21, 9))  # fmt: skip
    old_empty.created_at = vn(2026, 11, 21, 9)  # phiên luật cũ tự tạo, 0 tin
    with_msgs = _old_conversation(db, user, vn(2026, 11, 20, 9))
    db.flush()
    fresh = auth_client.post("/api/v1/chat/conversations").json()["data"]  # nút Phiên mới
    ids = [c["id"] for c in auth_client.get("/api/v1/chat/conversations").json()["data"]["items"]]
    assert ids == [fresh["id"], with_msgs.id]  # phiên rỗng cũ không hiện
    # Quá 10 phút mà vẫn trống thì cũng ẩn.
    db.get(Conversation, fresh["id"]).created_at = clock.now() - timedelta(minutes=11)
    db.flush()
    ids = [c["id"] for c in auth_client.get("/api/v1/chat/conversations").json()["data"]["items"]]
    assert ids == [with_msgs.id]


def test_cleanup_deletes_empty_sessions_older_than_a_day(db, user):
    from sqlalchemy import text as sql

    from app.modules.chat.models import Conversation
    from worker.jobs import cleanup

    old_empty = repo.create_conversation(db, user.user_id, clock.chat_day(vn(2026, 11, 21, 9), user.timezone),
                                         vn(2026, 11, 21, 9))  # fmt: skip
    new_empty = repo.create_conversation(
        db, user.user_id, clock.chat_day(clock.now(), user.timezone), clock.now()
    )
    kept = _old_conversation(db, user, vn(2026, 11, 20, 9))
    # Đoạn chat người dùng đặt tên sẵn theo nhu cầu (QĐ-58): trống vẫn giữ, vẫn hiện trong danh sách.
    named = repo.create_conversation(db, user.user_id, clock.chat_day(vn(2026, 11, 21, 9), user.timezone),
                                     vn(2026, 11, 21, 9), "Công việc DEGO")  # fmt: skip
    named.title_source = "user"
    db.execute(
        sql("UPDATE tab_conversation SET created_at = now() - interval '2 days' WHERE id IN (:a, :b, :c)"),
        {"a": old_empty.id, "b": kept.id, "c": named.id},
    )
    db.commit()
    cleanup.cleanup_old_data()
    db.expire_all()
    left = {c.id for c in db.query(Conversation).filter_by(user_id=user.user_id)}
    assert left == {new_empty.id, kept.id, named.id}
    listed = {c["id"] for c in service.list_conversations(db, user, None, 50)["items"]}
    assert named.id in listed and len(listed) == 3
