from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.inbox import service
from app.modules.inbox.models import APPS, RULE_KINDS

router = APIRouter()

Status = Literal["new", "seen", "done"]


class StatusIn(BaseModel):
    status: Status


class MarkIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=service.MARK_MAX)
    status: Status


class RuleIn(BaseModel):
    kind: Literal[RULE_KINDS]  # type: ignore[valid-type]
    value: str = Field(min_length=1, max_length=200)
    app: Literal[APPS] | None = None  # type: ignore[valid-type]


@router.get("/inbox/conversations")
def list_conversations(
    app: Literal[APPS] | None = None,  # type: ignore[valid-type]
    status: Status | None = None,
    importance: Literal["normal", "important"] | None = None,
    from_: AwareDatetime | None = Query(default=None, alias="from"),
    to: AwareDatetime | None = None,
    cursor: str | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    filters = {"app": app, "status": status, "importance": importance, "from": from_, "to": to}
    return ok(service.list_conversations(session, user.user_id, filters, cursor, limit))


@router.get("/inbox/conversations/{conversation_key}/messages")
def list_messages(
    conversation_key: str,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.list_messages(session, user.user_id, conversation_key, cursor, limit))


@router.post("/inbox/conversations/{conversation_key}/mark")
def mark_conversation(
    conversation_key: str,
    body: StatusIn,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.mark_conversation(session, user.user_id, conversation_key, body.status))


@router.post("/inbox/messages/mark")
def mark_messages(
    body: MarkIn, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.mark_messages(session, user.user_id, body.ids, body.status))


@router.patch("/inbox/messages/{message_id}")
def update_message(
    message_id: int,
    body: StatusIn,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.update_message(session, user.user_id, message_id, body.status))


@router.get("/inbox/rules")
def list_rules(
    user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok({"items": service.list_rules(session, user.user_id)})


@router.post("/inbox/rules", status_code=201)
def create_rule(
    body: RuleIn, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.create_rule(session, user.user_id, body.kind, body.value, body.app))


@router.delete("/inbox/rules/{rule_id}")
def delete_rule(
    rule_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    service.delete_rule(session, user.user_id, rule_id)
    return ok(None)
