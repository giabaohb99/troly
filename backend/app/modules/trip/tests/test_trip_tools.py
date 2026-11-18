"""Công cụ AI của lịch trình trên tệp mẫu Phước Hải – Trà Vinh (bài kiểm của agent AI, việc 4-02).
Claude và Maps giả theo fixture của agent Google (conftest.py cùng thư mục)."""

from datetime import UTC, date, datetime

import pytest

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
