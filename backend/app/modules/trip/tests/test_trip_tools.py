"""Công cụ AI của lịch trình trên tệp mẫu Phước Hải – Trà Vinh (bài kiểm của agent AI, việc 4-02).
Claude và Maps giả theo fixture của agent Google (conftest.py cùng thư mục)."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.ai.schemas import ToolContext
from app.modules.trip import tools
from app.modules.trip.models import Trip
from app.modules.trip.tests.conftest import run_job


@pytest.fixture
def ctx(db, user):
    return ToolContext(session=db, user=user, conversation_id=None, now=datetime(2026, 11, 18, 5, tzinfo=UTC))


def _spec(name):
    return next(t for t in tools.TOOLS if t.name == name)


def _call(ctx, name, **data):
    spec = _spec(name)
    return spec.run(ctx, spec.input_model.model_validate(data))


@pytest.fixture
def trip_id(db, ctx, maps_fake, fake_ai, sample_file):
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
    assert out.result["status"] == "importing" and out.actions[0]["screen"] == "trip_detail"
    run_job(db, "trip_import", out.result["trip_id"])
    return out.result["trip_id"]


def test_get_trip_compact_by_query(ctx, trip_id):
    out = _call(ctx, "get_trip", trip_id=None, query="Trà Vinh", day_no=3)
    r = out.result
    assert r["trip_id"] == trip_id and [d["day_no"] for d in r["days"]] == [3]
    assert all("lat" not in s for s in r["days"][0]["stops"])
    assert {f["kind"] for f in r["facts"]} >= {"checkin", "ferry_last"}


def test_evaluate_then_save_option(db, ctx, trip_id, maps_fake, fake_ai):
    out = _call(ctx, "evaluate_trip", trip_id=trip_id)
    assert out.result["status"] == "evaluating"
    run_job(db, "trip_evaluate", trip_id)
    got = _call(ctx, "get_trip", trip_id=trip_id, query=None, day_no=None).result
    assert got["options"] and any(r["code"] == "R2" for r in got["risks"])
    saved = _call(ctx, "save_trip", trip_id=trip_id, option_id=got["options"][0]["id"])
    assert saved.result["status"] == "planned"


def test_open_route_day_and_stop(ctx, trip_id):
    day = _call(ctx, "open_route", trip_id=trip_id, stop_id=None, place_query=None, scope="day", day_no=2)
    assert day.actions and all(a["type"] == "open_map_directions" and "id" not in a for a in day.actions)
    stop = _call(
        ctx, "open_route", trip_id=trip_id, stop_id=None, place_query="Chùa Âng", scope="stop", day_no=3
    )
    assert stop.actions[0]["type"] in ("open_map_navigation", "open_map_place")


def test_find_place_returns_paste_ready_link(ctx, maps_fake):
    out = _call(ctx, "find_place", query="bún nước lèo Trà Vinh", near=None)
    item = out.result["items"][0]
    assert item["place_id"] and item["link"].startswith(
        f"[{item['name']}](https://www.google.com/maps/search/"
    )
    assert "query_place_id=" in item["link"]


def test_delete_trip_always_needs_approval(db, ctx, trip_id):
    spec = _spec("delete_trip")
    data = spec.input_model.model_validate({"trip_id": trip_id, "reason": "không đi nữa"})
    assert spec.needs_approval(data) is True
    draft = spec.prepare(ctx, data)
    assert draft.danger and draft.input == {"trip_id": trip_id} and db.get(Trip, trip_id) is not None
    spec.execute(ctx, draft.input)
    assert db.get(Trip, trip_id) is None


def test_list_trips(ctx, trip_id):
    out = _call(ctx, "list_trips", status=None, query=None)
    assert [t["id"] for t in out.result["items"]] == [trip_id]


def test_find_place_without_maps_returns_search_link(ctx, no_maps):
    out = _call(ctx, "find_place", query="Bãi Sau Vũng Tàu", near=None)
    item = out.result["items"][0]
    assert item["verified"] is False and item["place_id"] is None
    assert item["link"].startswith("[Bãi Sau Vũng Tàu](https://www.google.com/maps/search/?api=1&query=")
    assert "query_place_id" not in item["link"] and "nguồn web" in out.result["ghi_chu"]


def test_chat_builds_trip_from_description_without_maps(auth_client, db, no_maps, monkeypatch):
    """Câu mô tả -> Sonnet tìm web -> find_place (không Maps, link tìm) -> import_trip. Claude giả."""
    import uuid

    from app.ai import client as ai_client
    from app.ai.models import DbRunRecorder
    from app.ai.registry import get_tool, register_tools
    from app.ai.tests.fake_claude import FakeClaude, text_reply, tool_call

    if get_tool("import_trip") is None:
        register_tools(tools.TOOLS)
    url = "https://vungtau.example.vn/bai-sau"
    search = {
        "content": [
            {
                "type": "server_tool_use",
                "id": "srvtoolu_1",
                "name": "web_search",
                "input": {"query": "điểm tham quan Vũng Tàu"},
            },
            {
                "type": "web_search_tool_result",
                "tool_use_id": "srvtoolu_1",
                "content": [{"type": "web_search_result", "url": url, "title": "Bãi Sau Vũng Tàu"}],
            },
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "find_place",
                "input": {"query": "Bãi Sau Vũng Tàu", "near": None},
            },
        ],
        "stop_reason": "tool_use",
    }
    itinerary = (
        "Ngày 1 (thứ 7)\n5h00 Xuất phát Cần Thơ\n"
        "15h00 Tắm biển [Bãi Sau Vũng Tàu](https://www.google.com/maps/search/?api=1&query=B%C3%A3i+Sau)\n"
    )
    fake = FakeClaude(
        [
            search,
            tool_call(
                "import_trip",
                {
                    "file_id": None,
                    "text": itinerary,
                    "url": None,
                    "title": "Vũng Tàu 2 ngày",
                    "start_date": "2026-11-21",
                    "travel_mode": None,
                },
                tool_id="toolu_2",
            ),
            text_reply("Em đã dựng chuyến Vũng Tàu 2 ngày, đang đọc lịch trình."),
        ]
    )
    monkeypatch.setattr(ai_client, "_client", ai_client.ClaudeClient(sdk=fake, recorder=DbRunRecorder()))
    resp = auth_client.post(
        "/api/v1/chat/messages",
        json={
            "client_message_id": str(uuid.uuid4()),
            "text": "tạo lịch trình đi Vũng Tàu 2 ngày, xuất phát Cần Thơ",
        },
    )
    assert resp.status_code == 200, resp.text
    first = fake.requests[0]
    assert first["model"] == "claude-sonnet-5-5"
    assert any(t.get("type") == "web_search_20260209" for t in first["tools"])
    find_result = next(
        b
        for m in fake.requests[1]["messages"]
        if isinstance(m["content"], list)
        for b in m["content"]
        if b.get("type") == "tool_result" and b.get("tool_use_id") == "toolu_1"
    )
    assert '"verified": false' in str(find_result["content"]).lower().replace("False", "false")
    trip = db.scalars(select(Trip)).one()
    assert trip.status == "importing" and trip.start_date == date(2026, 11, 21)
    assert any(
        a["screen"] == "trip_detail"
        for a in resp.json()["data"]["assistant_message"]["actions"]
        if a["type"] == "open_screen"
    )
