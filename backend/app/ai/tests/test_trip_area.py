"""infer_stop_areas (hợp đồng agent Google): sửa chuyến 7, điểm không chắc bỏ khỏi kết quả, lỗi thì ném."""

import pytest

from app.ai.schemas import AiError
from app.ai.tests.fake_claude import FakeClaude
from app.ai.trip_area import DayAreas, StopArea, infer_stop_areas

DAY = {
    "day_no": 1,
    "title": "Cần Thơ → Phước Hải",
    "route_text": "Đường đi: QL1A → Tân An → phà Cát Lái → Nhơn Trạch → Long Hải → Phước Hải (khoảng 250 km)",
}
STOPS = [
    {"stop_id": 201, "title": "Xuất phát", "place_query": "Ninh Kiều, Cần Thơ", "category": "khac"},
    {"stop_id": 202, "title": "Qua phà Cát Lái", "place_query": "phà Cát Lái", "category": "pha"},
    {"stop_id": 203, "title": "Tắm biển Long Hải", "place_query": "biển Long Hải", "category": "tham_quan"},
    {"stop_id": 204, "title": "Ăn tối", "place_query": "quán hải sản", "category": "an_uong"},
]


def _reply(items, dest="Phước Hải, Bà Rịa - Vũng Tàu"):
    parsed = DayAreas(day_destination=dest, stops=[StopArea(index=i, area=a) for i, a in items])
    return {"content": [{"type": "text", "text": parsed.model_dump_json()}], "parsed_output": parsed}


def test_trip7_day1_after_ferry_is_destination(make_client):
    fake = FakeClaude(
        [
            _reply(
                [
                    (0, "Ninh Kiều, Cần Thơ"),
                    (1, "Cát Lái, TP. Hồ Chí Minh"),
                    (2, " Long Hải,  Bà Rịa - Vũng Tàu "),
                    (3, ""),  # không chắc: bỏ, trip giữ kết quả theo luật
                    (7, "bịa"),
                ]
            )
        ]
    )
    out = infer_stop_areas(1, "Phước Hải - Trà Vinh", DAY, STOPS, client=make_client(fake))
    assert out == {
        201: "Ninh Kiều, Cần Thơ",
        202: "Cát Lái, TP. Hồ Chí Minh",
        203: "Long Hải, Bà Rịa - Vũng Tàu",
    }
    req = fake.requests[0]
    assert req["model"] == "claude-haiku-5-5" and "tools" not in req and len(fake.requests) == 1
    sent = req["messages"][0]["content"]
    assert "phà Cát Lái" in sent and '"category": "pha"' in sent and "từ điểm phà" in str(req["system"])


def test_refusal_raises_and_empty_day_skips_call(make_client):
    fake = FakeClaude([{"content": [], "stop_reason": "refusal"}])
    with pytest.raises(AiError):
        infer_stop_areas(1, "x", DAY, STOPS, client=make_client(fake))
    empty = FakeClaude([])
    assert infer_stop_areas(1, "x", DAY, [], client=make_client(empty)) == {} and empty.requests == []
