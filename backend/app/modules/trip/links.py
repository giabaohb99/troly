"""Link Google Maps dựng ở máy chủ, app chỉ mở (41 mục 7, 12 mục 5.7). Không cần khóa, không tính tiền.

Chia đoạn: cắt ở điểm nghỉ dài (khách sạn, ở lại từ 90 phút), mỗi đoạn tối đa max_waypoints điểm dừng,
điểm cuối đoạn trước là điểm đầu đoạn sau, link tối đa 2.048 ký tự; có tọa độ thì dùng tọa độ cho link ngắn,
không có thì dùng tên kèm địa chỉ (QĐ-36: V1 không có Maps Platform, app Google Maps tự tìm theo tên).
"""

import unicodedata
from dataclasses import dataclass
from urllib.parse import quote, urlencode


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFD", value.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


MAPS_DIR = "https://www.google.com/maps/dir/"
MAPS_SEARCH = "https://www.google.com/maps/search/"
MAX_URL = 2048
LONG_REST_MINUTES = 90


@dataclass
class LinkStop:
    id: int
    title: str
    category: str
    stay_minutes: int
    lat: float | None
    lng: float | None
    place_query: str | None
    place_id: str | None
    area: str | None = None  # xã/phường, tỉnh: không có thì Google chọn chỗ trùng tên gần người dùng

    @property
    def located(self) -> bool:
        return self.lat is not None and self.lng is not None

    @property
    def query(self) -> str:
        """Chuỗi tìm khi không có tọa độ: `<tên>, <địa phương>`."""
        name = (self.place_query or self.title or "").strip()
        area = (self.area or "").strip()
        if not area or _fold(area) in _fold(name):
            return name
        return f"{name}, {area}" if name else area

    @property
    def routable(self) -> bool:
        return self.located or bool(self.query)


def _coord(s: LinkStop) -> str:
    """Điểm trong link: tọa độ nếu có, không thì chuỗi tìm theo tên."""
    if s.located:
        return f"{float(s.lat):.6f},{float(s.lng):.6f}"
    return s.query


def directions_url(points: list[LinkStop], navigate: bool = False) -> str:
    params = {
        "api": "1",
        "origin": _coord(points[0]),
        "destination": _coord(points[-1]),
        "travelmode": "two-wheeler",
        "avoid": "highways",
    }
    if len(points) > 2:
        params["waypoints"] = "|".join(_coord(p) for p in points[1:-1])
    if navigate:
        params["dir_action"] = "navigate"
    return MAPS_DIR + "?" + urlencode(params, quote_via=quote, safe=",|")


def navigate_url(s: LinkStop) -> str:
    """Dự phòng khi máy không có app Google Maps: dẫn đường từ vị trí hiện tại."""
    params = {
        "api": "1",
        "destination": _coord(s),
        "travelmode": "two-wheeler",
        "avoid": "highways",
        "dir_action": "navigate",
    }
    return MAPS_DIR + "?" + urlencode(params, quote_via=quote, safe=",")


def place_url(s: LinkStop) -> str:
    params = {"api": "1", "query": s.query}
    if s.place_id:
        params["query_place_id"] = s.place_id
    return MAPS_SEARCH + "?" + urlencode(params, quote_via=quote)


def _is_long_rest(s: LinkStop) -> bool:
    return s.category == "khach_san" or (s.stay_minutes or 0) >= LONG_REST_MINUTES


def split_segments(stops: list[LinkStop], max_waypoints: int = 9) -> list[list[LinkStop]]:
    points = [s for s in stops if s.routable]
    if len(points) < 2:
        return []
    groups: list[list[LinkStop]] = []
    current = [points[0]]
    for p in points[1:]:
        current.append(p)
        if _is_long_rest(p) and len(current) >= 2:
            groups.append(current)
            current = [p]
    if len(current) >= 2:
        groups.append(current)
    segments: list[list[LinkStop]] = []
    for group in groups:
        size = max_waypoints + 2
        start = 0
        while start < len(group) - 1:
            chunk = group[start : start + size]
            while len(chunk) > 2 and len(directions_url(chunk)) > MAX_URL:
                chunk = chunk[:-1]
            segments.append(chunk)
            start += len(chunk) - 1
    return segments


def _label(segment: list[LinkStop]) -> str:
    return f"{segment[0].title} → {segment[-1].title} ({len(segment)} điểm)"


def day_actions(day_no: int, stops: list[LinkStop], max_waypoints: int) -> dict:
    """Hành động phẳng theo 12: mỗi đoạn một open_map_directions; mỗi điểm navigation và place."""
    segments = split_segments(stops, max_waypoints)
    seg_actions = [
        {
            "id": f"d{day_no}s{i + 1}",
            "type": "open_map_directions",
            "label": _label(seg),
            "urls": [directions_url(seg)],
            "segment_labels": [f"Đoạn {i + 1}/{len(segments)}"],
        }
        for i, seg in enumerate(segments)
    ]
    out_stops = []
    for s in stops:
        nav = None
        if s.routable:
            nav = {
                "id": f"n{s.id}",
                "type": "open_map_navigation",
                "label": f"Dẫn đường tới {s.title}",
                "lat": float(s.lat) if s.located else None,
                "lng": float(s.lng) if s.located else None,
                "query": s.query,
                "mode": "l",
                "avoid": "h",
                "uri": navigation_target(s),
                "fallback_url": navigate_url(s),
            }
        out_stops.append(
            {
                "stop_id": s.id,
                "lat": float(s.lat) if s.lat is not None else None,
                "lng": float(s.lng) if s.lng is not None else None,
                "navigation": nav,
                "place": {
                    "id": f"p{s.id}",
                    "type": "open_map_place",
                    "label": "Xem điểm",
                    "query": s.query,
                    "place_id": s.place_id,
                },
            }
        )
    return {"day_no": day_no, "segments": seg_actions, "stops": out_stops}


def navigation_uri(lat: float, lng: float) -> str:
    """Lệnh Android app ghép (Maps.navigate): xe hai bánh, tránh cao tốc (41 mục 7)."""
    return f"google.navigation:q={lat},{lng}&mode=l&avoid=h"


def navigation_target(s: LinkStop) -> str:
    """google.navigation theo tọa độ nếu có, không thì theo tên kèm địa chỉ (QĐ-36)."""
    if s.located:
        return navigation_uri(float(s.lat), float(s.lng))
    return f"google.navigation:q={quote(s.query)}&mode=l&avoid=h"
