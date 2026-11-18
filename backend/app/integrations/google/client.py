"""Gọi API Google có token của một tài khoản: 401 thì làm mới một lần rồi gọi lại (40 mục 10)."""

from sqlalchemy.orm import Session

from app.integrations.google import http, oauth
from app.integrations.google.errors import GoogleHttpError, GoogleScopeMissing
from app.integrations.google.models import GoogleAccount

CALENDAR = "https://www.googleapis.com/calendar/v3"
TASKS = "https://tasks.googleapis.com/tasks/v1"


class GoogleApi:
    def __init__(self, session: Session, account: GoogleAccount):
        self.session = session
        self.account = account

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        content: bytes | None = None,
        headers: dict | None = None,
        ok: tuple[int, ...] = (200,),
        return_location: bool = False,
    ):
        """Trả JSON của phản hồi; return_location=True thì trả header Location (phiên tải resumable)."""
        token = oauth.access_token(self.session, self.account)
        extra = (
            {"params": params, "json": json} if content is None else {"params": params, "content": content}
        )
        response = http.send(method, url, headers=self._headers(token, headers), **extra)
        if response.status_code == 401:
            token = oauth.access_token(self.session, self.account, force_refresh=True)
            response = http.send(method, url, headers=self._headers(token, headers), **extra)
        if response.status_code == 403 and http.error_reason(response) in (
            "insufficientPermissions",
            "ACCESS_TOKEN_SCOPE_INSUFFICIENT",
        ):
            raise GoogleScopeMissing()
        http.raise_for(response, ok)
        if return_location:
            return response.headers.get("location", "")
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    @staticmethod
    def _headers(token: str, extra: dict | None) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        if extra:
            headers.update(extra)
        return headers


__all__ = ["CALENDAR", "TASKS", "GoogleApi", "GoogleHttpError"]
