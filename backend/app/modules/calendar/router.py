from datetime import date

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.orm import Session

from app.core import clock
from app.core.auth import get_current_user, get_device_or_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.calendar import service

router = APIRouter()


class AttendeeIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str | None = Field(default=None, max_length=200)


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=1024)
    description: str | None = Field(default=None, max_length=8000)
    location: str | None = Field(default=None, max_length=1000)
    all_day: bool = False
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    start_date: date | None = None
    end_date: date | None = None
    remind_minutes: list[int] | None = Field(default=None, max_length=5)
    is_alarm: bool = False
    meet: bool = False
    attendees: list[AttendeeIn] = Field(default_factory=list, max_length=service.MAX_ATTENDEES)


class EventPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=1024)
    description: str | None = Field(default=None, max_length=8000)
    location: str | None = Field(default=None, max_length=1000)
    all_day: bool | None = None
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    start_date: date | None = None
    end_date: date | None = None
    remind_minutes: list[int] | None = Field(default=None, max_length=5)
    remind_source: str | None = Field(default=None, pattern="^(app|google)$")
    is_alarm: bool | None = None
    meet: bool | None = None
    attendees: list[AttendeeIn] | None = Field(default=None, max_length=service.MAX_ATTENDEES)


def _maybe_pending(result: dict, response: Response, created_status: int = 200):
    if "pending_action" in result:
        response.status_code = 202
        return ok({"pending_action": result["pending_action"]})
    response.status_code = created_status
    return ok(result.get("event", result))


@router.get("/calendar/events")
def list_events(
    from_: AwareDatetime = Query(alias="from"),
    to: AwareDatetime = Query(),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok({"items": service.list_events(session, user, from_, to)})


@router.post("/calendar/events", status_code=201)
def create_event(
    body: EventIn,
    response: Response,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return _maybe_pending(service.create_event(session, user, body.model_dump()), response, 201)


@router.get("/calendar/reminders")
def list_reminders(
    response: Response,
    from_: AwareDatetime | None = Query(default=None, alias="from"),
    days: int = Query(default=14, ge=1, le=31),
    if_none_match: str | None = Header(default=None),
    user: UserContext = Depends(get_device_or_user),
    session: Session = Depends(get_session),
):
    data = service.list_reminders(session, user, from_ or clock.now(), days)
    etag = f'"{data["revision"]}"'
    if if_none_match and if_none_match.removeprefix("W/").strip().strip('"') == etag.strip('"'):
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return ok(data)


@router.get("/calendar/events/{event_id}")
def get_event(
    event_id: int,
    occurrence_start: AwareDatetime | None = None,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.get_event(session, user, event_id, occurrence_start))


@router.patch("/calendar/events/{event_id}")
def update_event(
    event_id: int,
    body: EventPatch,
    response: Response,
    occurrence_start: AwareDatetime | None = None,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    changes = body.model_dump(exclude_unset=True)
    result = service.update_event(session, user, event_id, changes, occurrence_start=occurrence_start)
    return _maybe_pending(result, response)


@router.delete("/calendar/events/{event_id}")
def delete_event(
    event_id: int,
    response: Response,
    occurrence_start: AwareDatetime | None = None,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    result = service.delete_event(session, user, event_id, occurrence_start=occurrence_start)
    if result and "pending_action" in result:
        response.status_code = 202
        return ok({"pending_action": result["pending_action"]})
    return ok(None)


@router.post("/calendar/events/{event_id}/restore")
def restore_event(
    event_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.restore_event(session, user, event_id))
