from decimal import Decimal

import pytest

from app.ai.compaction import choose_cut, should_compact
from app.ai.pricing import UsageCount, compute_cost_usd, usage_from_response
from app.ai.router import normalize, plan_turn, supports_fallbacks
from app.ai.schemas import TurnInput


@pytest.mark.parametrize(
    ("text", "mode", "model", "web"),
    [
        ("cơm trưa 45k", None, "claude-haiku-5-5", True),
        ("Nghĩ KỸ giúp em tháng này nên cắt khoản nào", None, "claude-sonnet-5-5", False),
        ("tìm trên mạng giá vé phà", None, "claude-sonnet-5-5", True),
        ("giá vé phà", "research", "claude-sonnet-5-5", True),
        ("tóm tắt giúp", "summary", "claude-sonnet-5-5", False),
        ("dùng Opus phân tích chi tiêu", None, "claude-opus-5-5", False),
        ("dùng opus tìm web giá vàng", None, "claude-opus-5-5", True),
        ("researcher là gì", None, "claude-haiku-5-5", True),
    ],
)
def test_plan_turn(text, mode, model, web, settings):
    plan = plan_turn(TurnInput(text, mode), settings)
    assert plan.model == model
    assert plan.web_tools is web


def test_effort_by_mode(settings):
    assert plan_turn(TurnInput("chào"), settings).effort == "low"
    assert plan_turn(TurnInput("x", "think"), settings).effort == "medium"
    assert plan_turn(TurnInput("x", "summary"), settings).effort == "low"


def test_normalize():
    assert normalize("  Đường  Nghĩ Kỹ ") == "duong nghi ky"


def test_fallbacks_only_sonnet_opus():
    assert supports_fallbacks("claude-sonnet-5-5") and supports_fallbacks("claude-opus-5-5")
    assert not supports_fallbacks("claude-haiku-5-5")


def test_cost_haiku_with_cache():
    usage = UsageCount(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_tokens=1_000_000,
        cache_write_5m_tokens=1_000_000,
        cache_write_1h_tokens=1_000_000,
    )
    cost, card = compute_cost_usd("claude-haiku-5-5", usage)
    # 5 triệu token lời nhắc: vượt 100K nên theo bảng giá cao (0,50 / 2,50).
    assert card == "gt_100k"
    assert cost == Decimal("0.50") + Decimal("2.50") + Decimal("0.05") + Decimal("0.625") + Decimal("1.00")


def test_cost_sonnet_with_web_search():
    cost, card = compute_cost_usd(
        "claude-sonnet-5-5", UsageCount(input_tokens=10_000, output_tokens=1_000, web_search_requests=3)
    )
    assert card == "le_100k"
    assert cost == Decimal("0.020000") + Decimal("0.010000") + Decimal("0.03")


def test_usage_from_dict_handles_missing_fields():
    u = usage_from_response({"input_tokens": 5, "cache_creation_input_tokens": 7})
    assert u.input_tokens == 5 and u.cache_write_5m_tokens == 7 and u.web_search_requests == 0


def test_should_compact(settings):
    assert (
        should_compact(30_001, settings)
        and not should_compact(29_000, settings)
        and not should_compact(None, settings)
    )


def test_choose_cut_stops_at_user_turn():
    h = [
        {"role": "user", "content": "1"},
        {"role": "system", "content": "giờ"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t", "name": "x", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "{}"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "a"}]},
        {"role": "user", "content": "2"},
        {"role": "assistant", "content": [{"type": "text", "text": "b"}]},
        {"role": "user", "content": "3"},
        {"role": "assistant", "content": [{"type": "text", "text": "c"}]},
    ]
    cut = choose_cut(h, keep=6)
    assert h[cut]["role"] == "user" and h[cut]["content"] == "1"
    assert choose_cut(h[:3], keep=6) == 0


@pytest.mark.parametrize(
    "text, trip_plan",
    [
        ("tạo lịch trình đi Vũng Tàu 2 ngày, xuất phát Cần Thơ", True),
        ("Lên kế hoạch đi Đà Lạt cuối tuần", True),
        ("gợi ý giúp em lịch trình Côn Đảo 3 ngày", True),
        ("lịch trình Phước Hải ngày 2 đi đâu", False),
        ("xem lịch trình chuyến Trà Vinh", False),
        ("tạo lịch họp với anh Tuấn", False),
    ],
)
def test_trip_plan_goes_to_sonnet_with_web(text, trip_plan, settings):
    from app.ai.prompt import TRIP_PLAN_RULES, build_turn_system_text

    plan = plan_turn(TurnInput(text), settings)
    assert (plan.task == "trip_plan") is trip_plan
    if trip_plan:
        assert plan.model == settings.ai_model_smart and plan.web_tools and plan.mode == "think"
        from datetime import UTC, datetime

        assert TRIP_PLAN_RULES in build_turn_system_text(
            datetime(2026, 11, 18, tzinfo=UTC), "Asia/Ho_Chi_Minh", plan
        )
    else:
        assert plan.model == settings.ai_model_chat and plan.task is None


def test_haiku_turn_gets_basic_web_search_capped():
    from app.ai.prompt import build_tools
    from app.ai.settings import AiSettings

    plan = plan_turn(TurnInput("cây xăng gần Đất Đỏ"), AiSettings())
    web = [t for t in build_tools([{"name": "add_expense"}], plan) if t.get("type", "").startswith("web_")]
    assert web == [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 2,
            "user_location": {"type": "approximate", "timezone": "Asia/Ho_Chi_Minh"},
        }
    ]


@pytest.mark.parametrize(
    "text, previous, task",
    [
        ("Oke", "trip_plan", "trip_plan"),
        ("ừ làm đi", "trip_plan", "trip_plan"),
        ("thứ 7 22/11, xuất phát Cần Thơ 6h sáng", "trip_plan", "trip_plan"),
        ("Oke", None, None),
    ],
)
def test_short_follow_up_keeps_trip_plan(text, previous, task, settings):
    from app.ai.prompt import TRIP_PLAN_RULES, build_turn_system_text, turn_task_of

    plan = plan_turn(TurnInput(text), settings, previous)
    assert plan.task == task
    if task:
        from datetime import UTC, datetime

        saved = build_turn_system_text(datetime(2026, 11, 19, tzinfo=UTC), "Asia/Ho_Chi_Minh", plan)
        assert turn_task_of(saved) == "trip_plan" and TRIP_PLAN_RULES in saved
