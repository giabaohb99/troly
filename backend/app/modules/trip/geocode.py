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


# Danh mục địa danh nhỏ để nhận ra địa phương trong tên điểm và tuyến (miền Nam, nơi người dùng hay đi).
# Giữ tên tỉnh trước sáp nhập 2025 vì tài liệu của người dùng ghi vậy và Google Maps vẫn hiểu.
# Không đưa tên phường xã trùng ở nhiều tỉnh (ví dụ Phước Thới có ở Cần Thơ) vào đây.
PLACES = {
    "phước hải": "Phước Hải, Bà Rịa - Vũng Tàu",
    "long hải": "Long Hải, Bà Rịa - Vũng Tàu",
    "vũng tàu": "Vũng Tàu, Bà Rịa - Vũng Tàu",
    "bà rịa": "Bà Rịa, Bà Rịa - Vũng Tàu",
    "đất đỏ": "Đất Đỏ, Bà Rịa - Vũng Tàu",
    "hồ tràm": "Hồ Tràm, Bà Rịa - Vũng Tàu",
    "côn đảo": "Côn Đảo, Bà Rịa - Vũng Tàu",
    "nhơn trạch": "Nhơn Trạch, Đồng Nai",
    "biên hòa": "Biên Hòa, Đồng Nai",
    "cần giờ": "Cần Giờ, TP. Hồ Chí Minh",
    "bình chánh": "Bình Chánh, TP. Hồ Chí Minh",
    "sài gòn": "TP. Hồ Chí Minh",
    "hồ chí minh": "TP. Hồ Chí Minh",
    "tân an": "Tân An, Long An",
    "cần đước": "Cần Đước, Long An",
    "gò công": "Gò Công, Tiền Giang",
    "mỹ tho": "Mỹ Tho, Tiền Giang",
    "bến tre": "Bến Tre",
    "trà vinh": "Trà Vinh",
    "vĩnh long": "Vĩnh Long",
    "sa đéc": "Sa Đéc, Đồng Tháp",
    "cao lãnh": "Cao Lãnh, Đồng Tháp",
    "long xuyên": "Long Xuyên, An Giang",
    "châu đốc": "Châu Đốc, An Giang",
    "rạch giá": "Rạch Giá, Kiên Giang",
    "phú quốc": "Phú Quốc, Kiên Giang",
    "hà tiên": "Hà Tiên, Kiên Giang",
    "sóc trăng": "Sóc Trăng",
    "bạc liêu": "Bạc Liêu",
    "cà mau": "Cà Mau",
    "vị thanh": "Vị Thanh, Hậu Giang",
    "cần thơ": "Cần Thơ",
    "long an": "Long An",
    "tiền giang": "Tiền Giang",
    "đồng nai": "Đồng Nai",
    "đồng tháp": "Đồng Tháp",
    "an giang": "An Giang",
    "kiên giang": "Kiên Giang",
    "hậu giang": "Hậu Giang",
    "bình dương": "Bình Dương",
    "tây ninh": "Tây Ninh",
    "phan thiết": "Phan Thiết, Bình Thuận",
    "mũi né": "Mũi Né, Bình Thuận",
    "đà lạt": "Đà Lạt, Lâm Đồng",
    "nha trang": "Nha Trang, Khánh Hòa",
}
_PLACE_KEYS = sorted(((fold(k), v) for k, v in PLACES.items()), key=lambda kv: -len(kv[0]))
_CROSSING = re.compile(r"\b(ph[àa]|đ[òo]|qua s[ôo]ng)\b", re.IGNORECASE)


def _clean(segment: str) -> str:
    segment = re.sub(r"(?i)^\s*đường đi\s*:\s*", "", segment)
    return re.sub(r"\(.*?\)", "", segment).strip(" .;,:")


def route_ends(route_text: str | None) -> tuple[str | None, str | None]:
    """(đầu tuyến, cuối tuyến) từ *Cần Thơ → Phước Hải* hoặc dòng *Đường đi: QL1A → ... → Phước Hải (250 km)*."""
    parts = [_clean(p) for p in _ARROW.split(route_text or "")]
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return None, None
    return parts[0], parts[-1]


def known_place(text: str | None) -> str | None:
    """Địa danh trong danh mục có trong chuỗi (*Long Hải Channel Beach Resort* -> Long Hải, Bà Rịa - Vũng Tàu)."""
    key = f" {fold(text or '')} "
    for name, area in _PLACE_KEYS:
        if f" {name} " in key or f" {name}," in key or f"({name}" in key:
            return area
    return None


def with_province(place: str | None) -> str | None:
    """*Phước Hải* -> *Phước Hải, Bà Rịa - Vũng Tàu* khi có trong danh mục; đã có tỉnh thì giữ."""
    if not place:
        return None
    if "," in place:
        return place
    return known_place(place) or place


def _day_ends(day: dict) -> tuple[str | None, str | None]:
    """Tiêu đề ngày (*Cần Thơ → Phước Hải*) trước; không có thì dòng Đường đi."""
    start, end = route_ends(day.get("title"))
    if not end:
        start, end = route_ends(day.get("route_text"))
    return with_province(start), with_province(end)


