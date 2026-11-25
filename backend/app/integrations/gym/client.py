"""App gym (gym.baohuynh.io.vn) qua cửa chỉ đọc `/api/integration/summary` (QĐ-54). Trợ lý không ghi gì sang gym.

Khóa `GYM_API_KEY` gửi ở header `X-Integration-Key`, chỉ ở .env VPS và troly-secrets. Kết quả đệm 5 phút theo
(username, from, to). Thiếu env thì `GymNotConnected`; lỗi mạng hoặc gym trả lỗi thì `GymUnavailable`, nơi gọi
(thẻ báo cáo, công cụ AI của agent AI) hiện câu lỗi chứ không làm hỏng lượt.
"""

import logging
import threading
import time
from datetime import date

import httpx

from app.core.config import get_settings
from app.core.errors import AppError

log = logging.getLogger("troly.gym")

SUMMARY_PATH = "/api/integration/summary"
USER_AGENT = "troly-tro-ly-ca-nhan/1.0 (+https://assistant.baohuynh.io.vn)"
TIMEOUT = 10.0
CACHE_SECONDS = 300
MAX_DAYS = 92

_transport: httpx.BaseTransport | None = None
_cache_lock = threading.Lock()
_cache: dict[tuple, tuple[float, dict]] = {}


class GymNotConnected(AppError):
    status = 409
    code = "GYM_NOT_CONNECTED"
    message = "Chưa nối app gym."


class GymUnavailable(AppError):
    status = 502
    code = "GYM_UNAVAILABLE"
    message = "App gym đang không trả lời, thử lại sau."


def set_transport(transport: httpx.BaseTransport | None) -> None:
    """Bài kiểm thay gym thật bằng MockTransport; đổi transport thì xóa đệm."""
    global _transport
    _transport = transport
    clear_cache()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def is_configured() -> bool:
    s = get_settings()
    return bool(s.gym_base_url and s.gym_api_key and s.gym_username)


def fetch_summary(from_: date | None = None, to: date | None = None, username: str | None = None) -> dict:
    """`data` của gym: {username, range, workouts, planned, body, nutrition, progress, today}. Thiếu ngày thì gym
    tự lấy 7 ngày tới hôm nay (giờ Việt Nam). Khoảng quá 92 ngày thì ValidationError trước khi gọi."""
    from app.core.errors import ValidationError

    s = get_settings()
    if not is_configured():
        raise GymNotConnected()
    if from_ and to and (from_ > to or (to - from_).days + 1 > MAX_DAYS):
        raise ValidationError(fields={"from": f"Khoảng ngày từ 1 tới {MAX_DAYS} ngày, from trước to."})
    user = username or s.gym_username
    key = (user, from_, to)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    params = {"username": user}
    if from_:
        params["from"] = from_.isoformat()
    if to:
        params["to"] = to.isoformat()
    try:
        with httpx.Client(transport=_transport, timeout=TIMEOUT) as client:
            resp = client.get(
                s.gym_base_url.rstrip("/") + SUMMARY_PATH,
                params=params,
                headers={"X-Integration-Key": s.gym_api_key, "User-Agent": USER_AGENT},
            )
    except httpx.HTTPError as exc:
        log.warning("Gọi app gym lỗi mạng", extra={"error": type(exc).__name__})
        raise GymUnavailable() from exc
    if resp.status_code in (401, 404):
        # 401: khóa sai; 404: cửa tích hợp chưa bật hoặc không có tài khoản.
        log.warning("App gym từ chối", extra={"status": resp.status_code})
        raise GymNotConnected("App gym từ chối khóa hoặc chưa bật cửa tích hợp.")
    if resp.status_code != 200:
        log.warning("App gym trả lỗi", extra={"status": resp.status_code})
        raise GymUnavailable()
    try:
        data = resp.json()["data"]
    except (ValueError, KeyError, TypeError) as exc:
        raise GymUnavailable() from exc
    with _cache_lock:
        _cache[key] = (now, data)
    return data
