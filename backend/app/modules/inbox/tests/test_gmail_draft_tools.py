"""Công cụ soạn, gửi Gmail qua chat (QĐ-43, agent AI): nháp không duyệt, gửi luôn qua thẻ duyệt."""

import uuid

import pytest

from app.integrations.google import stores
from app.integrations.google.tests.conftest import GMAIL_SCOPES, connect_account, fake  # noqa: F401
from app.modules.inbox import tools
from app.modules.inbox.models import GmailDraft
from app.registry import register_integrations


@pytest.fixture
def gmail_user(db, user, fake):  # noqa: F811
    acc, result = connect_account(db, user, fake, packs=("gmail",), scope=GMAIL_SCOPES)
    assert result.ket_qua == "ok"
    register_integrations()
    yield acc
    stores.register_mail_store(None)
    stores.register_calendar_store(None)
    stores.register_task_store(None)


@pytest.fixture
def scripted(monkeypatch):
    from app.ai import client as ai_client
    from app.ai.models import DbRunRecorder
    from app.ai.registry import get_tool, register_tools
    from app.ai.tests.fake_claude import FakeClaude

    if get_tool("send_gmail_draft") is None:
        register_tools(tools.TOOLS)

    def make(script):
        claude = FakeClaude(script)
        monkeypatch.setattr(
            ai_client, "_client", ai_client.ClaudeClient(sdk=claude, recorder=DbRunRecorder())
        )
        return claude

    return make


def _say(client, text):
    return client.post("/api/v1/chat/messages", json={"client_message_id": str(uuid.uuid4()), "text": text})


def test_chat_drafts_then_sends_only_after_approval(auth_client, db, fake, gmail_user, scripted):  # noqa: F811
    from app.ai.tests.fake_claude import text_reply, tool_call

    scripted(
        [
            tool_call(
                "create_gmail_draft",
                {
                    "to": ["hanh@example.com"],
                    "cc": None,
                    "subject": "Xin nghỉ ngày mai",
                    "body": "Chị Hạnh ơi, mai em xin nghỉ một hôm. Em cảm ơn chị.",
                    "reply_to_thread_id": None,
                },
            ),
            text_reply("Em đã soạn nháp gửi chị Hạnh. Đại ca có muốn gửi luôn không?"),
        ]
    )
    resp = _say(auth_client, "soạn mail cho chị Hạnh hanh@example.com xin nghỉ mai")
    assert resp.status_code == 200, resp.text
    draft = db.query(GmailDraft).one()
    assert draft.status == "draft" and draft.google_draft_id in fake.gmail.drafts and fake.gmail.sent == []
    assert any(a["type"] == "open_link" for a in resp.json()["data"]["assistant_message"]["actions"])

    scripted(
        [
            tool_call("send_gmail_draft", {"draft_id": draft.id}),
            text_reply("Em đã tạo thẻ gửi thư, đại ca bấm Duyệt nhé."),
        ]
    )
    resp = _say(auth_client, "ok gửi đi")
    card = next(a for a in resp.json()["data"]["assistant_message"]["actions"] if a["type"] == "confirm")
    values = {d["label"]: d["value"] for d in card["details"]}
    assert values["Người nhận"] == "hanh@example.com" and values["Tiêu đề"] == "Xin nghỉ ngày mai"
    assert "mai em xin nghỉ" in values["Đoạn đầu"] and fake.gmail.sent == []  # chưa duyệt thì chưa gửi

    ok = auth_client.post(f"/api/v1/chat/actions/{card['pending_action_id']}/approve")
    assert ok.status_code == 200 and ok.json()["data"]["action"]["status"] == "done"
    db.refresh(draft)
    assert draft.status == "sent" and len(fake.gmail.sent) == 1


def test_send_card_refused_for_already_sent_draft(db, user, fake, gmail_user):  # noqa: F811
    from datetime import UTC, datetime

    from app.ai.schemas import AiError, ToolContext
    from app.modules.inbox import mail

    d = mail.create_draft(db, user.user_id, {"to": ["ban@example.com"], "subject": "Hẹn", "body": "Mai gặp"})
    row = db.get(GmailDraft, d["id"])
    row.status = "sent"
    spec = next(t for t in tools.TOOLS if t.name == "send_gmail_draft")
    ctx = ToolContext(session=db, user=user, conversation_id=None, now=datetime(2026, 11, 19, tzinfo=UTC))
    with pytest.raises(AiError, match="đã gửi"):
        spec.prepare(ctx, spec.input_model.model_validate({"draft_id": d["id"]}))
