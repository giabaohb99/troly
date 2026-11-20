"""Địa phương và tọa độ của điểm dừng khi không có Maps Platform (QĐ-36).

Lỗi thật 20/11: đứng ở Cần Thơ bấm Dẫn đường tới quán ở Phước Hải, Google Maps chọn quán trùng tên ở
Cần Thơ vì chuỗi tìm chỉ có tên. Nên:

1. Mỗi điểm có `area` (xã/phường, tỉnh): AI bóc tách trả; không có thì lấy khu vực của ngày từ dòng
   *Đường đi* (có phà: điểm trước phà thuộc đầu tuyến, từ phà trở đi thuộc cuối tuyến; không phà thì cuối
   tuyến); không có nữa thì điểm đến của chuyến (cuối tuyến ngày 1, rồi end_text).
2. Tọa độ lấy từ OpenStreetMap Nominatim (`<tên>, <địa phương>`), chỉ nhận kết quả cách tâm địa phương
   dưới 50 km (không tìm được tâm thì tên tỉnh phải có trong địa chỉ). Lưu đệm ở tab_place_cache
   (bias_key `osm`), không gọi lại cho điểm đã có tọa độ, lỗi mạng thì dừng lượt, không hỏng chuyến.
"""

import logging
import re
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core import clock
from app.integrations.osm import nominatim
from app.modules.trip import places
from app.modules.trip.models import PlaceCache, Trip, TripStop
from app.modules.trip.normalize import fold

log = logging.getLogger("troly.trip")

ROUTED_ROLES = ("main", "via")
MAX_KM = 50.0
CACHE_KEY = "osm"
NEGATIVE_TTL = timedelta(days=30)
_ARROW = re.compile(r"\s*(?:→|->|–>|=>|⇒)\s*")


# ---------- Địa phương ----------


def route_ends(route_text: str | None) -> tuple[str | None, str | None]:
    """(đầu tuyến, cuối tuyến) từ dòng Đường đi, ví dụ *Cần Thơ → phà Cát Lái → Phước Hải*."""
    parts = [p.strip(" .;") for p in _ARROW.split(route_text or "") if p.strip(" .;")]
    if len(parts) < 2:
        return None, None
    return parts[0], parts[-1]


def trip_area(trip: Trip) -> str | None:
    days = (trip.extract_json or {}).get("days") or []
    for d in sorted(days, key=lambda d: d.get("day_no") or 0):
        _, end = route_ends(d.get("route_text"))
        if end:
            return end
    return trip.end_text or None


def fill_areas(trip: Trip, stops: list[TripStop]) -> int:
    """Điền `area` cho điểm chưa có (AI đã trả thì giữ). Trả số điểm vừa điền."""
    routes = {
        d.get("day_no"): route_ends(d.get("route_text")) for d in (trip.extract_json or {}).get("days") or []
    }
    fallback = trip_area(trip)
    day_areas = {d.get("day_no"): d.get("area") for d in (trip.extract_json or {}).get("days") or []}
    filled = 0
    for day_no in sorted({s.day_no for s in stops}):
        day = sorted((s for s in stops if s.day_no == day_no), key=lambda s: s.seq)
        start, end = routes.get(day_no, (None, None))
        ferry_seen = not any(s.category == "pha" for s in day)  # không phà: cả ngày thuộc cuối tuyến
        for s in day:
            if s.category == "pha":
                ferry_seen = True
            if s.area:
                continue
            area = (end if ferry_seen else start) or end or day_areas.get(day_no) or fallback
            if area:
                s.area = area[:200]
                filled += 1
    return filled


def search_text(name: str | None, area: str | None) -> str:
    """`<tên>, <địa phương>`; tên đã chứa địa phương thì không lặp."""
    name = (name or "").strip()
    area = (area or "").strip()
    if not area or fold(area) in fold(name):
        return name
    return f"{name}, {area}" if name else area


# ---------- Tọa độ ----------


