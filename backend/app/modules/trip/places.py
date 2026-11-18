"""Định vị điểm dừng và lưu đệm địa điểm (41 mục 4).

Thứ tự: tọa độ hoặc place_id trong link > tab_place_cache > Text Search chỉ places.id (giá 0) rồi
Place Details Essentials > Geocoding cho địa chỉ thuần. Tọa độ Google giữ tối đa 30 ngày; place_id giữ mãi.
"""

import math
import re
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core import clock
from app.integrations.google import maps
from app.modules.trip.models import PlaceCache
from app.modules.trip.normalize import fold

COORD_TTL = timedelta(days=30)
MAX_KM_FROM_PREVIOUS = 80
ADDRESS_RE = re.compile(r"\b\d+[a-z]?(/\d+)?\s+\D", re.I)
STOP_WORDS = {"pho", "quan", "tinh", "thanh", "phuong", "xa", "huyen", "cua", "o", "va", "the"}


@dataclass
class Resolved:
    place_id: str | None
    lat: float | None
    lng: float | None
    address: str | None
    status: str  # ok, uncertain, not_found
    candidates: list[dict]


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def bias_key(bias: tuple[float, float] | None) -> str:
    """Vùng tìm làm tròn 0,25 độ để lưu đệm dùng lại được giữa các chuyến gần nhau."""
    if bias is None:
        return "none"
    return f"{round(bias[0] * 4) / 4:.2f},{round(bias[1] * 4) / 4:.2f}"


def _fresh(row: PlaceCache) -> bool:
    return row.lat is not None and row.fetched_at is not None and clock.now() - row.fetched_at < COORD_TTL


def _cache_get(session: Session, query_norm: str, key: str) -> PlaceCache | None:
    return session.get(PlaceCache, (query_norm, key))


def _cache_put(session: Session, query_norm: str, key: str, info: maps.PlaceInfo | None) -> None:
    values = {
        "query_norm": query_norm,
        "bias_key": key,
        "place_id": info.place_id if info else None,
        "lat": info.lat if info else None,
        "lng": info.lng if info else None,
        "formatted_address": info.address if info else None,
        "fetched_at": clock.now(),
    }
    stmt = insert(PlaceCache).values(**values)
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=["query_norm", "bias_key"],
            set_={k: v for k, v in values.items() if k not in ("query_norm", "bias_key")},
        )
    )


def details_cached(session: Session, place_id: str) -> maps.PlaceInfo:
    """Place Details Essentials, dùng lại tọa độ còn hạn trong lưu đệm theo place_id."""
    row = session.scalar(
        select(PlaceCache)
        .where(PlaceCache.place_id == place_id)
        .order_by(PlaceCache.fetched_at.desc())
        .limit(1)
    )
    if row is not None and _fresh(row):
        return maps.PlaceInfo(place_id, float(row.lat), float(row.lng), row.formatted_address)
    info = maps.place_essentials(place_id)
    _cache_put(session, f"place_id:{place_id}", "none", info)
    return info


def _confident(query: str, info: maps.PlaceInfo, category: str, previous: tuple[float, float] | None) -> bool:
    if info.lat is None:
        return False
    if previous is not None and distance_km(previous, (info.lat, info.lng)) > MAX_KM_FROM_PREVIOUS:
        return False
    words = [w for w in fold(query).split() if len(w) > 2 and w not in STOP_WORDS]
    address = fold(info.address)
    hits = sum(1 for w in words if w in address)
    type_match = {
        "an_uong": {"restaurant", "food", "cafe", "meal_takeaway"},
        "khach_san": {"lodging", "hotel"},
        "tham_quan": {"tourist_attraction", "museum", "park", "place_of_worship"},
    }.get(category, set())
    return bool(type_match & set(info.types)) or (words and hits >= max(1, len(words) // 2))


def resolve(
    session: Session,
    query: str,
    category: str,
    previous: tuple[float, float] | None,
) -> Resolved:
    query_norm = fold(query)
    key = bias_key(previous)
    cached = _cache_get(session, query_norm, key)
    if cached is not None and cached.place_id:
        info = (
            maps.PlaceInfo(cached.place_id, float(cached.lat), float(cached.lng), cached.formatted_address)
            if _fresh(cached)
            else details_cached(session, cached.place_id)
        )
        return Resolved(info.place_id, info.lat, info.lng, info.address, "ok", [])
    ids = maps.text_search_ids(query, previous)
    if not ids and ADDRESS_RE.search(query):
        found = maps.geocode(query)
        if found and found.lat is not None:
            _cache_put(session, query_norm, key, found)
            return Resolved(found.place_id or None, found.lat, found.lng, found.address, "ok", [])
    if not ids:
        _cache_put(session, query_norm, key, None)
        return Resolved(None, None, None, None, "not_found", [])
    first = details_cached(session, ids[0])
    if _confident(query, first, category, previous):
        _cache_put(session, query_norm, key, first)
        return Resolved(first.place_id, first.lat, first.lng, first.address, "ok", [])
    infos = [first] + [details_cached(session, pid) for pid in ids[1:3]]
    return Resolved(None, None, None, None, "uncertain", [candidate(i) for i in infos])


def suggestions(session: Session, query: str, previous: tuple[float, float] | None) -> list[dict]:
    """3 gợi ý cho điểm generic (tên món kèm vùng); lưu place_id và nhãn, không lưu tọa độ (11)."""
    ids = maps.text_search_ids(query, previous)
    return [candidate(details_cached(session, pid)) for pid in ids[:3]]


def candidate(info: maps.PlaceInfo) -> dict:
    return {
        "place_id": info.place_id,
        "name": info.name or (info.address or "").split(",")[0],
        "address": info.address,
        "lat": info.lat,
        "lng": info.lng,
    }
