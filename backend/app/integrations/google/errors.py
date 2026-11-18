"""Lỗi của tích hợp Google; mã theo 12 mục 3.5."""

from app.core.errors import AppError, ExternalServiceError


class GoogleNotConnected(AppError):
    status = 409
    code = "GOOGLE_NOT_CONNECTED"
    message = "Chưa kết nối Google."


class GoogleReauthRequired(AppError):
    status = 409
    code = "GOOGLE_REAUTH_REQUIRED"
    message = "Kết nối Google đã hết hạn, hãy nối lại."


class GoogleScopeMissing(AppError):
    status = 409
    code = "GOOGLE_SCOPE_MISSING"
    message = "Google chưa cấp đủ quyền cho mục này, hãy kết nối lại."


class GoogleUnavailable(ExternalServiceError):
    message = "Google đang không phản hồi, thử lại sau."


class GoogleHttpError(Exception):
    """Lỗi HTTP Google sau khi đã thử lại; nơi gọi xử lý theo mã (404, 410, 412...)."""

    def __init__(self, status: int, reason: str = "", body: dict | None = None):
        self.status = status
        self.reason = reason
        self.body = body or {}
        super().__init__(f"Google {status} {reason}".strip())
