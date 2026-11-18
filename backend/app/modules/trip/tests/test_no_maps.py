"""QĐ-36: V1 không có Maps Platform. Chạy trọn tệp mẫu Phước Hải – Trà Vinh không có khóa Maps:
ra 3 ngày, link mở đúng, rủi ro bảo tàng thứ Hai và giờ phà vẫn có; thời gian chạy là ước tính."""

from datetime import date
from urllib.parse import unquote

import pytest
from sqlalchemy import select

from app.modules.trip import service
from app.modules.trip.hours_text import hours_from_text
from app.modules.trip.models import Trip, TripOption, TripStop
from app.modules.trip.reader import parse_maps_url, read_docx
from app.modules.trip.tests.conftest import run_job


@pytest.fixture
def trip(db, user, no_maps, fake_ai, sample_file):
    data = service.import_trip(db, user, file_id=sample_file, start_date=date(2026, 11, 21))
    run_job(db, "trip_import", data["trip_id"])
    return db.get(Trip, data["trip_id"])


def _stops(db, trip_id):
    return list(
        db.scalars(
            select(TripStop).where(TripStop.trip_id == trip_id).order_by(TripStop.day_no, TripStop.seq)
        )
    )


def _evaluate(db, user, trip, mode="normal"):
    service.evaluate_trip(db, user, trip.id, mode=mode)
    run_job(db, "trip_evaluate", trip.id)
    db.refresh(trip)
    return trip.evaluation["risks"]


def test_import_without_maps_key_keeps_file_links(db, trip, no_maps):
    assert trip.status == "draft", trip.error
    stops = _stops(db, trip.id)
    assert {s.day_no for s in stops} == {1, 2, 3}
    linked = [s for s in stops if s.source_url and "/maps/search/" in s.source_url]
    assert len(linked) >= 30
    assert not no_maps  # không một lời gọi Maps nào


def test_map_links_by_name_and_navigation_by_name(db, user, trip):
    data = service.map_links(db, user, trip.id, None, 9)
    for day in data["days"]:
        assert day["segments"], day["day_no"]
        for seg in day["segments"]:
            url = seg["urls"][0]
            assert "travelmode=two-wheeler" in url and len(url) <= 2048
            assert len(parse_maps_url(url).waypoints) <= 9
    day2 = next(d for d in data["days"] if d["day_no"] == 2)
    assert "Làng chài Phước Hải" in unquote(day2["segments"][0]["urls"][0])
    unlocated = next(s for d in data["days"] for s in d["stops"] if s["lat"] is None and s["navigation"])
    nav = unlocated["navigation"]
    assert nav["lat"] is None and nav["query"]
    assert nav["uri"].startswith("google.navigation:q=") and nav["uri"].endswith("&mode=l&avoid=h")
    assert unquote(nav["uri"].split("q=", 1)[1].split("&mode")[0]) == nav["query"]
    assert unlocated["place"]["type"] == "open_map_place" and unlocated["place"]["query"]


def test_evaluate_with_estimates_finds_museum_ferry_and_night(db, user, trip, no_maps, fake_ai):
    risks = _evaluate(db, user, trip)
    assert trip.status == "draft", trip.error
    assert fake_ai["estimate"][0]["web"] is False
    museum = [r for r in risks if r["code"] == "R2" and "thứ Hai" in r["message"]]
    assert museum and museum[0]["day_no"] == 3 and museum[0]["level"] == "yellow"  # tệp ghi *có thể*
    assert "Bảo tàng" in museum[0]["message"]
    assert (
        len([r for r in risks if r["code"] == "R2" and r["day_no"] == 3]) == 1
    )  # Ao Bà Om, Chùa Âng không bị gán
    assert [r for r in risks if r["code"] == "R3" and r["day_no"] == 2]
    night = [r for r in risks if r["code"] == "R5" and r["day_no"] == 1]
    assert night and night[0]["level"] == "red" and "(ước tính)" in night[0]["message"]
    assert not any(r["code"] == "R8" for r in risks)  # không có Maps thì không báo chưa định vị
    assert trip.evaluation["estimated"] is True
    options = list(db.scalars(select(TripOption).where(TripOption.trip_id == trip.id)))
    assert options and all(o.total_km and o.total_km > 0 for o in options)
    assert not no_maps


