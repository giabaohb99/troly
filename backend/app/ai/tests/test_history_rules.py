"""Lịch sử gửi lên phải đúng luật Messages API (lỗi 400 thật ngày 18/11/2026) và công cụ không vượt giới hạn."""

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ConfigDict

from app.ai.loop import run_turn
from app.ai.prompt import build_turn_system_message, normalize_history
from app.ai.registry import check_strict_limits, get_tool_definitions, register_tools, tool_definition
from app.ai.router import choose_turn
from app.ai.schemas import SystemParts, ToolOutput, ToolSpec
from app.ai.tests.fake_claude import FakeClaude, text_reply, validate_request

T1 = {"role": "system", "content": "Thời điểm hiện tại: thứ Tư, 18/11/2026, 11:00 giờ Việt Nam (UTC+7)."}
T2 = {"role": "system", "content": "Thời điểm hiện tại: thứ Tư, 18/11/2026, 11:30 giờ Việt Nam (UTC+7)."}
NOTE = {"role": "system", "content": "Người dùng đã duyệt: Xóa 2 khoản chi. Kết quả: thành công."}


def u(text):
    return {"role": "user", "content": [{"type": "text", "text": text}]}


def a(text):
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def test_failed_turn_leaves_no_dangling_system():
    """Lượt trước hỏng (có tin thời gian, không có trả lời): đúng lỗi messages.2 đã gặp."""
    raw = [u("chào"), T1, u("cơm trưa 45k"), T2]
    assert validate_request({"messages": raw})  # FakeClaude bắt được lỗi như API thật
    fixed = normalize_history(raw)
    assert validate_request({"messages": fixed}) is None
    assert [m["role"] for m in fixed] == ["user", "system"]
    assert [b["text"] for b in fixed[0]["content"]] == ["chào", "cơm trưa 45k"]
    assert fixed[1]["content"] == T2["content"]  # chỉ còn mốc giờ của lượt mới


def test_approval_note_after_assistant_moves_to_next_turn():
    raw = [u("xóa hai khoản"), T1, a("Đã soạn thẻ, bấm Duyệt."), NOTE, u("còn gì không"), T2]
    assert validate_request({"messages": raw})
    fixed = normalize_history(raw)
    assert validate_request({"messages": fixed}) is None
    assert fixed[-1]["role"] == "system"
    assert fixed[-1]["content"].startswith("Người dùng đã duyệt") and T2["content"] in fixed[-1]["content"]


def test_normalize_is_stable_and_keeps_good_history():
    good = [u("chào"), T1, a("Chào đại ca."), u("cơm trưa 45k"), T2]
    assert normalize_history(good) == normalize_history(good)
    assert normalize_history(good) == good


def test_run_turn_after_failed_turn_sends_valid_request(make_client, settings, store):
    from app.ai.schemas import ToolContext
    from app.ai.tests.conftest import FakeSession, FakeUser

    now = datetime(2026, 11, 18, 4, 30, tzinfo=UTC)
    ctx = ToolContext(session=FakeSession(), user=FakeUser(), conversation_id=1, now=now)
    plan = choose_turn("cơm trưa 45k", None, settings=settings)
    history = [u("chào"), T1, u("cơm trưa 45k"), build_turn_system_message(now, "Asia/Ho_Chi_Minh", plan)]
    fake = FakeClaude([text_reply("Đã ghi.")])
    events = list(
        run_turn(ctx, plan, SystemParts("x"), history, store, client=make_client(fake), settings=settings)
    )
    assert events[-1].type == "turn.completed"


class Wide(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: int | None
    b: str | None
    c: str | None
    d: str | None
    e: str | None


def _wide(name, strict):
    return ToolSpec(
        name=name,
        label=name,
        description="x",
        input_model=Wide,
        run=lambda c, d: ToolOutput({}),
        strict=strict,
    )


def test_tools_are_not_strict_by_default():
    register_tools([_wide("w1", False)])
    assert "strict" not in get_tool_definitions()[0]


def test_strict_limits_are_enforced():
    defs = [tool_definition(_wide(f"w{i}", True)) for i in range(4)]  # 4 x 5 = 20 tham số union
    with pytest.raises(ValueError, match="union"):
        check_strict_limits(defs)
    assert validate_request({"messages": [u("x")], "tools": defs})
