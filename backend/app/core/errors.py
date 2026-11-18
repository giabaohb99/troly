"""Lỗi và phong bì {success, message, data} (10 mục 3.8, 12 mục 3.3, 3.5)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("troly.errors")


class AppError(Exception):
    status = 400
    code = "VALIDATION_ERROR"
    message = "Dữ liệu chưa hợp lệ."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status: int | None = None,
        fields: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.message = message or self.message
        self.code = code or self.code
        self.status = status or self.status
        self.fields = fields
        self.extra = data or {}
        self.headers = headers
        super().__init__(self.message)


class ValidationError(AppError):
    pass


class UnauthorizedError(AppError):
    status = 401
    code = "AUTH_REQUIRED"
    message = "Cần đăng nhập."


class NotFoundError(AppError):
    status = 404
    code = "NOT_FOUND"
    message = "Không tìm thấy."


class ConflictError(AppError):
    status = 409
    code = "CONFLICT"
    message = "Dữ liệu đã thay đổi, tải lại rồi thử lại."


class RateLimitError(AppError):
    status = 429
    code = "RATE_LIMITED"
    message = "Thao tác quá nhanh, thử lại sau ít phút."


class ExternalServiceError(AppError):
    status = 502
    code = "EXTERNAL_SERVICE_ERROR"
    message = "Dịch vụ ngoài đang lỗi, thử lại sau."


class AiUnavailableError(ExternalServiceError):
    code = "AI_UNAVAILABLE"
    message = "Trợ lý đang bận, thử lại sau."


def ok(data: Any = None, message: str = "") -> dict[str, Any]:
    return {"success": True, "message": message, "data": data}


def error_body(code: str, message: str, fields: dict | None = None, **extra: Any) -> dict[str, Any]:
    return {"success": False, "message": message, "data": {"code": code, "fields": fields, **extra}}


_PYDANTIC_MESSAGES = {
    "missing": "Thiếu trường này.",
    "string_too_long": "Quá dài.",
    "string_too_short": "Quá ngắn.",
    "greater_than": "Phải lớn hơn {gt}.",
    "less_than": "Phải nhỏ hơn {lt}.",
    "int_parsing": "Phải là số nguyên.",
    "datetime_parsing": "Thời điểm không hợp lệ.",
    "timezone_aware": "Thời điểm phải có múi giờ, ví dụ +07:00.",
    "literal_error": "Giá trị không hợp lệ.",
    "enum": "Giá trị không hợp lệ.",
    "extra_forbidden": "Trường không được phép.",
}


def _field_message(err: dict) -> str:
    template = _PYDANTIC_MESSAGES.get(err.get("type", ""))
    if template is None:
        return "Giá trị không hợp lệ."
    try:
        return template.format(**(err.get("ctx") or {}))
    except (KeyError, IndexError):
        return template


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=error_body(exc.code, exc.message, exc.fields, **exc.extra),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
            fields[".".join(loc) or "_"] = _field_message(err)
        return JSONResponse(
            status_code=400, content=error_body("VALIDATION_ERROR", "Dữ liệu chưa hợp lệ.", fields)
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return JSONResponse(status_code=404, content=error_body("NOT_FOUND", "Không tìm thấy."))
        if exc.status_code == 405:
            return JSONResponse(
                status_code=405, content=error_body("METHOD_NOT_ALLOWED", "Phương thức không hợp lệ.")
            )
        return JSONResponse(status_code=exc.status_code, content=error_body("HTTP_ERROR", str(exc.detail)))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        log.exception("Lỗi chưa bắt", extra={"request_id": request_id})
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "Máy chủ gặp lỗi, đã ghi lại.", request_id=request_id),
        )
