"""Gọi ra máy chủ do người dùng nhập (QĐ-56): chống SSRF, giới hạn kích thước và thời gian.

Chỉ nhận https, cổng 443; tên máy phải phân giải ra địa chỉ công khai (chặn localhost, IP riêng, link-local,
dải dành riêng, multicast); không theo chuyển hướng; phản hồi tối đa 1 MB. Mọi URL lấy từ metadata
(authorize, token, register, revoke) cũng qua đây.
"""

import ipaddress
import socket
from urllib.parse import urlsplit

import httpx

from app.core.errors import AppError, ValidationError
from app.integrations.connectors.settings import get_connector_settings

_transport: httpx.BaseTransport | None = None
_resolve = socket.getaddrinfo


class ConnectorUnavailable(AppError):
    status = 502
    code = "CONNECTOR_UNAVAILABLE"
    message = "Máy chủ kết nối không phản hồi, thử lại sau."


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


def check_url(url: str) -> str:
    """Trả URL đã chuẩn hóa hoặc ném ValidationError (câu tiếng Việt)."""
    parts = urlsplit((url or "").strip())
    if parts.scheme != "https" or not parts.hostname:
        raise ValidationError("Địa chỉ phải bắt đầu bằng https://.", fields={"url": "Chỉ nhận https."})
    if parts.username or parts.password:
        raise ValidationError("Địa chỉ không được chứa tên đăng nhập.", fields={"url": "Không hợp lệ."})
    if parts.port not in (None, 443):
        raise ValidationError("Chỉ nhận cổng 443.", fields={"url": "Không hợp lệ."})
    host = parts.hostname
    try:
        infos = _resolve(host, 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError) as exc:
        raise ValidationError("Không tìm thấy máy chủ này.", fields={"url": "Không phân giải được."}) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise ValidationError(
                "Địa chỉ trỏ vào mạng nội bộ, không được dùng.", fields={"url": "Mạng nội bộ."}
            )
    return parts._replace(fragment="").geturl()


def send(method: str, url: str, **kw) -> httpx.Response:
    """Một lời gọi ra ngoài an toàn. Phản hồi quá 1 MB thì ném ConnectorUnavailable."""
    check_url(url)
    settings = get_connector_settings()
    headers = {"Accept": "application/json", **kw.pop("headers", {})}
    try:
        with httpx.Client(
            transport=_transport, timeout=settings.connectors_timeout_seconds, follow_redirects=False
        ) as c:
            with c.stream(method, url, headers=headers, **kw) as r:
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > settings.connectors_max_response_bytes:
                        raise ConnectorUnavailable("Máy chủ trả dữ liệu quá lớn.")
                # iter_bytes đã giải nén: bỏ các header nén, độ dài để bản dựng lại không giải nén lần hai.
                keep = {
                    k: v
                    for k, v in r.headers.items()
                    if k.lower() not in ("content-encoding", "content-length", "transfer-encoding")
                }
                return httpx.Response(r.status_code, headers=keep, content=body, request=r.request)
    except httpx.HTTPError as exc:
        raise ConnectorUnavailable() from exc
