from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ValidationError, ok
from app.modules.chat import service

router = APIRouter()


class SendMessageIn(BaseModel):
    client_message_id: UUID
    text: str = Field(default="", max_length=4000)
    attachment_file_ids: list[int] = Field(default_factory=list, max_length=4)
    mode: Literal["chat", "think", "research", "summary"] | None = None


@router.post("/chat/messages")
def post_message(
    body: SendMessageIn,
    request: Request,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not body.text.strip() and not body.attachment_file_ids:
        raise ValidationError(fields={"text": "Nhập nội dung hoặc đính kèm tệp."})
    prepared = service.prepare_turn(
        session, user, body.text, body.mode, body.client_message_id, body.attachment_file_ids
    )
    if "text/event-stream" in request.headers.get("accept", ""):
        return StreamingResponse(
            service.stream_turn(prepared),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return ok(service.run_turn_json(prepared))


@router.get("/chat/today")
def get_today(user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    return ok(service.get_today(session, user))


@router.get("/chat/conversations")
def get_conversations(
    cursor: str | None = None,
    limit: int = Query(30, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.list_conversations(session, user, cursor, limit))


@router.get("/chat/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: int,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.list_messages(session, user, conversation_id, cursor, limit))


@router.delete("/chat/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    service.delete_conversation(session, user, conversation_id)
    return ok(None)


@router.get("/chat/actions")
def get_actions(
    status: str = "pending",
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok({"items": service.list_actions(session, user, status)})


@router.post("/chat/actions/{action_id}/approve")
def approve_action(
    action_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.decide_action(session, user, action_id, approve=True))


@router.post("/chat/actions/{action_id}/reject")
def reject_action(
    action_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.decide_action(session, user, action_id, approve=False))
