"""Phần đầu lời nhắc phải giữ nguyên byte giữa các lượt để cache ăn (20 mục 3.3)."""

import json
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ai.prompt import build_system, build_tools, build_turn_system_text, strip_thinking
from app.ai.registry import get_tool_definitions, register_tools
from app.ai.router import plan_turn
from app.ai.schemas import PrevMessage, SystemParts, ToolOutput, ToolSpec, TurnInput


class In(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(description="Tên")
    note: str | None = Field(default=None, max_length=50)


def _spec(name):
    return ToolSpec(
        name=name, label=name, description="mô tả", input_model=In, run=lambda c, d: ToolOutput({})
    )


def test_tools_sorted_and_stable(settings):
    register_tools([_spec("zeta"), _spec("alpha")])
    plan = plan_turn(TurnInput("chào"), settings)
    a = json.dumps(build_tools(get_tool_definitions(), plan), sort_keys=True, ensure_ascii=False)
    b = json.dumps(build_tools(get_tool_definitions(), plan), sort_keys=True, ensure_ascii=False)
    assert a == b
    tools = json.loads(a)
    assert [t["name"] for t in tools] == ["alpha", "zeta"]
    assert tools[-1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert "cache_control" not in tools[0]


def test_strict_schema_keeps_property_named_title():
    register_tools([_spec("alpha")])
    schema = get_tool_definitions()[0]["input_schema"]
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["note", "title"]
    assert "title" in schema["properties"]
    assert "maxLength" not in json.dumps(schema)
    assert "default" not in json.dumps(schema)


def test_system_has_no_time_and_is_stable():
    parts = SystemParts(profile_md="## Xưng hô\r\nGọi đại ca.  ", summary="Đã làm: ghi 45k")
    a = build_system(parts, "1h")
    b = build_system(parts, "1h")
    assert a == b
    text = json.dumps(a, ensure_ascii=False)
    assert "Thời điểm hiện tại:" not in text
    assert a[1]["text"] == "<ho_so_loi>\n## Xưng hô\nGọi đại ca.\n</ho_so_loi>"
    assert a[1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert a[2]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_sonnet_uses_5m_ttl(settings):
    plan = plan_turn(TurnInput("nghĩ kỹ giúp em"), settings)
    assert plan.prefix_ttl == "5m"
    assert build_system(SystemParts("x"), plan.prefix_ttl)[1]["cache_control"] == {"type": "ephemeral"}


def test_prev_tail_rendered_with_local_time():
    parts = SystemParts(
        profile_md="x",
        prev_tail=[PrevMessage("user", "đi ngủ đây", datetime(2026, 11, 17, 20, 50, tzinfo=UTC))],
    )
    block = build_system(parts, "1h")[2]["text"]
    assert "<tin_cuoi_phien_truoc>" in block and "[03:50] Người dùng: đi ngủ đây" in block


def test_turn_system_text_has_mode_rules(settings):
    now = datetime(2026, 11, 18, 4, 30, tzinfo=UTC)
    research = build_turn_system_text(
        now, "Asia/Ho_Chi_Minh", plan_turn(TurnInput("x", "research"), settings)
    )
    assert research.startswith("Thời điểm hiện tại: thứ Tư, 18/11/2026, 11:30 giờ Việt Nam (UTC+7).")
    assert "tìm web" in research
    chat = build_turn_system_text(now, "Asia/Ho_Chi_Minh", plan_turn(TurnInput("x"), settings))
    assert "\n" not in chat


def test_strip_thinking_removes_all_thinking():
    msgs = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": [{"type": "thinking", "thinking": "", "signature": "s"}]},
        {
            "role": "assistant",
            "content": [{"type": "redacted_thinking", "data": "x"}, {"type": "text", "text": "b"}],
        },
    ]
    out = strip_thinking(msgs)
    assert out[1]["content"] == [{"type": "text", "text": "."}]
    assert out[2]["content"] == [{"type": "text", "text": "b"}]
