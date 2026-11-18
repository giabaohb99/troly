"""Lớp giữa: request_id và log truy cập, giới hạn thân, kiểm bản app (10 mục 3.13)."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.errors import error_body
from app.core.logging import request_id_var, user_id_var

log = logging.getLogger("troly.access")

MAX_BODY = 1024 * 1024
DEVICE_EVENTS_MAX_BODY = 256 * 1024


def client_ip(request: Request) -> str:
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "unknown")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        user_token = user_id_var.set(None)
        started = time.perf_counter()
        status = 500
        try:
            length = int(request.headers.get("content-length") or 0)
            limit = DEVICE_EVENTS_MAX_BODY if request.url.path.endswith("/device/events") else MAX_BODY
            if length > limit:
                response: Response = JSONResponse(
                    status_code=413, content=error_body("PAYLOAD_TOO_LARGE", "Dữ liệu gửi lên quá lớn.")
                )
            else:
                response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "ip": client_ip(request),
                },
            )
            request_id_var.reset(token)
            user_id_var.reset(user_token)
