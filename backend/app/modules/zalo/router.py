"""Route Zalo (QĐ-52), chỉ đăng ký khi FEATURE_ZALO_BRIDGE bật.

`POST /internal/zalo/events` cho zalo-bridge (khóa ZALO_BRIDGE_TOKEN, không JWT). Còn lại cho app (JWT): tin và
cuộc trò chuyện Zalo đọc qua `/inbox/conversations?app=zalo` và `/inbox/conversations/{key}/messages`.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.zalo import service

router = APIRouter()


class EventsIn(BaseModel):
    events: list = Field(default_factory=list, max_length=service.MAX_EVENTS)


@router.post("/internal/zalo/events")
def receive_events(
    body: EventsIn,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    service.check_bridge_token(authorization)
    return ok(service.handle_events(session, body.events))


@router.get("/zalo/status")
def get_status(
    user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.status(session, user))


@router.post("/zalo/login")
def start_login(
    user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.start_login(session, user))


@router.post("/zalo/logout")
def logout(user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    return ok(service.logout(session, user))


@router.get("/zalo/contacts")
def get_contacts(user: UserContext = Depends(get_current_user)) -> dict:
    return ok({"items": service.contacts(user)})


@router.post("/zalo/conversations/{conversation_key}/sync")
def sync_history(
    conversation_key: str,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.sync_history(session, user, conversation_key))


class SendIn(BaseModel):
    conversation_key: str | None = Field(default=None, max_length=200)
    thread_id: str | None = Field(default=None, max_length=100)
    thread_type: Literal["user", "group"] | None = None
    text: str | None = Field(default=None, max_length=service.TEXT_MAX)
    file_ids: list[int] = Field(default_factory=list, max_length=service.MAX_FILES)
    client_ref: str | None = Field(default=None, max_length=100)


@router.post("/zalo/messages")
def send_message(
    body: SendIn, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    """Người dùng tự gõ trong app: gửi thẳng, không qua thẻ duyệt (QĐ-52)."""
    return ok(service.send(session, user, **body.model_dump()))