def trip_area(trip: Trip) -> str | None:
    """Nơi đến của ngày đầu có tuyến. Không lùi về end_text: chuyến khứ hồi thì end_text là nhà."""
    days = (trip.extract_json or {}).get("days") or []
    for d in sorted(days, key=lambda d: d.get("day_no") or 0):
        _, end = _day_ends(d)
        if end:
            return end
    return None


def _is_crossing(s: TripStop) -> bool:
    return (
        s.category == "pha"
        or bool(_CROSSING.search(s.title or ""))
        or bool(_CROSSING.search(s.place_query or ""))
    )


def infer_areas(trip: Trip, stops: list[TripStop]) -> dict[int, str]:
    """Địa phương theo luật cho từng điểm: tên có địa danh thì lấy địa danh; trong ngày tuyến A -> B, từ điểm
    phà hoặc qua sông đầu tiên, hoặc từ điểm có tên chứa B, trở đi là B; trước đó là A."""
    days = {d.get("day_no"): d for d in (trip.extract_json or {}).get("days") or []}
    fallback = trip_area(trip)
    out: dict[int, str] = {}
    for day_no in sorted({s.day_no for s in stops}):
        day = sorted((s for s in stops if s.day_no == day_no), key=lambda s: s.seq)
        info = days.get(day_no, {})
        start, end = _day_ends(info)
        end = end or with_province(info.get("area")) or fallback
        start = start or end
        end_key = fold((end or "").split(",")[0])
        arrived = False
        for s in day:
            name = " ".join(x for x in (s.title, s.place_query) if x)
            if _is_crossing(s) or (end_key and end_key in fold(name)):
                arrived = True
            area = known_place(name) or (end if arrived else start)
            if area:
                out[s.id] = area[:200]
    return out


def fill_areas(trip: Trip, stops: list[TripStop], overwrite: bool = False) -> int:
    """Điền `area` cho điểm chưa có (AI đã trả thì giữ). overwrite: làm lại cho chuyến cũ (suy sai trước đây).
    Đổi địa phương thì bỏ tọa độ OpenStreetMap cũ để tìm lại. Trả số điểm đã đổi."""
    areas = infer_areas(trip, stops)
    changed = 0
    for s in stops:
        area = areas.get(s.id)
        if not area or (s.area and not overwrite) or s.area == area:
            continue
        s.area = area
        if s.coord_source == "osm":
            s.lat = s.lng = s.coord_source = s.coord_fetched_at = None
        changed += 1
    return changed


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


# ---------- Chuyến cũ: suy lại địa phương ----------


def _infer_stop_areas():
    """app.ai.trip_area.infer_stop_areas của agent AI (Haiku, mỗi ngày một lần); chưa có thì None."""
    import importlib

    try:
        return importlib.import_module("app.ai.trip_area").infer_stop_areas
    except (ModuleNotFoundError, AttributeError):
        return None


def _ai_areas(trip: Trip, stops: list[TripStop]) -> dict[int, str]:
    """Nhờ AI suy địa phương từng điểm theo tuyến của ngày. Chưa có hàm, AI lỗi hoặc từ chối thì trả rỗng,
    giữ kết quả theo luật."""
    infer = _infer_stop_areas()
    if infer is None:
        return {}
    days = {d.get("day_no"): d for d in (trip.extract_json or {}).get("days") or []}
    out: dict[int, str] = {}
    for day_no in sorted({s.day_no for s in stops}):
        info = days.get(day_no, {})
        payload = [
            {"stop_id": s.id, "title": s.title, "place_query": s.place_query, "category": s.category}
            for s in sorted((x for x in stops if x.day_no == day_no), key=lambda x: x.seq)
        ]
        day = {"day_no": day_no, "title": info.get("title"), "route_text": info.get("route_text")}
        try:
            got = infer(trip.user_id, trip.title, day, payload)
        except Exception:
            log.warning("AI suy địa phương lỗi", extra={"trip_id": trip.id, "day_no": day_no})
            continue
        out.update({int(k): v.strip()[:200] for k, v in (got or {}).items() if v and v.strip()})
    return out


def reinfer_trip(session: Session, trip: Trip, use_ai: bool = True) -> dict:
    """Chuyến nhập trước khi có `area` hoặc suy sai: làm lại địa phương (luật, rồi AI nếu có), bỏ tọa độ
    OpenStreetMap của điểm đổi địa phương, rồi lấy tọa độ lại. Trả `{changed, ai, ...geocode}`."""
    stops = list(
        session.scalars(
            select(TripStop).where(TripStop.trip_id == trip.id).order_by(TripStop.day_no, TripStop.seq)
        )
    )
    changed = fill_areas(trip, stops, overwrite=True)
    ai = _ai_areas(trip, stops) if use_ai else {}
    for s in stops:
        area = ai.get(s.id)
        if area and area != s.area:
            s.area = area
            if s.coord_source == "osm":
                s.lat = s.lng = s.coord_source = s.coord_fetched_at = None
            changed += 1
    session.flush()
    return {"changed": changed, "ai": len(ai), **geocode_trip(session, trip)}