def test_think_mode_uses_web_hours_and_ferry_from_ai(db, user, trip, fake_ai):
    risks = _evaluate(db, user, trip, mode="think")
    assert fake_ai["estimate"][-1]["web"] is True
    assert any(r["code"] == "R2" and "Chùa Hang" in r["message"] and r["level"] == "red" for r in risks)
    from app.modules.trip.models import TripFact

    web_fact = db.scalar(select(TripFact).where(TripFact.text.like("Phà Bình Khánh chuyến cuối%")))
    assert web_fact is not None and web_fact.value_time.hour == 16 and "example.test/pha" in web_fact.text
    assert any(
        r["code"] == "R3" and r["stop_id"] == web_fact.stop_id and "16:00" in r["message"] for r in risks
    )
    db.refresh(trip)
    assert any("Không tìm được giờ mở cửa" in a for a in trip.evaluation["advice"])


def test_ferry_wait_is_not_counted_as_riding(db, user, trip, fake_ai):
    _evaluate(db, user, trip)
    payload = fake_ai["estimate"][0]
    assert payload["stops"][0]["visit_date"] == "2026-11-21"
    assert all(set(p) == {"from_stop_id", "to_stop_id"} for p in payload["legs"])
    assert {
        "stop_id",
        "day_no",
        "title",
        "category",
        "address",
        "place_query",
        "lat",
        "lng",
        "planned_time",
        "visit_date",
    } == set(payload["stops"][0])


def test_without_any_estimate_still_reads_hours_from_file(db, user, trip, monkeypatch):
    from app.modules.trip import bridge

    monkeypatch.setattr(bridge, "estimate_legs", lambda *a, **k: None)
    risks = _evaluate(db, user, trip)
    assert trip.status == "draft"
    assert any(r["code"] == "R2" and "thứ Hai" in r["message"] for r in risks)


def test_export_docx_without_maps(db, user, trip, stored_files):
    result = service.export_docx(db, user, trip.id)
    doc = read_docx(stored_files[result["file_id"]])
    assert doc.tables == 3 and any("two-wheeler" in u for u in doc.links)


def test_hours_from_text_forms():
    maybe = hours_from_text("Bảo tàng Văn hóa Khmer có thể đóng cửa thứ 2.")
    assert maybe["maybe"] is True and all(p["open"]["day"] != 1 for p in maybe["regular"]["periods"])
    sure = hours_from_text("Nghỉ thứ hai và chủ nhật; mở cửa 7h30 - 17h")
    days = {p["open"]["day"] for p in sure["regular"]["periods"]}
    assert 1 not in days and 0 not in days and sure["maybe"] is False
    first = sure["regular"]["periods"][0]
    assert first["open"]["hour"] == 7 and first["open"]["minute"] == 30 and first["close"]["hour"] == 17
    assert hours_from_text("Ăn sáng hủ tiếu") is None


def test_repeated_think_does_not_duplicate_ferry_fact(db, user, trip, fake_ai):
    from app.core.models import JobQueue
    from app.modules.trip.models import TripFact

    _evaluate(db, user, trip, mode="think")
    db.execute(JobQueue.__table__.delete())
    _evaluate(db, user, trip, mode="think")
    count = len(list(db.scalars(select(TripFact).where(TripFact.text.like("Phà Bình Khánh chuyến cuối%")))))
    assert count == 1


def test_export_docx_save_to_drive_queues_upload(db, user, trip, stored_files, monkeypatch):
    from app.modules.trip import bridge

    asked = []
    monkeypatch.setattr(bridge, "request_drive_upload", lambda s, uid, fid: asked.append((uid, fid)) or True)
    result = service.export_docx(db, user, trip.id, save_to_drive=True)
    assert result["drive_queued"] is True and asked == [(user.user_id, result["file_id"])]


def test_export_docx_drive_not_connected_still_exports(db, user, trip, stored_files):
    result = service.export_docx(db, user, trip.id, save_to_drive=True)
    assert result["drive_queued"] is False and result["file_id"] in stored_files


# ---------- Dựng chuyến từ câu mô tả khi không có khóa Maps ----------


