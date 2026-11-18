"""Ước tính chặng xe máy theo QĐ-36 (Sonnet, mã kẹp số; nghĩ kỹ thì tìm web giờ mở cửa, giờ phà)."""

from datetime import time

import pytest

from app.ai.registry import count_complexity, to_strict_schema
from app.ai.tests.fake_claude import FakeClaude
from app.ai.trip_legs import (
    CheckGuess,
    LegGuess,
    LegPlan,
    check_leg,
    estimate_legs,
    straight_km,
)

STOPS = [
    {
        "stop_id": 1,
        "day_no": 1,
        "title": "Nhà ở Cần Thơ",
        "category": "khac",
        "address": "Ninh Kiều, Cần Thơ",
    },
    {"stop_id": 2, "day_no": 1, "title": "Phà Cát Lái", "category": "pha", "visit_date": "2026-11-21"},
    {
        "stop_id": 3,
        "day_no": 1,
        "title": "Khách sạn Phước Hải",
        "category": "khach_san",
        "lat": 10.4477939,
        "lng": 107.2709,
    },
    {
        "stop_id": 4,
        "day_no": 1,
        "title": "Chợ Phước Hải",
        "category": "an_uong",
        "lat": 10.4470,
        "lng": 107.2650,
        "visit_date": "2026-11-21",
    },
]
LEGS = [
    {"from_stop_id": 1, "to_stop_id": 2},
    {"from_stop_id": 2, "to_stop_id": 3},
    {"from_stop_id": 3, "to_stop_id": 4},
]


def _leg(index, km, minutes, ferry=0, confidence="medium", note="đi QL1"):
    return LegGuess(
        index=index,
        km=km,
        minutes=minutes,
        ferry_minutes=ferry,
        confidence=confidence,
        roads=["QL1A"],
        note=note,
    )


def _check(stop_index, kind, **kw):
    base = {
        "found": True,
        "open_weekdays": [],
        "open_time": "",
        "close_time": "",
        "break_start": "",
        "break_end": "",
        "last_time": "",
        "source_url": "",
        "text": "",
    }
    return CheckGuess(stop_index=stop_index, kind=kind, **{**base, **kw})


def _reply(plan: LegPlan):
    return {"content": [{"type": "text", "text": plan.model_dump_json()}], "parsed_output": plan}


def test_schema_has_no_unions_or_optionals():
    assert count_complexity(to_strict_schema(LegPlan.model_json_schema())) == (0, 0)


def test_check_leg_clamps_speed_and_negatives():
    assert check_leg(30, 60, 0, None) == (30.0, 60, 0, False)
    km, minutes, ferry, adjusted = check_leg(100, 30, 0, None)  # 200 km/h
    assert adjusted and minutes == 100
    km, minutes, _, adjusted = check_leg(10, 300, 0, None)  # 2 km/h
    assert adjusted and minutes == 40
    km, minutes, ferry, adjusted = check_leg(-5, -1, 0, None)
    assert adjusted and (km, minutes, ferry) == (0.0, 0, 0)


def test_check_leg_ferry_time_not_counted_in_speed():
    km, minutes, ferry, adjusted = check_leg(20, 100, 60, None)  # 40 phút chạy 20 km: 30 km/h
    assert (km, minutes, ferry, adjusted) == (20.0, 100, 60, False)
    _, minutes, ferry, adjusted = check_leg(20, 30, 60, None)  # phà dài hơn cả chặng
    assert adjusted and ferry == 30 and minutes == 30 + 20


def test_check_leg_not_below_straight_line():
    km, _, _, adjusted = check_leg(1, 5, 0, 10)
    assert adjusted and km == 13.0
    km, _, _, adjusted = check_leg(100, 150, 0, 10)
    assert adjusted and km == 16.0


def test_straight_km_needs_both_points():
    assert straight_km(STOPS[2], STOPS[3]) == pytest.approx(0.65, abs=0.1)
    assert straight_km(STOPS[0], STOPS[2]) is None


def test_estimate_legs_without_web(make_client):
    plan = LegPlan(legs=[_leg(0, 160, 240, ferry=0), _leg(1, 70, 30)], checks=[])  # chặng 1 quá nhanh
    fake = FakeClaude([_reply(plan)])
    out = estimate_legs(
        1, trip_title="Phước Hải", region="Bà Rịa", stops=STOPS, legs=LEGS, client=make_client(fake)
    )
    assert [(g.from_stop_id, g.to_stop_id) for g in out.legs] == [(1, 2), (2, 3), (3, 4)]
    first, second, third = out.legs
    assert (first.km, first.minutes, first.adjusted, first.estimated) == (160.0, 240, False, True)
    assert second.adjusted and second.minutes == 70
    assert third.adjusted and third.note == "Ước tính theo đường chim bay."  # model bỏ sót, có tọa độ
    assert out.checks == [] and len(fake.requests) == 1
    req = fake.requests[0]
    assert req["model"] == "claude-sonnet-5-5" and req["output_config"] == {"effort": "low"}
    assert "tools" not in req and '"index": 2' in req["messages"][0]["content"]


