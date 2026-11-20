"""Thêm, sửa, bỏ điểm dừng trong chuyến có sẵn qua chat (lỗi thật 19/11: xin thêm chỗ đổ xăng mỗi 150 km)."""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.ai.schemas import ToolContext
from app.modules.trip import tools
from app.modules.trip.models import TripStop
from app.modules.trip.tests.conftest import run_job


@pytest.fixture
def ctx(db, user):
    return ToolContext(session=db, user=user, conversation_id=None, now=datetime(2026, 11, 19, 5, tzinfo=UTC))


def _call(ctx, name, **data):
    spec = next(t for t in tools.TOOLS if t.name == name)
    return spec.run(ctx, spec.input_model.model_validate(data))


@pytest.fixture
def evaluated(db, ctx, maps_fake, fake_ai, sample_file):
    out = _call(
        ctx,
        "import_trip",
        file_id=sample_file,
        text=None,
        url=None,
        title=None,
        start_date=date(2026, 11, 21),
        travel_mode=None,
    )
    trip_id = out.result["trip_id"]
    run_job(db, "trip_import", trip_id)
    _call(ctx, "evaluate_trip", trip_id=trip_id)
    return trip_id


def _day1(db, trip_id):
    return list(
        db.scalars(
            select(TripStop).where(TripStop.trip_id == trip_id, TripStop.day_no == 1).order_by(TripStop.seq)
        )
    )


def test_get_trip_shows_cumulative_km_for_fuel_planning(ctx, evaluated):
    got = _call(ctx, "get_trip", trip_id=evaluated, query=None, day_no=1).result
    kms = [s["km_tu_dau_ngay"] for s in got["days"][0]["stops"] if s["km_tu_dau_ngay"] is not None]
    assert kms and kms == sorted(kms) and kms[-1] > 0


def test_add_fuel_stops_in_place_and_reevaluate(db, ctx, evaluated):
    first, second = _day1(db, evaluated)[:2]
    out = _call(
        ctx,
        "add_trip_stops",
        trip_id=evaluated,
        stops=[
            {
                "day_no": 1,
                "title": "Đổ xăng ở Long Thành",
                "category": "di_chuyen",
                "after_stop_id": first.id,
                "place_query": "cây xăng gần Long Thành, Đồng Nai",
            },
            {
                "day_no": 1,
                "title": "Đổ xăng ở Bà Rịa",
                "category": "di_chuyen",
                "after_stop_id": second.id,
                "place_query": "cây xăng gần Bà Rịa",
            },
        ],
    )
    assert out.result["da_danh_gia_lai"] is True and out.result["options"]
    titles = [s.title for s in _day1(db, evaluated)]
    assert titles[1] == "Đổ xăng ở Long Thành" and titles[3] == "Đổ xăng ở Bà Rịa"
    fuel = next(s for s in _day1(db, evaluated) if s.title == "Đổ xăng ở Bà Rịa")
    assert fuel.stay_minutes == 10 and fuel.place_query == "cây xăng gần Bà Rịa"


def test_delete_stop_offers_undo_by_chat(db, ctx, evaluated):
    stops = _day1(db, evaluated)
    out = _call(ctx, "delete_trip_stop", trip_id=evaluated, stop_id=stops[1].id)
    assert db.get(TripStop, stops[1].id) is None
    undo = out.actions[0]
    assert undo["type"] == "choices" and undo["options"][0]["label"] == "Hoàn tác"
    assert stops[1].title in undo["options"][0]["value"] and stops[0].title in undo["options"][0]["value"]
    from app.ai.schemas import AiError

    with pytest.raises(AiError, match="đã xóa trước đó"):
        _call(ctx, "delete_trip_stop", trip_id=evaluated, stop_id=stops[1].id)


def test_chat_adds_two_fuel_stops_to_existing_trip(auth_client, db, user, evaluated, monkeypatch):
    """Một lượt chat: Claude giả đọc chuyến rồi gọi add_trip_stops với 2 điểm đổ xăng theo thị trấn."""
    from app.ai import client as ai_client
    from app.ai.models import DbRunRecorder
    from app.ai.registry import get_tool, register_tools
    from app.ai.tests.fake_claude import FakeClaude, text_reply, tool_call

    if get_tool("add_trip_stops") is None:
        register_tools(tools.TOOLS)
    first, second = _day1(db, evaluated)[:2]
    fake = FakeClaude(
        [
            tool_call("get_trip", {"trip_id": evaluated, "query": None, "day_no": 1}, tool_id="toolu_1"),
            tool_call(
                "add_trip_stops",
                {
                    "trip_id": evaluated,
                    "stops": [
                        {
                            "day_no": 1,
                            "title": "Đổ xăng ở Long Thành",
                            "category": "di_chuyen",
                            "after_stop_id": first.id,
                            "place_query": "cây xăng gần Long Thành",
                        },
                        {
                            "day_no": 1,
                            "title": "Đổ xăng ở Bà Rịa",
                            "category": "di_chuyen",
                            "after_stop_id": second.id,
                            "place_query": "cây xăng gần Bà Rịa",
                        },
                    ],
                },
                tool_id="toolu_2",
            ),
            text_reply("Em đã thêm 2 chỗ đổ xăng ở Long Thành và Bà Rịa, đánh giá lại xong."),
        ]
    )
    monkeypatch.setattr(ai_client, "_client", ai_client.ClaudeClient(sdk=fake, recorder=DbRunRecorder()))
    resp = auth_client.post(
        "/api/v1/chat/messages",
        json={
            "client_message_id": str(uuid.uuid4()),
            "text": "tìm cây xăng trên đường cho chuyến Phước Hải, khoảng 150 km đổ 1 lần rồi thêm vào lịch trình",
        },
    )
    assert resp.status_code == 200, resp.text
    names = {t["name"] for t in fake.requests[0]["tools"]}
    assert {"add_trip_stops", "update_trip_stop", "delete_trip_stop"} <= names
    titles = [s.title for s in _day1(db, evaluated)]
    assert "Đổ xăng ở Long Thành" in titles and "Đổ xăng ở Bà Rịa" in titles
    result = next(
        b
        for m in fake.requests[2]["messages"]
        if isinstance(m["content"], list)
        for b in m["content"]
        if b.get("type") == "tool_result" and b.get("tool_use_id") == "toolu_2"
    )
    assert "da_danh_gia_lai" in str(result["content"]) and result.get("is_error") is not True


