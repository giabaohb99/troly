"""Google Maps Platform gọi từ máy chủ (40 mục 9, 41 mục 4, 5).

Giá tính theo trường xin trong X-Goog-FieldMask, nên mỗi hàm xin đúng tầng SKU:
- text_search_ids: chỉ places.id (IDs Only, miễn phí);
- place_essentials: location, formattedAddress, types (Essentials);
- place_with_name: thêm displayName (Pro, cho find_place);
- opening_hours: giờ mở cửa (Enterprise, chỉ gọi lúc đánh giá);
- compute_route: TWO_WHEELER + avoidHighways (Enterprise), dự phòng DRIVE;
- route_matrix: DRIVE + avoidHighways (Essentials), để sắp thứ tự.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from app.core.errors import ExternalServiceError
from app.integrations.google import http
from app.integrations.google.errors import GoogleUnavailable
from app.integrations.google.settings import get_google_settings

log = logging.getLogger("troly.maps")

PLACES = "https://places.googleapis.com/v1"
ROUTES = "https://routes.googleapis.com"
GEOCODE = "https://maps.googleapis.com/maps/api/geocode/json"
RESOLVE = "https://mapstools.googleapis.com/v1:resolveMapsUrls"


class MapsUnavailable(ExternalServiceError):
    code = "MAPS_UNAVAILABLE"
    message = "Chưa tra được bản đồ (chưa có khóa Maps hoặc Google đang lỗi)."


@dataclass
class PlaceInfo:
    place_id: str
    lat: float | None = None
    lng: float | None = None
    address: str | None = None
    name: str | None = None
    types: list[str] = field(default_factory=list)
    business_status: str | None = None


@dataclass
class Leg:
    distance_m: int
    duration_s: int
    instructions: list[str] = field(default_factory=list)


@dataclass
class RouteResult:
    legs: list[Leg]
    travel_mode: str  # two_wheeler hoặc drive
    warnings: list[str] = field(default_factory=list)


def configured() -> bool:
    return bool(get_google_settings().google_maps_api_key)


def _headers(field_mask: str) -> dict:
    key = get_google_settings().google_maps_api_key
    if not key:
        raise MapsUnavailable()
    return {"X-Goog-Api-Key": key, "X-Goog-FieldMask": field_mask}


def _call(method: str, url: str, *, field_mask: str, **kwargs) -> dict | list:
    try:
        response = http.send(method, url, headers=_headers(field_mask), **kwargs)
    except GoogleUnavailable as exc:
        raise MapsUnavailable() from exc
    if response.status_code != 200:
        log.warning("Maps lỗi", extra={"status": response.status_code, "reason": http.error_reason(response)})
        raise MapsUnavailable()
    return response.json()


def _latlng(location: dict | None) -> tuple[float | None, float | None]:
    if not location:
        return None, None
    return location.get("latitude"), location.get("longitude")


def text_search_ids(query: str, bias: tuple[float, float] | None, page_size: int = 3) -> list[str]:
    body: dict = {"textQuery": query, "languageCode": "vi", "regionCode": "VN", "pageSize": page_size}
    if bias is not None:
        body["locationBias"] = {
            "circle": {"center": {"latitude": bias[0], "longitude": bias[1]}, "radius": 30000.0}
        }
    data = _call("POST", f"{PLACES}/places:searchText", field_mask="places.id", json=body)
    return [p["id"] for p in data.get("places", []) if p.get("id")]


def _details(place_id: str, fields: str) -> dict:
    return _call(
        "GET",
        f"{PLACES}/places/{place_id}",
        field_mask=fields,
        params={"languageCode": "vi", "regionCode": "VN"},
    )


def place_essentials(place_id: str) -> PlaceInfo:
    data = _details(place_id, "id,location,formattedAddress,types")
    lat, lng = _latlng(data.get("location"))
    return PlaceInfo(place_id, lat, lng, data.get("formattedAddress"), types=data.get("types", []))


def place_with_name(place_id: str) -> PlaceInfo:
    data = _details(place_id, "id,location,formattedAddress,types,displayName")
    lat, lng = _latlng(data.get("location"))
    name = (data.get("displayName") or {}).get("text")
    return PlaceInfo(place_id, lat, lng, data.get("formattedAddress"), name, data.get("types", []))


def opening_hours(place_id: str) -> dict:
    """Trả {regular, current, utc_offset_minutes, business_status}; không lưu lâu dài (41 mục 4)."""
    data = _details(place_id, "id,regularOpeningHours,currentOpeningHours,utcOffsetMinutes,businessStatus")
    return {
        "regular": data.get("regularOpeningHours"),
        "current": data.get("currentOpeningHours"),
        "utc_offset_minutes": data.get("utcOffsetMinutes"),
        "business_status": data.get("businessStatus"),
    }


def geocode(address: str) -> PlaceInfo | None:
    key = get_google_settings().google_maps_api_key
    if not key:
        raise MapsUnavailable()
    response = http.send(
        "GET", GEOCODE, params={"address": address, "language": "vi", "region": "vn", "key": key}
    )
    if response.status_code != 200:
        raise MapsUnavailable()
    results = response.json().get("results") or []
    if not results:
        return None
    top = results[0]
    loc = (top.get("geometry") or {}).get("location") or {}
    return PlaceInfo(top.get("place_id", ""), loc.get("lat"), loc.get("lng"), top.get("formatted_address"))


def resolve_short_links(urls: list[str]) -> dict[str, str]:
    """Link maps.app.goo.gl thành place_id qua Resolution API (giá 0); lỗi thì trả rỗng."""
    if not urls:
        return {}
    try:
        data = _call("POST", RESOLVE, field_mask="*", json={"urls": urls[:20]})
    except MapsUnavailable:
        return {}
    out: dict[str, str] = {}
    for item in data.get("results", data.get("resolvedUrls", [])) or []:
        url = item.get("url") or item.get("originalUrl")
        place = item.get("placeId") or (item.get("place") or {}).get("id")
        if url and place:
            out[url] = place
    return out


def _waypoint(point: tuple[float, float]) -> dict:
    return {"location": {"latLng": {"latitude": point[0], "longitude": point[1]}}}


def _seconds(value: str | None) -> int:
    return int(float((value or "0s").rstrip("s")))


def compute_route(points: list[tuple[float, float]], departure: datetime | None) -> RouteResult:
    """Một lời gọi cho một đoạn (tối đa 25 điểm giữa). Xe hai bánh trước, lỗi thì ô tô tránh cao tốc."""
    if len(points) < 2:
        return RouteResult([], "two_wheeler")
    mask = (
        "routes.legs.distanceMeters,routes.legs.duration,routes.legs.steps.navigationInstruction,"
        "routes.distanceMeters,routes.duration,routes.warnings"
    )
    for mode, label in (("TWO_WHEELER", "two_wheeler"), ("DRIVE", "drive")):
        body: dict = {
            "origin": _waypoint(points[0]),
            "destination": _waypoint(points[-1]),
            "intermediates": [_waypoint(p) for p in points[1:-1]],
            "travelMode": mode,
            "routingPreference": "TRAFFIC_UNAWARE",
            "routeModifiers": {"avoidHighways": True},
            "languageCode": "vi",
            "regionCode": "VN",
        }
        if departure is not None:
            body["departureTime"] = departure.isoformat().replace("+00:00", "Z")
        try:
            data = _call("POST", f"{ROUTES}/directions/v2:computeRoutes", field_mask=mask, json=body)
        except MapsUnavailable:
            if mode == "DRIVE":
                raise
            continue
        routes = data.get("routes") or []
        if not routes:
            if mode == "DRIVE":
                raise MapsUnavailable("Google không tìm được đường giữa các điểm.")
            continue
        legs = [
            Leg(
                leg.get("distanceMeters", 0),
                _seconds(leg.get("duration")),
                [
                    (s.get("navigationInstruction") or {}).get("instructions", "")
                    for s in leg.get("steps", [])
                    if s.get("navigationInstruction")
                ],
            )
            for leg in routes[0].get("legs", [])
        ]
        return RouteResult(legs, label, routes[0].get("warnings", []))
    raise MapsUnavailable()


def route_matrix(points: list[tuple[float, float]]) -> list[list[int | None]]:
    """Ma trận giây DRIVE + avoidHighways (SKU Essentials); tối đa 25 điểm (625 phần tử)."""
    n = len(points)
    body = {
        "origins": [{"waypoint": _waypoint(p), "routeModifiers": {"avoidHighways": True}} for p in points],
        "destinations": [{"waypoint": _waypoint(p)} for p in points],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_UNAWARE",
    }
    data = _call(
        "POST",
        f"{ROUTES}/distanceMatrix/v2:computeRouteMatrix",
        field_mask="originIndex,destinationIndex,duration,status,condition",
        json=body,
    )
    items = data if isinstance(data, list) else json.loads(data) if isinstance(data, str) else []
    matrix: list[list[int | None]] = [[None] * n for _ in range(n)]
    for item in items:
        if item.get("condition", "ROUTE_EXISTS") != "ROUTE_EXISTS":
            continue
        matrix[item["originIndex"]][item["destinationIndex"]] = _seconds(item.get("duration"))
    return matrix
