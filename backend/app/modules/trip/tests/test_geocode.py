"""Lỗi thật 20/11: đứng ở Cần Thơ bấm Dẫn đường tới quán ở Phước Hải, Google Maps ra quán trùng tên ở
Cần Thơ. Sửa: chuỗi tìm luôn kèm địa phương; tọa độ lấy từ OpenStreetMap, chỉ nhận đúng vùng."""

from datetime import date
from urllib.parse import unquote

import httpx
import pytest
from sqlalchemy import select

from app.core.models import JobQueue
from app.integrations.osm import nominatim
from app.modules.trip import geocode, links, service
from app.modules.trip.models import PlaceCache, Trip, TripStop
from app.modules.trip.normalize import fold
from app.modules.trip.tests.conftest import run_job

PH = "Phước Hải, Bà Rịa - Vũng Tàu"
CT = "Cần Thơ"
CAN_THO = {"lat": "10.0340", "lon": "105.7880", "display_name": "Cafe Mộc, Ninh Kiều, Cần Thơ, Việt Nam",
           "address": {"state": "Cần Thơ"}}  # fmt: skip
PHUOC_HAI = {"lat": "10.4231", "lon": "107.2611", "display_name": "Cafe Mộc, Phước Hải, Đất Đỏ, Việt Nam",
             "address": {"state": "Bà Rịa - Vũng Tàu"}}  # fmt: skip
GAZ = {
    fold(f"Cafe Mộc, {PH}"): [CAN_THO, PHUOC_HAI],  # Nominatim có thể trả quán trùng tên trước
    fold(f"Quán Ốc Chị Bảy, {PH}"): [CAN_THO],  # chỉ có quán trùng tên ở tỉnh khác
    fold(PH): [{"lat": "10.4100", "lon": "107.2700", "display_name": "Phước Hải, Việt Nam", "address": {}}],
    fold(CT): [{"lat": "10.0452", "lon": "105.7469", "display_name": "Cần Thơ, Việt Nam", "address": {}}],
    fold(f"Bến Ninh Kiều, {CT}"): [
        {"lat": "10.0333", "lon": "105.7880", "display_name": "Bến Ninh Kiều, Cần Thơ"}
    ],
}


@pytest.fixture
def osm(monkeypatch):
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=GAZ.get(fold(request.url.params["q"]), []))

    sleeps: list[float] = []
    monkeypatch.setattr(nominatim, "_sleep", sleeps.append)
    monkeypatch.setattr(nominatim, "_last_call", 0.0)
    nominatim.set_transport(httpx.MockTransport(handle))
    yield calls, sleeps
    nominatim.set_transport(None)


def _trip(db, user, stops, route="Cần Thơ → phà Cát Lái → Phước Hải, Bà Rịa - Vũng Tàu"):
    trip = Trip(
        user_id=user.user_id,
        title="Phước Hải",
        status="draft",
        start_date=date(2026, 11, 21),
        end_date=date(2026, 11, 21),
        extract_json={"days": [{"day_no": 1, "route_text": route}]},
    )
    db.add(trip)
    db.flush()
    for seq, (title, category, extra) in enumerate(stops, 1):
        db.add(TripStop(user_id=user.user_id, trip_id=trip.id, day_no=1, seq=seq, title=title,
                        category=category, place_query=title, **extra))  # fmt: skip
    db.flush()
    return trip


def _stops(db, trip):
    return list(db.scalars(select(TripStop).where(TripStop.trip_id == trip.id).order_by(TripStop.seq)))


def test_area_from_route_before_and_after_ferry(db, user):
    trip = _trip(
        db,
        user,
        [
            ("Bến Ninh Kiều", "tham_quan", {}),
            ("Phà Cát Lái", "pha", {}),
            ("Cafe Mộc", "an_uong", {}),
            ("Chợ đêm", "an_uong", {"area": "Long Hải, Bà Rịa - Vũng Tàu"}),  # AI đã trả thì giữ
        ],
    )
    stops = _stops(db, trip)
    assert geocode.fill_areas(trip, stops) == 3
    assert [s.area for s in stops] == [CT, PH, PH, "Long Hải, Bà Rịa - Vũng Tàu"]


def test_area_without_ferry_uses_route_end_then_trip_destination(db, user):
    trip = _trip(db, user, [("Cafe Mộc", "an_uong", {})], route=f"Vũng Tàu → {PH}")
    stops = _stops(db, trip)
    geocode.fill_areas(trip, stops)
    assert stops[0].area == PH
    trip2 = _trip(db, user, [("Cafe Mộc", "an_uong", {})], route=None)
    trip2.end_text = "Phước Hải"
    stops2 = _stops(db, trip2)
    geocode.fill_areas(trip2, stops2)
    assert stops2[0].area == "Phước Hải"


def test_links_search_by_name_with_area():
    s = links.LinkStop(1, "Cafe Mộc", "an_uong", 0, None, None, "Cafe Mộc", None, PH)
    assert s.query == f"Cafe Mộc, {PH}"
    assert unquote(links.navigation_target(s)).startswith(f"google.navigation:q=Cafe Mộc, {PH}")
    assert PH in unquote(links.place_url(s)) and PH in unquote(links.directions_url([s, s]))
    same = links.LinkStop(2, "x", "khac", 0, None, None, "Chợ Phước Hải, Bà Rịa - Vũng Tàu", None, PH)
    assert same.query == "Chợ Phước Hải, Bà Rịa - Vũng Tàu"  # đã có địa phương thì không lặp
    located = links.LinkStop(3, "Cafe Mộc", "an_uong", 0, 10.4231, 107.2611, "Cafe Mộc", None, PH)
    assert links.navigation_target(located) == "google.navigation:q=10.4231,107.2611&mode=l&avoid=h"