def test_move_stop_to_other_day_after_given_stop(db, ctx, evaluated):
    stop = _day1(db, evaluated)[1]
    day2 = list(
        db.scalars(
            select(TripStop).where(TripStop.trip_id == evaluated, TripStop.day_no == 2).order_by(TripStop.seq)
        )
    )
    _call(ctx, "update_trip_stop", trip_id=evaluated, stop_id=stop.id, day_no=2, after_stop_id=day2[0].id)
    moved = list(
        db.scalars(
            select(TripStop).where(TripStop.trip_id == evaluated, TripStop.day_no == 2).order_by(TripStop.seq)
        )
    )
    assert [s.id for s in moved][:2] == [day2[0].id, stop.id]
    assert [s.seq for s in moved] == list(range(1, len(moved) + 1))


# ---------- QĐ-42: Đã đi, Đi lại ----------


def test_archive_moves_trip_to_past_and_back(ctx, evaluated):
    out = _call(ctx, "archive_trip", trip_id=evaluated, archived=True)
    assert out.result["da_luu_tru"] is True
    past = _call(ctx, "list_trips", status=None, query=None, scope="past").result["items"]
    assert [t["id"] for t in past] == [evaluated]
    _call(ctx, "archive_trip", trip_id=evaluated, archived=False)
    assert _call(ctx, "list_trips", status=None, query=None, scope="past").result["items"] == []


def test_chat_go_again_duplicates_then_asks_to_evaluate(auth_client, db, evaluated, monkeypatch):
    from app.ai import client as ai_client
    from app.ai.models import DbRunRecorder
    from app.ai.registry import get_tool, register_tools
    from app.ai.tests.fake_claude import FakeClaude, text_reply, tool_call
    from app.modules.trip.models import Trip

    if get_tool("duplicate_trip") is None:
        register_tools(tools.TOOLS)
    fake = FakeClaude(
        [
            tool_call("duplicate_trip", {"trip_id": evaluated, "start_date": "2026-11-28", "title": None}),
            text_reply("Em đã chép chuyến sang 28/11. Đại ca có muốn em đánh giá lại không?"),
        ]
    )
    monkeypatch.setattr(ai_client, "_client", ai_client.ClaudeClient(sdk=fake, recorder=DbRunRecorder()))
    resp = auth_client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid.uuid4()), "text": "đi lại chuyến Phước Hải ngày 28/11"},
    )
    assert resp.status_code == 200, resp.text
    trips = list(db.scalars(select(Trip).order_by(Trip.id)))
    assert len(trips) == 2 and trips[1].start_date == date(2026, 11, 28) and trips[1].evaluation is None
    result = next(
        b
        for m in fake.requests[1]["messages"]
        if isinstance(m["content"], list)
        for b in m["content"]
        if b.get("type") == "tool_result"
    )
    assert "evaluate_trip" in str(result["content"])
    system = str(fake.requests[0]["system"])
    assert "archive_trip" in system and "duplicate_trip" in system


def test_fix_wrong_area_for_navigation(db, ctx, evaluated):
    """Dẫn đường ra quán trùng tên ở Cần Thơ: người dùng báo, bot sửa area của điểm."""
    stop = _day1(db, evaluated)[1]
    _call(ctx, "update_trip_stop", trip_id=evaluated, stop_id=stop.id, area="Phước Hải, Bà Rịa - Vũng Tàu")
    db.refresh(stop)
    assert stop.area == "Phước Hải, Bà Rịa - Vũng Tàu"
    out = _call(
        ctx,
        "add_trip_stops",
        trip_id=evaluated,
        stops=[
            {
                "day_no": 1,
                "title": "Đổ xăng ở Long Thành",
                "category": "di_chuyen",
                "area": "Long Thành, Đồng Nai",
            }
        ],
    )
    added = db.get(TripStop, out.result["da_them"][0]["stop_id"])
    assert added.area == "Long Thành, Đồng Nai"
