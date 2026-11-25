"""Công cụ send_zalo_message (QĐ-52, agent AI): chỉ tạo thẻ duyệt; duyệt xong mới gửi (cầu Zalo giả)."""

from datetime import UTC, datetime

import pytest

from app.ai.schemas import ToolContext
from app.core.context import UserContext
from app.modules.chat import service as chat_service
from app.modules.zalo import tools
from app.modules.zalo.tests.test_zalo import fake, msg, post_events  # noqa: F401 - fixture dùng chung


def _call(db, user, **data):
    spec = tools.TOOLS[0]
    ctx = ToolContext(
        session=db,
        user=UserContext(user_id=user.user_id, timezone=user.timezone),
        conversation_id=None,
        now=datetime(2026, 11, 25, 3, tzinfo=UTC),
    )
    return spec.run(ctx, spec.input_model.model_validate(data))


def test_tool_creates_card_and_sends_only_after_approval(client, db, user, fake):  # noqa: F811
    post_events(client, [msg("1")])
    out = _call(db, user, conversation_key="zalo:u:u-lan", text="Dạ mai em tới")
    assert out.result["trang_thai"] == "cho_duyet" and fake.sent() == []
    card = out.actions[0]
    assert card["type"] == "confirm" and card["pending_action_id"] == out.result["pending_action_id"]
    assert {"label": "Gửi tới", "value": "Lan"} in card["details"]
    u = UserContext(user_id=user.user_id, timezone=user.timezone)
    chat_service.decide_action(db, u, card["pending_action_id"], approve=True)
    assert fake.sent()[-1]["text"] == "Dạ mai em tới"


def test_tool_rejects_partial_conversation_key(db, user, fake):  # noqa: F811
    with pytest.raises(Exception) as exc:
        _call(db, user, conversation_key="Lan", text="chào")
    assert getattr(exc.value, "code", "") == "VALIDATION_ERROR" and fake.sent() == []
