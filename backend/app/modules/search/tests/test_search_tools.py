"""Công cụ AI search_everything (bài kiểm của agent AI, việc 1-06)."""

import uuid
from datetime import UTC, datetime

import pytest

from app.ai.schemas import ToolContext
from app.core import clock
from app.modules.chat import repo as chat_repo
from app.modules.chat.models import Message
from app.modules.memory import service as memory
from app.modules.search import tools

NOW = datetime(2026, 11, 18, 5, tzinfo=UTC)


def _run(ctx, **kw):
    spec = tools.TOOLS[0]
    data = {"query": "visa", "types": None, "from_date": None, "to_date": None, "limit": None, **kw}
    return spec.run(ctx, spec.input_model.model_validate(data))


@pytest.fixture
def conv(db, user):
    return chat_repo.get_or_create_conversation(db, user.user_id, clock.now().date(), clock.now())


def test_finds_note_unaccented_with_open_button(db, user, conv):
    memory.create_note(db, user.user_id, "Hồ sơ visa", "Nộp hồ sơ visa Úc trước thứ Sáu", ["visa"])
    ctx = ToolContext(session=db, user=user, conversation_id=conv.id, now=NOW)
    out = _run(ctx, query="ho so visa")
    assert out.result["items"][0]["source"] == "note"
    assert "<b>" not in out.result["items"][0]["snippet"]
    button = out.actions[0]
    assert button["type"] == "open_screen" and "id" not in button and button["label"].startswith("Mở")
    assert out.contains_third_party is False


def test_skips_current_conversation_messages(db, user, conv):
    db.add(
        Message(
            user_id=user.user_id,
            conversation_id=conv.id,
            turn_id=uuid.uuid4(),
            role="user",
            content=[{"type": "text", "text": "tìm lại ghi chú về visa"}],
            text="tìm lại ghi chú về visa",
        )
    )
    db.flush()
    ctx = ToolContext(session=db, user=user, conversation_id=conv.id, now=NOW)
    out = _run(ctx)
    assert out.result["items"] == [] and "ghi_chu" in out.result
    other = ToolContext(session=db, user=user, conversation_id=None, now=NOW)
    assert _run(other).result["items"][0]["source"] == "chat"


def test_unknown_type_rejected_by_model():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        tools.TOOLS[0].input_model.model_validate(
            {"query": "x", "types": ["email"], "from_date": None, "to_date": None, "limit": None}
        )