def test_find_place_without_key_returns_search_link(db, user, no_maps):
    [item] = service.find_place(db, user, "Bãi Sau", "Vũng Tàu")
    assert item["place_id"] is None and item["verified"] is False and item["address"] == "Vũng Tàu"
    link = parse_maps_url(item["link"])
    assert link.kind == "search" and link.query == "Bãi Sau Vũng Tàu" and link.place_id is None
    assert not no_maps


def test_resolve_candidates_without_key_keeps_name(db, user, trip, no_maps):
    stop = _stops(db, trip.id)[0]
    out = service.resolve_candidates(db, user, trip.id, stop.id, "Chợ Bến Thành")
    [c] = out["candidates"]
    assert c["place_id"] is None and "Ch%E1%BB%A3+B%E1%BA%BFn+Th%C3%A0nh" in c["link"]
    assert stop.place_query == "Chợ Bến Thành" and not no_maps


def test_trip_from_description_without_key(db, user, no_maps, fake_ai, monkeypatch):
    from app.modules.trip import bridge
    from app.modules.trip.schemas import TripExtract

    found = {q: service.find_place(db, user, q, "Vũng Tàu")[0] for q in ("Bãi Sau", "Hải đăng Vũng Tàu")}
    text = (
        "Đi Vũng Tàu 2 ngày, xuất phát từ TP.HCM.\n"
        f"Ngày 1: 9h00 tắm biển [Bãi Sau]({found['Bãi Sau']['link']}).\n"
        f"Ngày 2: 7h00 lên [Hải đăng Vũng Tàu]({found['Hải đăng Vũng Tàu']['link']})."
    )

    def extract(user_id, content, output_model, hint=None):
        assert content == text
        days = [
            {"day_no": i + 1, "stops": [{"time_text": t, "title": title, "category": "tham_quan",
             "places": [{"label": q, "url": found[q]["link"]}]}]}
            for i, (t, title, q) in enumerate(
                [("9h00", "Tắm biển Bãi Sau", "Bãi Sau"), ("7h00", "Lên hải đăng", "Hải đăng Vũng Tàu")]
            )
        ]  # fmt: skip
        return TripExtract.model_validate({"title": "Vũng Tàu 2 ngày", "origin_text": "TP.HCM", "days": days})

    monkeypatch.setattr(bridge, "extract_trip", extract)
    data = service.import_trip(db, user, text=text, start_date=date(2026, 11, 28))
    run_job(db, "trip_import", data["trip_id"])
    trip = db.get(Trip, data["trip_id"])
    assert trip.status == "draft", trip.error
    stops = [s for s in _stops(db, trip.id) if s.source_url]
    assert [s.place_query for s in stops] == ["Bãi Sau Vũng Tàu", "Hải đăng Vũng Tàu Vũng Tàu"]
    assert all(s.place_id is None and s.lat is None for s in stops)

    _evaluate(db, user, trip)
    assert fake_ai["estimate"], "chặng phải qua estimate_legs"
    assert db.scalars(select(TripOption).where(TripOption.trip_id == trip.id)).first() is not None
    assert not no_maps


def test_run_job_now_imports_and_evaluates_in_same_transaction(db, user, no_maps, fake_ai, sample_file):
    from app.core.errors import NotFoundError
    from app.core.models import JobQueue

    data = service.import_trip(db, user, file_id=sample_file, start_date=date(2026, 11, 21))
    service.run_job_now(db, user, data["job_id"])
    trip = db.get(Trip, data["trip_id"])
    assert trip.status == "draft" and db.get(JobQueue, data["job_id"]).status == "done"
    with pytest.raises(NotFoundError):  # đã xong thì không chạy lại
        service.run_job_now(db, user, data["job_id"])

    out = service.evaluate_trip(db, user, trip.id)
    service.run_job_now(db, user, out["job_id"])
    db.refresh(trip)
    assert trip.evaluation["risks"] is not None and db.get(JobQueue, out["job_id"]).status == "done"


def test_run_job_now_refuses_other_users_job(db, user, no_maps, fake_ai, sample_file):
    from app.core.context import UserContext
    from app.core.errors import NotFoundError

    other_user = UserContext(user_id=user.user_id + 100000, timezone=user.timezone)

    data = service.import_trip(db, user, file_id=sample_file)
    with pytest.raises(NotFoundError):
        service.run_job_now(db, other_user, data["job_id"])
