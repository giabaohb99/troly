"""QĐ-51 bước 1, phần AI: đặt tên phiên tự động và tìm trong phiên cũ (agent AI)."""

import uuid
from datetime import UTC, datetime

import pytest

from app.ai import client as ai_client
from app.ai.schemas import ToolContext
from app.ai.tests.fake_claude import FakeClaude, text_reply
from app.modules.chat import service, tools
from app.modules.chat.models import Conversation, Message


@pytest.fixture
def fake_claude(monkeypatch):
    from app.ai.models import DbRunRecorder

    fake = FakeClaude()
    monkeypatch.setattr(ai_client, "_client", ai_client.ClaudeClient(sdk=fake, recorder=DbRunRecorder()))
    return fake


@pytest.fixture
def auto_title(monkeypatch):
    monkeypatch.setattr(service, "AUTO_TITLE_IN_TESTS", True)
    monkeypatch.setattr(service, "AUTO_TITLE_BACKGROUND", False)


def send(client, text, conversation_id=None):
    body = {"client_message_id": str(uuid.uuid4()), "text": text}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return client.post("/api/v1/chat/messages", json=body)


def test_first_answer_names_session_once(auth_client, db, fake_claude, auto_title):
    fake_claude.script += [
        text_reply("Tháng 11 đại ca đã chi 3.465.000đ."),
        {"content": [{"type": "text", "text": "Chi tiêu tháng 11."}]},  # lời gọi đặt tên
        text_reply("Ăn uống nhiều nhất."),
    ]
    first = send(auth_client, "tháng này anh tiêu bao nhiêu")
    assert first.status_code == 200, first.text
    cid = (
        first.json()["data"]["user_message"]["conversation_id"]
        if "conversation_id" in first.json()["data"]["user_message"]
        else None
    )
    conv = db.query(Conversation).order_by(Conversation.id.desc()).first()
    db.refresh(conv)
    assert conv.title == "Chi tiêu tháng 11" and conv.title_source == "auto"
    title_call = fake_claude.requests[1]
    assert (
        title_call["model"] == "claude-haiku-5-5"
        and title_call["max_tokens"] == 64
        and "tools" not in title_call
    )
    send(auth_client, "khoản nào nhiều nhất", cid or conv.id)
    assert len(fake_claude.requests) == 3  # đã có tên: không gọi đặt tên lần nữa


def test_user_title_never_overwritten(auth_client, db, fake_claude, auto_title):
    created = auth_client.post("/api/v1/chat/conversations", json={"title": "Họp tuần"})
    assert created.status_code in (200, 201), created.text
    cid = created.json()["data"]["id"]
    fake_claude.script.append(text_reply("Dạ em ghi nhận."))
    assert send(auth_client, "ghi chú lịch họp tuần sau", cid).status_code == 200
    conv = db.get(Conversation, cid)
    db.refresh(conv)
    assert conv.title == "Họp tuần" and conv.title_source == "user" and len(fake_claude.requests) == 1


def _conversation(db, user, title, texts, at):
    conv = Conversation(
        user_id=user.user_id,
        local_date=at.date(),
        started_at=at,
        last_message_at=at,
        title=title,
        title_source="user",
    )
    db.add(conv)
    db.flush()
    turn = uuid.uuid4()
    for role, text in texts:
        db.add(
            Message(
                user_id=user.user_id,
                conversation_id=conv.id,
                turn_id=turn,
                role=role,
                text=text,
                content=[{"type": "text", "text": text}],
            )
        )
    db.flush()
    return conv


def test_search_chat_history_returns_snippets_and_open_button(db, user):
    at = datetime(2026, 11, 20, 5, tzinfo=UTC)
    old = _conversation(
        db,
        user,
        "Quán ăn Trà Vinh",
        [
            ("user", "ở Trà Vinh ăn gì ngon em"),
            ("assistant", "Đại ca thử bún nước lèo bà Tư gần chợ Trà Vinh, mở từ 6h sáng."),
        ],
        at,
    )
    _conversation(db, user, "Chi tiêu", [("user", "cơm trưa 45k"), ("assistant", "Đã ghi 45.000đ.")], at)
    ctx = ToolContext(session=db, user=user, conversation_id=None, now=at)
    spec = tools.TOOLS[0]
    out = spec.run(ctx, spec.input_model.model_validate({"query": "bún nước lèo"}))
    assert [i["conversation_id"] for i in out.result["items"]] == [old.id]
    snip = out.result["items"][0]["doan_trich"][0]
    assert snip["role"] == "trợ lý" and "bún nước lèo bà Tư" in snip["text"]
    assert out.actions[0]["screen"] == "chat" and out.actions[0]["params"] == {"conversation_id": old.id}
    none = spec.run(ctx, spec.input_model.model_validate({"query": "vé máy bay Đà Lạt"}))
    assert none.result["items"] == [] and "không đoán" in none.result["ghi_chu"]
