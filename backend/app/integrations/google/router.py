"""Đường Google (12 mục 5.1, 5.6). Gắn dưới /api/v1. callback và webhook không cần JWT."""

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.integrations.google import calendar_sync, oauth, service

router = APIRouter()


@router.get("/google/status")
def read_status(
    user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.get_status(session, user.user_id))


@router.post("/google/connect")
def connect(
    packs: list[str] = Body(..., embed=True),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.connect(session, user.user_id, packs))


@router.get("/google/oauth/callback", response_class=HTMLResponse)
def oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    result = oauth.finish_connect(session, code, state, error)
    return HTMLResponse(oauth.callback_html(result))


@router.post("/google/disconnect")
def disconnect(
    keep_data: bool = Body(True, embed=True),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    service.disconnect(session, user.user_id, keep_data)
    return ok(None, "Đã ngắt kết nối Google.")


@router.post("/google/sync/{service_name}", status_code=202)
def sync_now(
    service_name: str,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    data = service.request_sync(session, user.user_id, service_name)
    session.execute(text("NOTIFY troly_wake, 'google'"))
    return ok(data, "Đã đặt đồng bộ.")


@router.get("/google/outbox")
def list_outbox(
    status: str = Query("failed,conflict"),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    wanted = [s for s in status.split(",") if s in ("pending", "processing", "done", "failed", "conflict")]
    return ok({"items": service.list_outbox(session, user.user_id, wanted)})


@router.post("/google/outbox/{outbox_id}/retry")
def retry_outbox(
    outbox_id: int,
    reapply: bool = Body(False, embed=True),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    data = service.retry_outbox(session, user.user_id, outbox_id, reapply)
    session.execute(text("NOTIFY troly_wake, 'google'"))
    return ok(data, "Đã đặt thử lại.")


@router.post("/webhooks/google/calendar")
def calendar_webhook(request: Request, session: Session = Depends(get_session)) -> Response:
    """Luôn trả 200 rỗng; chỉ đặt cờ đồng bộ khi kênh và token khớp (12 mục 5.6)."""
    headers = request.headers
    matched = calendar_sync.handle_webhook(
        session,
        headers.get("x-goog-channel-id"),
        headers.get("x-goog-channel-token"),
        headers.get("x-goog-resource-state"),
    )
    if matched:
        session.execute(text("NOTIFY troly_wake, 'google'"))
    return Response(status_code=200)
