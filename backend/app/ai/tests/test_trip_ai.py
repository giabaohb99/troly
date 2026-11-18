from app.ai.registry import count_complexity, to_strict_schema
from app.ai.tests.fake_claude import FakeClaude
from app.ai.trip_ai import (
    OptionSummaries,
    OptionSummary,
    TripExtract,
    extract_trip,
    fallback_summary,
    summarize_options,
)

TEXT = (
    "Ngày 1 (thứ 7)\n2h30 Xuất phát Cần Thơ\n"
    "~7h00 Qua [phà Cát Lái](https://www.google.com/maps/search/?api=1&query=pha+cat+lai)\n"
)


def _extract(**kw):
    base = {
        "title": "Phước Hải",
        "travel_mode": "motorbike",
        "origin_text": "Cần Thơ",
        "end_text": "Cần Thơ",
        "start_date": "",
        "nights": 2,
        "days": [
            {
                "day_no": 1,
                "weekday_text": "thứ 7",
                "date": "21/11",
                "title": "Cần Thơ đi Phước Hải",
                "route_text": "",
                "stops": [
                    {
                        "time_text": "~7h00",
                        "title": "Qua phà Cát Lái",
                        "category": "pha",
                        "places": [
                            {
                                "label": "phà Cát Lái",
                                "url": "https://www.google.com/maps/search/?api=1&query=pha+cat+lai",
                                "role": "main",
                            },
                            {"label": "Quán bịa", "url": "https://bia.example/x", "role": "alternative"},
                        ],
                        "cost_note": "",
                        "phone": "",
                        "note": "",
                        "optional": False,
                    }
                ],
            }
        ],
        "hotels": [],
        "map_links": [{"day_no": 1, "label": "Tuyến bịa", "url": "https://maps.example/bia"}],
        "notes": [],
        "facts": [],
    }
    return TripExtract(**{**base, **kw})


def _reply(parsed):
    return {"content": [{"type": "text", "text": parsed.model_dump_json()}], "parsed_output": parsed}


def test_schema_has_no_unions_or_optionals():
    schema = to_strict_schema(TripExtract.model_json_schema())
    assert count_complexity(schema) == (0, 0)
    assert count_complexity(to_strict_schema(OptionSummaries.model_json_schema())) == (0, 0)


def test_extract_drops_invented_links_and_bad_dates(make_client):
    fake = FakeClaude([_reply(_extract())])
    out = extract_trip(1, text=TEXT, client=make_client(fake))
    places = out.days[0].stops[0].places
    assert places[0].url.startswith("https://www.google.com/maps/search")
    assert places[1].url == ""  # link không có trong tệp
    assert out.map_links == [] and out.days[0].date == ""
    req = fake.requests[0]
    assert req["model"] == "claude-haiku-5-5" and req["output_config"] == {"effort": "medium"}
    assert req["max_tokens"] == 32000 and fake.timeouts == [300]
    assert "<lich_trinh>" in req["messages"][0]["content"][0]["text"]


def test_extract_hint_is_sent(make_client):
    fake = FakeClaude([_reply(_extract())])
    extract_trip(1, text=TEXT, hint="thiếu ngày 3", client=make_client(fake))
    assert "thiếu ngày 3" in fake.requests[0]["messages"][0]["content"][-1]["text"]


OPTIONS = [
    {
        "option_id": 11,
        "name": "Đúng giờ, ít rủi ro",
        "total_km": 512.4,
        "total_ride_minutes": 690,
        "night_ride_minutes": 45,
        "red_count": 0,
        "yellow_count": 2,
        "changes": ["Bỏ An Nhứt"],
        "risks": [{"code": "R3", "level": "yellow", "day_no": 2, "message": "Phà cuối 17:00"}],
    },
    {
        "option_id": 12,
        "name": "Nhiều điểm",
        "total_km": 540,
        "total_ride_minutes": 750,
        "night_ride_minutes": 90,
        "red_count": 1,
        "yellow_count": 3,
        "changes": [],
        "risks": [],
    },
]


def _summaries(*items):
    return OptionSummaries(items=[OptionSummary(**i) for i in items])


def test_summaries_keep_only_known_numbers(make_client):
    good = {
        "option_id": 11,
        "summary": "Đi khoảng 512 km, 11 giờ 30 phút chạy xe. Còn 2 rủi ro vàng.",
        "tips": [],
    }
    bad = {"option_id": 12, "summary": "Đi 600 km. Còn 1 rủi ro đỏ.", "tips": []}
    fixed = {
        "option_id": 12,
        "summary": "Đi khoảng 540 km. Còn 1 rủi ro đỏ và 3 rủi ro vàng.",
        "tips": ["Gọi phà"],
    }
    fake = FakeClaude([_reply(_summaries(good, bad)), _reply(_summaries(fixed))])
    out = summarize_options(1, trip_title="Phước Hải", options=OPTIONS, client=make_client(fake))
    assert [o.option_id for o in out] == [11, 12]
    assert out[0].summary == good["summary"] and out[1].summary == fixed["summary"]
    assert "600" in fake.requests[1]["messages"][0]["content"]
    assert fake.requests[0]["model"] == "claude-sonnet-5-5" and fake.requests[0]["beta"] is True


def test_summaries_fall_back_to_code_when_still_wrong(make_client):
    bad = {"option_id": 11, "summary": "Đi 999 km.", "tips": []}
    fake = FakeClaude([_reply(_summaries(bad)), _reply(_summaries(bad))])
    out = summarize_options(1, trip_title="X", options=OPTIONS[:1], client=make_client(fake))
    assert out[0] == fallback_summary(OPTIONS[0])
    assert out[0].summary.startswith("Đúng giờ, ít rủi ro: khoảng 512 km, 11 giờ 30 phút chạy xe.")
