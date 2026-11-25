"""Gọi dịch vụ `zalo-bridge` (QĐ-52, Node + zca-js, trong mạng nội bộ compose): hợp đồng ở 50 mục 3.15.

Mọi đường (trừ /health) cần `Authorization: Bearer <ZALO_BRIDGE_TOKEN>`; bridge trả phong bì
`{success, message, data}`, lỗi có `data.code`. Mã lỗi đổi thành `ZaloError` với câu tiếng Việt cho app.
"""

import logging
import urllib.parse

import httpx

from app.core.config import get_settings
from app.core.errors import AppError

log = logging.getLogger("troly.zalo")

TIMEOUT = 20.0
MEDIA_TIMEOUT = 120.0
MAX_MEDIA_BYTES = 50 * 1024 * 1024

_transport: httpx.BaseTransport | None = None


class ZaloError(AppError):
    status = 502
    code = "ZALO_ERROR"
    message = "Zalo đang lỗi, thử lại sau."


# (HTTP của api, câu cho người dùng) theo `data.code` của bridge.
_ERRORS = {
    "NOT_LOGGED_IN": (409, "Zalo chưa đăng nhập. Vào Cài đặt → Zalo để quét mã QR."),
    "ALREADY_LOGGED_IN": (409, "Zalo đã đăng nhập rồi."),
    "RATE_LIMITED": (429, "Gửi Zalo nhanh quá, thử lại sau ít giây."),
    "THREAD_NOT_FOUND": (404, "Không thấy người hoặc nhóm Zalo này."),
    "ATTACHMENT_HOST_NOT_ALLOWED": (400, "Tệp đính kèm không hợp lệ."),
    "NOT_SUPPORTED": (400, "Zalo không cho việc này."),
    "VALIDATION_ERROR": (400, "Dữ liệu gửi Zalo chưa hợp lệ."),
    "TOO_LARGE": (413, "Tệp quá 50 MB."),
    "DOWNLOAD_FAILED": (502, "Không tải được tệp từ Zalo."),
    "ZALO_ERROR": (502, "Zalo trả lỗi, thử lại sau."),
    "UNAUTHORIZED": (502, "Máy chủ chưa khớp khóa với dịch vụ Zalo."),
}


def set_transport(transport: httpx.BaseTransport | None) -> None:
    """Bài kiểm thay bridge thật bằng MockTransport."""
    global _transport
    _transport = transport


def _client(timeout: float) -> httpx.Client:
    s = get_settings()
    if not s.zalo_bridge_token:
        raise ZaloError("Chưa cấu hình dịch vụ Zalo.", code="ZALO_BRIDGE_UNAVAILABLE", status=503)
    return httpx.Client(
        base_url=s.zalo_bridge_url.rstrip("/"),
        transport=_transport,
        timeout=timeout,
        headers={"Authorization": f"Bearer {s.zalo_bridge_token}"},
    )


def _raise_for(resp: httpx.Response) -> None:
    try:
        data = resp.json().get("data") or {}
    except ValueError:
        data = {}
    code = data.get("code") or ("ZALO_ERROR" if resp.status_code >= 500 else "VALIDATION_ERROR")
    status, message = _ERRORS.get(code, (502, "Zalo trả lỗi, thử lại sau."))
    if code == "RATE_LIMITED" and data.get("retry_after"):
        message = f"Gửi Zalo nhanh quá, thử lại sau {int(data['retry_after'])} giây."
    log.warning("zalo-bridge trả lỗi", extra={"status": resp.status_code, "code": code})
    raise ZaloError(message, code=code, status=status, data={"retry_after": data.get("retry_after")})


def request(method: str, path: str, *, json: dict | None = None, params: dict | None = None) -> dict:
    try:
        with _client(TIMEOUT) as client:
            resp = client.request(method, path, json=json, params=params)
    except httpx.HTTPError as exc:
        log.warning("Không gọi được zalo-bridge", extra={"error": type(exc).__name__})
        raise ZaloError("Dịch vụ Zalo đang tắt.", code="ZALO_BRIDGE_UNAVAILABLE", status=503) from exc
    if resp.status_code >= 400:
        _raise_for(resp)
    try:
        return resp.json().get("data") or {}
    except ValueError as exc:
        raise ZaloError() from exc


def login_status() -> dict:
    return request("GET", "/login/status")


def start_login() -> dict:
    return request("POST", "/login/qr")


def logout() -> dict:
    return request("POST", "/logout")


def contacts() -> list[dict]:
    return request("GET", "/conversations").get("items") or []


def group_history(thread_id: str, count: int = 50) -> list[dict]:
    data = request(
        "GET",
        f"/conversations/{urllib.parse.quote(thread_id, safe='')}/messages",
        params={"thread_type": "group", "count": count},
    )
    return data.get("items") or data.get("messages") or []


def request_old_messages(thread_type: str) -> dict:
    return request("POST", "/sync/old-messages", json={"thread_type": thread_type})


def send_message(
    thread_id: str, thread_type: str, *, text: str | None, files: list[dict], client_ref: str
) -> dict:
    body: dict = {"thread_id": thread_id, "thread_type": thread_type, "client_ref": client_ref}
    if text:
        body["text"] = text
    if files:
        body["files"] = files
    return request("POST", "/messages", json=body)


def fetch_media(url: str, name: str | None = None) -> tuple[bytes, str, str | None]:
    """Byte của ảnh, video, tệp trong tin Zalo (link CDN hết hạn sau vài giờ). Trả `(dữ liệu, mime, tên)`."""
    body = {"url": url}
    if name:
        body["name"] = name
    try:
        with _client(MEDIA_TIMEOUT) as client:
            resp = client.post("/media/fetch", json=body)
    except httpx.HTTPError as exc:
        raise ZaloError("Dịch vụ Zalo đang tắt.", code="ZALO_BRIDGE_UNAVAILABLE", status=503) from exc
    if resp.status_code >= 400:
        _raise_for(resp)
    if len(resp.content) > MAX_MEDIA_BYTES:
        raise ZaloError("Tệp quá 50 MB.", code="TOO_LARGE", status=413)
    mime = (resp.headers.get("content-type") or "application/octet-stream").split(";")[0].strip()
    raw_name = resp.headers.get("x-file-name")
    return resp.content, mime, urllib.parse.unquote(raw_name) if raw_name else name
