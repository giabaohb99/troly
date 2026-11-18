"""Công cụ AI cài đặt (bài kiểm của agent AI, việc 4-02)."""

from datetime import UTC, datetime

import pytest

from app.ai.schemas import AiError, ToolContext
from app.modules.setting import tools


@pytest.fixture
def ctx(db, user):
    return ToolContext(session=db, user=user, conversation_id=None, now=datetime(2026, 11, 18, 5, tzinfo=UTC))


def _call(ctx, name, **data):
    spec = next(t for t in tools.TOOLS if t.name == name)
    return spec.run(ctx, spec.input_model.model_validate(data))


def test_add_and_remove_vip_sender(ctx):
    _call(ctx, "update_setting", key="vip_sender", op="add", value="Mẹ", app=None)
    _call(ctx, "update_setting", key="urgent_keyword", op="add", value="gấp", app="zalo")
    got = _call(ctx, "get_settings").result
    assert got["inbox_rules"]["vip_sender"] == ["Mẹ"] and got["inbox_rules"]["urgent_keyword"] == [
        "gấp (zalo)"
    ]
    assert "inbox.ai_enabled" in got["settings"]
    _call(ctx, "update_setting", key="vip_sender", op="remove", value="me", app=None)
    assert _call(ctx, "get_settings").result["inbox_rules"]["vip_sender"] == []
    with pytest.raises(AiError):
        _call(ctx, "update_setting", key="vip_sender", op="remove", value="Lan", app=None)


def test_listened_apps_cannot_be_changed_by_ai():
    from pydantic import ValidationError

    spec = next(t for t in tools.TOOLS if t.name == "update_setting")
    with pytest.raises(ValidationError):
        spec.input_model.model_validate({"key": "listened_app", "op": "add", "value": "x", "app": None})