def _cache_get(session: Session, text: str) -> PlaceCache | None:
    """Đệm còn dùng: có tọa độ thì giữ mãi (ODbL cho phép); không thấy thì hỏi lại sau 30 ngày."""
    row = session.get(PlaceCache, (fold(text), CACHE_KEY))
    if (
        row is not None
        and row.lat is None
        and (row.fetched_at is None or clock.now() - row.fetched_at > NEGATIVE_TTL)
    ):
        return None
    return row


def _cache_put(session: Session, text: str, place: nominatim.Place | None) -> None:
    values = {
        "query_norm": fold(text),
        "bias_key": CACHE_KEY,
        "place_id": None,
        "lat": place.lat if place else None,
        "lng": place.lng if place else None,
        "formatted_address": place.display_name[:500] if place else None,
        "fetched_at": clock.now(),
    }
    session.execute(
        insert(PlaceCache)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["query_norm", "bias_key"],
            set_={k: v for k, v in values.items() if k not in ("query_norm", "bias_key")},
        )
    )


def _lookup(session: Session, text: str) -> list[nominatim.Place]:
    """Một lần tìm có lưu đệm (cả khi không thấy, để không hỏi lại)."""
    row = _cache_get(session, text)
    if row is not None:
        if row.lat is None:
            return []
        return [nominatim.Place(float(row.lat), float(row.lng), row.formatted_address or "", None)]
    found = nominatim.search(text)
    _cache_put(session, text, found[0] if found else None)
    return found


def _area_center(session: Session, area: str, centers: dict) -> tuple[float, float] | None:
    if area not in centers:
        found = _lookup(session, area)
        centers[area] = (found[0].lat, found[0].lng) if found else None
    return centers[area]


def _province(area: str) -> str:
    return fold(area.split(",")[-1])


def _accept(place: nominatim.Place, area: str, center: tuple[float, float] | None) -> bool:
    if center is not None:
        return places.distance_km((place.lat, place.lng), center) <= MAX_KM
    province = _province(area)
    return bool(province) and province in fold(place.display_name)


def locate(session: Session, name: str, area: str, centers: dict | None = None) -> nominatim.Place | None:
    """Điểm khớp đầu tiên nằm đúng địa phương; trùng tên ở tỉnh khác thì bỏ."""
    centers = {} if centers is None else centers
    text = search_text(name, area)
    row = _cache_get(session, text)
    if row is not None:
        if row.lat is None:
            return None
        cached = nominatim.Place(float(row.lat), float(row.lng), row.formatted_address or "", None)
        return cached if _accept(cached, area, _area_center(session, area, centers)) else None
    found = nominatim.search(text)
    center = _area_center(session, area, centers)
    hit = next((p for p in found if _accept(p, area, center)), None)
    _cache_put(session, text, hit)
    return hit


def geocode_trip(session: Session, trip: Trip) -> dict:
    """Lấy tọa độ cho điểm chưa có. Trả `{found, missed, skipped, error}`; lỗi mạng thì dừng lượt."""
    stops = list(
        session.scalars(
            select(TripStop).where(TripStop.trip_id == trip.id).order_by(TripStop.day_no, TripStop.seq)
        )
    )
    fill_areas(trip, stops)
    result = {"found": 0, "missed": 0, "skipped": 0, "error": None}
    centers: dict = {}
    for s in stops:
        name = s.place_query or s.title
        if s.lat is not None or s.role not in ROUTED_ROLES or not name:
            continue
        if not s.area:
            result["skipped"] += 1  # không biết địa phương thì không đoán, tránh trùng tên tỉnh khác
            continue
        try:
            hit = locate(session, name, s.area, centers)
        except nominatim.NominatimUnavailable as exc:
            log.info("Nominatim không dùng được, dừng lượt lấy tọa độ", extra={"trip_id": trip.id})
            result["error"] = str(exc)[:100]
            break
        if hit is None:
            result["missed"] += 1
            continue
        s.lat, s.lng = round(hit.lat, 6), round(hit.lng, 6)
        s.coord_source, s.coord_fetched_at = "osm", clock.now()
        if s.resolve_status in ("uncertain", "not_found"):
            s.resolve_status = "ok"
        result["found"] += 1
    session.flush()
    return result
