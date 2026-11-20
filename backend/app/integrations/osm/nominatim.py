"""OpenStreetMap Nominatim: lấy tọa độ miễn phí cho điểm dừng (QĐ-36 không có Maps Platform).

Theo chính sách dùng Nominatim công cộng (operations.osmfoundation.org/policies/nominatim):
tối đa 1 yêu cầu mỗi giây cho cả tiến trình, User-Agent riêng có tên app, nơi gọi lưu đệm kết quả và
không gọi lại cho điểm đã có tọa độ. Dữ liệu © OpenStreetMap contributors, ODbL.
"""

import logging
import threading
import time
from dataclasses import dataclass

import httpx

log = logging.getLogger("troly.osm")

SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "troly-tro-ly-ca-nhan/1.0 (+https://assistant.baohuynh.io.vn)"
MIN_INTERVAL = 1.0
TIMEOUT = 10.0

_lock = threading.Lock()
_last_call = 0.0
_transport: httpx.BaseTransport | None = None
_sleep = time.sleep


class NominatimUnavailable(Exception):
    """Lỗi mạng, hết hạn mức (429) hoặc lỗi máy chủ: nơi gọi bỏ qua, không làm hỏng chuyến."""


@dataclass
class Place:
    lat: float
    lng: float
    display_name: str
    state: str | None


def set_transport(transport: httpx.BaseTransport | None) -> None:
    """Bài kiểm thay Nominatim thật bằng MockTransport."""
    global _transport
    _transport = transport


def _wait_turn() -> None:
    global _last_call
    gap = MIN_INTERVAL - (time.monotonic() - _last_call)
    if gap > 0:
        _sleep(gap)
    _last_call = time.monotonic()


def search(query: str, limit: int = 5) -> list[Place]:
    """Tìm trong Việt Nam, tên tiếng Việt. Trả rỗng khi không có kết quả."""
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": "1",
        "countrycodes": "vn",
        "accept-language": "vi",
        "limit": str(limit),
    }
    with _lock:
        _wait_turn()
        try:
            with httpx.Client(transport=_transport, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as c:
                response = c.get(SEARCH_URL, params=params)
        except httpx.HTTPError as exc:
            raise NominatimUnavailable(type(exc).__name__) from exc
    if response.status_code != 200:
        log.warning("Nominatim trả lỗi", extra={"status": response.status_code})
        raise NominatimUnavailable(str(response.status_code))
    out = []
    for row in response.json() or []:
        try:
            address = row.get("address") or {}
            out.append(
                Place(
                    float(row["lat"]),
                    float(row["lon"]),
                    row.get("display_name") or "",
                    address.get("state") or address.get("province") or address.get("city"),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out
