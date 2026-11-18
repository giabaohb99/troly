"""Công cụ AI của memory (bài kiểm của agent AI, việc 1-06)."""

from datetime import UTC, datetime

import pytest

from app.ai.schemas import AiError, ToolContext
from app.modules.memory import service, tools


@pytest.fixture
def ctx(db, user):
    return ToolContext(session=db, user=user, conversation_id=None, now=datetime(2026, 11, 18, 5, tzinfo=UTC))


def _call(ctx, name, **data):
    spec = next(t for t in tools.TOOLS if t.name == name)
    return spec.run(ctx, spec.input_model.model_validate(data))


def test_add_fact_creates_section_in_order():
    md = "## Mục tiêu\n- Định cư Úc\n"
    out = tools.add_fact(md, "Xưng hô", "Gọi đại ca, xưng em")
    assert out.index("## Xưng hô") < out.index("## Mục tiêu")
    assert tools.add_fact(out, "Ghi nhớ khác", "gọi ĐẠI CA, xưng em") is None


def test_remember_then_dedupe_and_undo_version(ctx, db, user):
    out = _call(ctx, "remember", section="Ăn uống, sức khỏe", fact="Dị ứng tôm", reason="người dùng nói")
    action = out.actions[0]
    assert action["type"] == "memory_changed" and action["undo_version"] == action["version"] - 1
    md = service.get_profile_markdown(db, user.user_id)
    assert "## Ăn uống, sức khỏe\n- Dị ứng tôm" in md
    again = _call(ctx, "remember", section="Ăn uống, sức khỏe", fact="dị ứng tôm", reason="lặp")
    assert again.result["trang_thai"] == "da_co" and again.actions == []


def test_forget_one_and_many(ctx, db, user):
    _call(ctx, "remember", section="Thông tin cơ bản", fact="Đang ở Cần Thơ", reason="x")
    _call(ctx, "remember", section="Công việc", fact="Làm ở Cần Thơ 3 năm", reason="x")
    many = _call(ctx, "forget", match="can tho", reason="chuyển nhà")
    assert many.result["trang_thai"] == "nhieu_dong" and many.actions[0]["type"] == "choices"
    one = _call(ctx, "forget", match="đang ở cần thơ", reason="chuyển nhà")
    assert one.result["removed"] == "Đang ở Cần Thơ"
    assert "Đang ở Cần Thơ" not in service.get_profile_markdown(db, user.user_id)
    with pytest.raises(AiError):
        _call(ctx, "forget", match="Hà Nội", reason="x")


def test_save_note(ctx):
    out = _call(ctx, "save_note", title="Hồ sơ visa", body="Nộp trước thứ Sáu", tags=["Visa"])
    assert out.result["note_id"] > 0
