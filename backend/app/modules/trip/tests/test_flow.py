"""Chạy thử trên chính tệp mẫu Phước Hải – Trà Vinh (41 mục 9): nhập, định vị, đánh giá, phương án,
link bản đồ, xuất Word, đưa vào lịch. Claude và Maps đều giả."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.models import JobQueue
from app.modules.trip import service
from app.modules.trip.models import PlaceCache, RouteCache, Trip, TripFact, TripOption, TripStop
from app.modules.trip.reader import parse_maps_url, read_docx
from app.modules.trip.tests.conftest import run_job


@pytest.fixture
def imported(db, user, maps_fake, fake_ai, sample_file):
    data = service.import_trip(db, user, file_id=sample_file, start_date=date(2026, 11, 21))
    run_job(db, "trip_import", data["trip_id"])
    return db.get(Trip, data["trip_id"])


def _stops(db, trip_id):
    return list(
        db.scalars(
            select(TripStop).where(TripStop.trip_id == trip_id).order_by(TripStop.day_no, TripStop.seq)
        )
    )


def test_import_sample_builds_three_days_and_facts(db, imported, maps_fake):
    assert imported.status == "draft", imported.error
    assert (imported.start_date, imported.end_date) == (date(2026, 11, 21), date(2026, 11, 23))
    stops = _stops(db, imported.id)
    assert {s.day_no for s in stops} == {1, 2, 3}
    kinds = {f.kind for f in db.scalars(select(TripFact).where(TripFact.trip_id == imported.id))}
    assert kinds == {"checkin", "checkout", "ferry_last", "hotline"}
    ferry_fact = db.scalar(select(TripFact).where(TripFact.kind == "ferry_last"))
    ferry_stop = db.get(TripStop, ferry_fact.stop_id)
    assert ferry_stop.category == "pha" and "Vũng Tàu" in ferry_stop.title
    hotel = next(s for s in stops if s.day_no == 1 and s.category == "khach_san")
    assert hotel.coord_source == "user" and float(hotel.lat) == pytest.approx(10.4477939)
    assert hotel.place_id  # link rút gọn đọc qua Resolution API


def test_places_use_cheap_field_masks_and_cache(db, imported, maps_fake):
    masks = maps_fake.masks("places:searchText")
    assert masks and set(masks) == {"places.id"}
    details = maps_fake.masks("places.googleapis.com/v1/places/pl_")
    assert all("displayName" not in m and "OpeningHours" not in m for m in details)
    assert db.scalar(select(PlaceCache).limit(1)) is not None
    generic = [s for s in _stops(db, imported.id) if s.role == "generic"]
    assert generic and all(s.alternatives and "lat" not in s.alternatives[0] for s in generic)


def test_evaluate_finds_monday_museum_ferry_and_night_ride(db, user, imported, maps_fake, fake_ai):
    service.evaluate_trip(db, user, imported.id)
    run_job(db, "trip_evaluate", imported.id)
    db.refresh(imported)
    assert imported.status == "draft", imported.error
    risks = imported.evaluation["risks"]
    museum = [r for r in risks if r["code"] == "R2" and r["level"] == "red" and "thứ Hai" in r["message"]]
    assert museum and museum[0]["day_no"] == 3
    assert any(r["code"] == "R5" and r["level"] == "red" and r["day_no"] == 1 for r in risks)
    assert any(r["code"] == "R3" and r["day_no"] == 2 for r in risks)
    assert {"code", "level", "day_no", "stop_id", "message", "suggestion", "checked_at"} <= set(risks[0])
    options = list(db.scalars(select(TripOption).where(TripOption.trip_id == imported.id)))
    assert 2 <= len(options) <= 3 and options[0].name == "Nhiều điểm"
    safe = next((o for o in options if o.name == "Đúng giờ, ít rủi ro"), None)
    assert safe is not None and any("Bảo tàng" in c for c in safe.changes)
    assert all(o.summary and o.total_km and o.total_km > 0 for o in options)
    assert imported.evaluation["advice"] == [
        "Gọi hotline phà trước 1 ngày.",
        "Mặc áo phản quang khi chạy đêm.",
    ]
    hours_masks = [m for m in maps_fake.masks("v1/places/pl_") if "OpeningHours" in m]
    assert hours_masks  # giờ mở cửa chỉ xin lúc đánh giá
    routes = maps_fake.calls(":computeRoutes")
    assert routes and all('"TWO_WHEELER"' in r.content.decode() for r in routes)
    assert db.scalar(select(RouteCache).limit(1)) is not None


def test_second_evaluation_reuses_route_cache(db, user, imported, maps_fake, fake_ai):
    service.evaluate_trip(db, user, imported.id)
    run_job(db, "trip_evaluate", imported.id)
    first = len(maps_fake.calls(":computeRoutes"))
    db.execute(JobQueue.__table__.delete())
    service.evaluate_trip(db, user, imported.id)
    run_job(db, "trip_evaluate", imported.id)
    assert len(maps_fake.calls(":computeRoutes")) == first


def test_choose_option_applies_plan(db, user, imported, maps_fake, fake_ai):
    service.evaluate_trip(db, user, imported.id)
    run_job(db, "trip_evaluate", imported.id)
    safe = db.scalar(select(TripOption).where(TripOption.name == "Đúng giờ, ít rủi ro"))
    data = service.choose_option(db, user, imported.id, safe.id)
    assert data["status"] == "planned" and data["chosen_option_id"] == safe.id
    titles = [s["title"] for d in data["days"] for s in d["stops"]]
    assert not any("Bảo tàng" in t for t in titles)


def test_map_links_split_like_sample(db, user, imported):
    data = service.map_links(db, user, imported.id, None, 9)
    by_day = {d["day_no"]: d for d in data["days"]}
    assert len(by_day[1]["segments"]) >= 2
    for day in data["days"]:
        for seg in day["segments"]:
            url = seg["urls"][0]
            assert len(url) <= 2048 and "travelmode=two-wheeler" in url and "avoid=highways" in url
            assert len(parse_maps_url(url).waypoints) <= 9
    small = service.map_links(db, user, imported.id, 1, 3)
    assert all(len(parse_maps_url(s["urls"][0]).waypoints) <= 3 for s in small["days"][0]["segments"])


def test_route_actions_for_chat(db, user, imported):
    stop = next(s for s in _stops(db, imported.id) if s.lat is not None and s.category == "an_uong")
    actions = service.route_actions(db, user, trip_id=imported.id, stop_id=stop.id)
    assert actions[0]["type"] == "open_map_navigation" and actions[0]["mode"] == "l"
    day = service.route_actions(db, user, trip_id=imported.id, scope="day", day_no=2)
    assert day and all(a["type"] == "open_map_directions" for a in day)


def test_export_docx_round_trip(db, user, imported, stored_files, maps_fake, fake_ai):
    service.evaluate_trip(db, user, imported.id)
    run_job(db, "trip_evaluate", imported.id)
    result = service.export_docx(db, user, imported.id)
    data = stored_files[result["file_id"]]
    doc = read_docx(data)
    assert doc.tables == 3
    assert "## Ngày 1 (thứ 7, 21/11)" in doc.text and "### Bản đồ ngày 1" in doc.text
    assert any("two-wheeler" in u for u in doc.links) and any("/maps/search/" in u for u in doc.links)
    assert "Thời gian xe máy do Google ước tính" in doc.text
    import io

    from docx import Document

    word = Document(io.BytesIO(data))
    assert word.styles["Title"].font.size.pt == 18
    assert word.sections[0].page_width.twips == 11906


def test_to_calendar_creates_day_and_fixed_events(db, user, imported):
    result = service.to_calendar(db, user, imported.id)
    assert len(result["event_ids"]) >= 3
    from app.modules.calendar.models import Event

    events = list(db.scalars(select(Event).where(Event.id.in_(result["event_ids"]))))
    assert sum(e.all_day for e in events) == 3
    assert all(e.remind_source == "app" for e in events)


def test_change_start_date_shifts_times(db, user, imported):
    before = _stops(db, imported.id)[0].planned_start
    service.update_trip(db, user, imported.id, {"start_date": date(2026, 11, 28)})
    after = _stops(db, imported.id)[0].planned_start
    assert after - before == timedelta(days=7)


def test_without_maps_key_import_keeps_points_to_confirm(db, user, no_maps, fake_ai, sample_file):
    data = service.import_trip(db, user, file_id=sample_file)
    run_job(db, "trip_import", data["trip_id"])
    trip = service.get_trip(db, user, data["trip_id"])
    assert trip["status"] == "draft" and trip["start_date_suggested"] is True
    assert trip["needs_confirmation"]


def test_failed_extraction_marks_trip_failed(db, user, maps_fake, sample_file, monkeypatch):
    from app.modules.trip import bridge

    monkeypatch.setattr(bridge, "extract_trip", lambda *a, **k: None)
    data = service.import_trip(db, user, file_id=sample_file)
    run_job(db, "trip_import", data["trip_id"])
    trip = db.get(Trip, data["trip_id"])
    assert trip.status == "failed" and trip.error


def test_other_user_cannot_read_trip(db, user, imported):
    from app.core.context import UserContext
    from app.core.errors import NotFoundError

    with pytest.raises(NotFoundError):
        service.get_trip(
            db, UserContext(user_id=user.user_id + 999, timezone="Asia/Ho_Chi_Minh"), imported.id
        )


def test_pick_candidate_by_place_id_only(db, user, imported, maps_fake):
    stop = next(s for s in _stops(db, imported.id) if s.role == "main" and s.place_query)
    found = service.resolve_candidates(db, user, imported.id, stop.id, "Chùa Âng Trà Vinh")
    pid = found["candidates"][0]["place_id"]
    data = service.update_stop(db, user, imported.id, stop.id, {"place_id": pid})
    assert data["lat"] is not None and data["resolve_status"] == "manual" and data["place_id"] == pid


def test_ai_extract_converts_to_trip_schema():
    from app.ai.trip_ai import TripExtract as AiExtract
    from app.modules.trip.bridge import from_ai_extract
    from app.modules.trip.schemas import TripExtract

    stop = {
        "time_text": "~7h00",
        "title": "Ăn sáng",
        "category": "an_uong",
        "places": [{"label": "Chợ", "url": "", "role": "main"}],
        "cost_note": "",
        "phone": "",
        "note": "",
        "optional": False,
    }
    raw = AiExtract.model_validate(
        {
            "title": "Chuyến thử",
            "travel_mode": "unknown",
            "origin_text": "",
            "end_text": "",
            "start_date": "",
            "nights": 1,
            "days": [
                {
                    "day_no": 1,
                    "weekday_text": "thứ 7",
                    "date": "",
                    "title": "",
                    "route_text": "",
                    "stops": [stop],
                }
            ],
            "hotels": [
                {
                    "night_no": 1,
                    "label": "Khách sạn A",
                    "url": "",
                    "booked": False,
                    "backups": ["Khách sạn B"],
                }
            ],
            "map_links": [],
            "notes": [],
            "facts": [
                {"kind": "hotline", "day_no": 0, "value_time": "", "value_text": "0123", "text": "Gọi"}
            ],
        }
    )
    out = from_ai_extract(raw, TripExtract)
    assert out.travel_mode == "motorbike" and out.start_date is None and out.origin_text is None
    assert out.days[0].stops[0].places[0].url is None and out.facts[0].day_no is None
    assert out.hotels[0].backups[0].label == "Khách sạn B"


def test_find_trip_by_query_and_day(db, user, imported):
    data = service.find_trip(db, user, query="Phước Hải", day_no=2)
    assert data["id"] == imported.id and [d["day_no"] for d in data["days"]] == [2]
