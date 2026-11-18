"""Gọi HTTP tới Google: thời hạn 10 giây, thử lại trong một lời gọi (10 mục 3.9, 40 mục 10).

429, 5xx, 403 rateLimitExceeded, hết giờ: chờ 2^n giây cộng ngẫu nhiên tối đa 1 giây, trần 64 giây,
tối đa 5 lần. Bài kiểm thay transport bằng Google giả (set_transport) và thay _sleep.
"""

import logging
import random
import time

import httpx

from app.integrations.google.errors import GoogleHttpError, GoogleUnavailable
from app.integrations.google.settings import get_google_settings

log = logging.getLogger("troly.google")

MAX_RETRIES = 5
RETRY_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "backendError"}

_transport: httpx.BaseTransport | None = None
_sleep = time.sleep


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


def error_reason(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    err = body.get("error")
    if isinstance(err, str):
        return err  # điểm token: {"error": "invalid_grant"}
    if isinstance(err, dict):
        items = err.get("errors") or []
        if items and isinstance(items[0], dict):
            return items[0].get("reason", "") or err.get("status", "")
        return err.get("status", "")
    return ""


def _should_retry(response: httpx.Response) -> bool:
    if response.status_code == 429 or response.status_code >= 500:
        return True
    return response.status_code == 403 and error_reason(response) in RETRY_REASONS


def send(method: str, url: str, **kwargs) -> httpx.Response:
    """Gửi một yêu cầu, tự thử lại lỗi tạm. Trả phản hồi cuối (kể cả 4xx) để nơi gọi xử lý."""
    timeout = get_google_settings().google_timeout_seconds
    attempt = 0
    while True:
        try:
            with httpx.Client(transport=_transport, timeout=timeout) as client:
                response = client.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            if attempt >= MAX_RETRIES:
                raise GoogleUnavailable() from exc
            response = None
        if response is not None and not _should_retry(response):
            return response
        if attempt >= MAX_RETRIES:
            if response is None:
                raise GoogleUnavailable()
            return response
        wait = min(2**attempt + random.random(), 64)
        log.info("Google lỗi tạm, thử lại", extra={"attempt": attempt + 1, "wait_s": round(wait, 1)})
        _sleep(wait)
        attempt += 1


def raise_for(response: httpx.Response, ok: tuple[int, ...] = (200,)) -> None:
    if response.status_code in ok:
        return
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code == 429 or response.status_code >= 500:
        raise GoogleUnavailable()
    raise GoogleHttpError(response.status_code, error_reason(response), body)