def test_same_name_in_other_province_is_rejected(db, user, osm):
    calls, sleeps = osm
    trip = _trip(db, user, [("Phà Cát Lái", "pha", {}), ("Cafe Mộc", "an_uong", {}),
                            ("Quán Ốc Chị Bảy", "an_uong", {})])  # fmt: skip
    result = geocode.geocode_trip(db, trip)
    cafe, oc = _stops(db, trip)[1:]
    assert (float(cafe.lat), float(cafe.lng)) == (10.4231, 107.2611) and cafe.coord_source == "osm"
    assert oc.lat is None  # chỉ có quán trùng tên ở Cần Thơ: thà không có tọa độ, link vẫn kèm địa phương
    assert result["found"] == 1 and result["missed"] == 2  # phà và quán ốc
    assert all(r.headers["user-agent"] == nominatim.USER_AGENT for r in calls)
    assert all(r.url.params["countrycodes"] == "vn" for r in calls)
    assert len(sleeps) == len(calls) - 1  # tối đa 1 yêu cầu mỗi giây


def test_cache_and_located_stops_are_not_asked_again(db, user, osm):
    calls, _ = osm
    trip = _trip(db, user, [("Phà Cát Lái", "pha", {}), ("Cafe Mộc", "an_uong", {}),
                            ("Quán Ốc Chị Bảy", "an_uong", {})])  # fmt: skip
    geocode.geocode_trip(db, trip)
    first = len(calls)
    geocode.geocode_trip(db, trip)  # Cafe Mộc đã có tọa độ; Ốc Chị Bảy đã lưu đệm là không thấy
    assert len(calls) == first
    other = _trip(db, user, [("Phà Cát Lái", "pha", {}), ("Cafe Mộc", "an_uong", {})])
    geocode.geocode_trip(db, other)  # chuyến khác cùng quán: lấy từ đệm
    assert len(calls) == first and _stops(db, other)[1].lat is not None
    row = db.get(PlaceCache, (fold(f"Cafe Mộc, {PH}"), "osm"))
    assert row is not None and row.place_id is None


def test_network_error_does_not_break_trip(db, user):
    trip = _trip(db, user, [("Phà Cát Lái", "pha", {}), ("Cafe Mộc", "an_uong", {})])
    result = geocode.geocode_trip(db, trip)  # osm_offline: mọi lời gọi lỗi mạng
    assert result["error"] and result["found"] == 0
    assert _stops(db, trip)[1].area == PH and trip.status == "draft"


def test_center_unknown_falls_back_to_province_name(db, user, osm, monkeypatch):
    monkeypatch.setitem(GAZ, fold(PH), [])
    trip = _trip(db, user, [("Phà Cát Lái", "pha", {}), ("Cafe Mộc", "an_uong", {})])
    geocode.geocode_trip(db, trip)
    stop = _stops(db, trip)[1]
    assert stop.lat is None  # PHUOC_HAI ghi Đất Đỏ, không có tên tỉnh: không đủ chắc thì bỏ

    monkeypatch.setitem(
        GAZ, fold(f"Quán Ốc Chị Bảy, {PH}"), [{**PHUOC_HAI, "display_name": "Ốc, Bà Rịa - Vũng Tàu"}]
    )
    trip2 = _trip(db, user, [("Phà Cát Lái", "pha", {}), ("Quán Ốc Chị Bảy", "an_uong", {})])
    geocode.geocode_trip(db, trip2)
    assert _stops(db, trip2)[1].lat is not None


def test_import_queues_geocode_and_links_use_coords(db, user, no_maps, fake_ai, sample_file, osm):
    data = service.import_trip(db, user, file_id=sample_file, start_date=date(2026, 11, 21))
    run_job(db, "trip_import", data["trip_id"])
    job = db.scalar(select(JobQueue).where(JobQueue.kind == "trip_geocode"))
    assert job is not None and job.payload == {"trip_id": data["trip_id"]}
    trip = db.get(Trip, data["trip_id"])
    stops = [s for s in _stops(db, trip) if s.role in ("main", "via")]
    assert all(s.area for s in stops), [s.title for s in stops if not s.area]
    run_job(db, "trip_geocode", trip.id)  # Nominatim giả không biết các quán này: không đoán bừa
    assert all(s.coord_source != "osm" for s in _stops(db, trip))
    nav = next(
        s["navigation"]
        for d in service.map_links(db, user, trip.id, None, 9)["days"]
        for s in d["stops"]
        if s["navigation"] and s["lat"] is None
    )
    assert "," in nav["query"]  # tên kèm địa phương


def test_cli_geocode_one_trip(db, user, osm, monkeypatch, capsys):
    from app.modules.trip import cli

    trip = _trip(db, user, [("Phà Cát Lái", "pha", {}), ("Cafe Mộc", "an_uong", {})])

    class Session:
        def __enter__(self):
            return db

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(cli, "SessionLocal", Session)
    monkeypatch.setattr(db, "commit", db.flush)
    assert cli.main(["geocode", "--trip", str(trip.id)]) == 0
    assert '"found": 1' in capsys.readouterr().out


def test_editing_area_drops_osm_coords(db, user, osm):
    trip = _trip(db, user, [("Phà Cát Lái", "pha", {}), ("Cafe Mộc", "an_uong", {})])
    geocode.geocode_trip(db, trip)
    cafe = _stops(db, trip)[1]
    assert cafe.coord_source == "osm"
    out = service.update_stop(db, user, trip.id, cafe.id, {"area": "Long Hải, Bà Rịa - Vũng Tàu"})
    assert cafe.lat is None and out["search_query"] == "Cafe Mộc, Long Hải, Bà Rịa - Vũng Tàu"