def test_estimate_legs_think_searches_web_then_parses(make_client):
    url = "https://baria-vungtau.gov.vn/pha-cat-lai"
    web = {
        "content": [
            {
                "type": "server_tool_use",
                "id": "srvtoolu_1",
                "name": "web_search",
                "input": {"query": "phà Cát Lái"},
            },
            {
                "type": "web_search_tool_result",
                "tool_use_id": "srvtoolu_1",
                "content": [{"type": "web_search_result", "url": url, "title": "Giờ phà Cát Lái"}],
            },
            {
                "type": "text",
                "text": "[1] Phà Cát Lái: chuyến cuối 22:00. [3] Chợ Phước Hải: 5:00 tới 18:00.",
            },
        ]
    }
    plan = LegPlan(
        legs=[_leg(0, 150, 260, ferry=30), _leg(1, 90, 150), _leg(2, 1, 5)],
        checks=[
            _check(1, "ferry_last", last_time="22:00", source_url=url, text="Chuyến cuối 22:00"),
            _check(
                3,
                "opening_hours",
                open_weekdays=[0, 1, 2, 3, 4, 5, 6],
                open_time="05:00",
                close_time="18:00",
                source_url="https://bia.example/x",
            ),
            _check(0, "opening_hours", open_time="08:00", close_time="17:00"),  # điểm không được hỏi
        ],
    )
    fake = FakeClaude([web, _reply(plan)])
    out = estimate_legs(
        1,
        trip_title="Phước Hải",
        region="Bà Rịa",
        stops=STOPS,
        legs=LEGS,
        think=True,
        client=make_client(fake),
    )
    web_req, parse_req = fake.requests
    assert [t["type"] for t in web_req["tools"]] == ["web_search_20260209"] and "output_format" not in web_req
    assert web_req["tools"][0]["max_uses"] == 4
    assert "tools" not in parse_req and "<ghi_chu_web>" in parse_req["messages"][0]["content"]
    ferry = next(c for c in out.checks if c.kind == "ferry_last")
    assert ferry.stop_id == 2 and ferry.last_time == time(22, 0) and ferry.source_url == url
    market = next(c for c in out.checks if c.kind == "opening_hours")
    assert market.stop_id == 4 and market.source_url is None  # link không có trong kết quả tìm
    periods = market.hours["regular"]["periods"]
    assert len(periods) == 7 and periods[0]["open"] == {"day": 0, "hour": 5, "minute": 0}
    assert len(out.checks) == 2 and out.sources == [{"title": "Giờ phà Cát Lái", "url": url}]


def test_web_failure_still_estimates(make_client):
    from app.ai.schemas import AiRequestError

    plan = LegPlan(legs=[_leg(0, 150, 240), _leg(1, 90, 150), _leg(2, 1, 5)], checks=[])
    fake = FakeClaude([AiRequestError("AI_UNAVAILABLE", "lỗi mạng"), _reply(plan)])
    out = estimate_legs(
        1, trip_title="Phước Hải", region=None, stops=STOPS, legs=LEGS, think=True, client=make_client(fake)
    )
    assert len(out.legs) == 3 and out.checks == []


def test_refusal_returns_none(make_client):
    fake = FakeClaude([{"content": [], "stop_reason": "refusal"}])
    assert (
        estimate_legs(1, trip_title="x", region=None, stops=STOPS, legs=LEGS, client=make_client(fake))
        is None
    )


def test_lunch_break_splits_periods():
    from app.ai.trip_legs import _to_check

    guess = _check(
        0,
        "opening_hours",
        open_weekdays=[0, 2],
        open_time="07:00",
        close_time="17:00",
        break_start="11:00",
        break_end="13:00",
    )
    periods = _to_check(guess, 9, set()).hours["regular"]["periods"]
    assert [(p["open"]["day"], p["open"]["hour"], p["close"]["hour"]) for p in periods] == [
        (0, 7, 11),
        (0, 13, 17),
        (2, 7, 11),
        (2, 13, 17),
    ]


def test_car_allows_higher_speed():
    assert check_leg(90, 60, 0, None, 90) == (90.0, 60, 0, False)
    assert check_leg(90, 60, 0, None)[3] is True


def test_note_carries_main_roads_for_night_rule():
    from app.ai.trip_legs import _note_with_roads

    assert _note_with_roads("Đi ven biển", ["QL55", "ĐT44A"]) == "Đi ven biển Đường chính: QL55, ĐT44A."
    assert _note_with_roads("Đi QL 51 qua Bà Rịa", ["QL51"]) == "Đi QL 51 qua Bà Rịa"
