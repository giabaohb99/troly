"""Đường /trips (12 mục 5.1, 5.7)."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.trip import service

router = APIRouter(prefix="/trips", tags=["trip"])


class ImportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: int | None = None
    text: str | None = None
    url: str | None = None
    title: str | None = None
    start_date: date | None = None
    travel_mode: str | None = None


class TripPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    start_date: date | None = None
    travel_mode: str | None = None
    origin_text: str | None = None
    status: str | None = None


class StopIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day_no: int | None = None
    seq: int | None = None
    title: str | None = None
    category: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    fixed: bool | None = None
    optional: bool | None = None
    stay_minutes: int | None = None
    place_query: str | None = None
    note: str | None = None
    phone: str | None = None
    cost_note: str | None = None
    place_id: str | None = None
    lat: float | None = None
    lng: float | None = None
    resolve_status: str | None = None


class ReorderIn(BaseModel):
    day_no: int
    stop_ids: list[int]


class ResolveIn(BaseModel):
    place_query: str


class ExportIn(BaseModel):
    save_to_drive: bool = False


@router.get("")
def list_trips(
    status: str | None = None,
    q: str | None = None,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok({"items": service.list_trips(session, user, status, q), "next_cursor": None})


@router.post("/import", status_code=202)
def import_trip(
    body: ImportIn, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    data = service.import_trip(session, user, **body.model_dump())
    return ok(data, "Đang đọc lịch trình.")


@router.get("/{trip_id}")
def get_trip(
    trip_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.get_trip(session, user, trip_id))


@router.patch("/{trip_id}")
def patch_trip(
    trip_id: int,
    body: TripPatch,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.update_trip(session, user, trip_id, body.model_dump(exclude_unset=True)))


@router.delete("/{trip_id}")
def delete_trip(
    trip_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    service.delete_trip(session, user, trip_id)
    return ok(None, "Đã xóa chuyến đi.")


@router.post("/{trip_id}/stops", status_code=201)
def create_stop(
    trip_id: int,
    body: StopIn,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.create_stop(session, user, trip_id, body.model_dump(exclude_unset=True)))


@router.post("/{trip_id}/stops/reorder")
def reorder_stops(
    trip_id: int,
    body: ReorderIn,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok({"items": service.reorder_stops(session, user, trip_id, body.day_no, body.stop_ids)})


@router.patch("/{trip_id}/stops/{stop_id}")
def patch_stop(
    trip_id: int,
    stop_id: int,
    body: StopIn,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.update_stop(session, user, trip_id, stop_id, body.model_dump(exclude_unset=True)))


@router.delete("/{trip_id}/stops/{stop_id}")
def delete_stop(
    trip_id: int,
    stop_id: int,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    service.delete_stop(session, user, trip_id, stop_id)
    return ok(None, "Đã xóa điểm.")


@router.post("/{trip_id}/stops/{stop_id}/resolve")
def resolve_stop(
    trip_id: int,
    stop_id: int,
    body: ResolveIn,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.resolve_candidates(session, user, trip_id, stop_id, body.place_query))


@router.post("/{trip_id}/evaluate", status_code=202)
def evaluate(
    trip_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.evaluate_trip(session, user, trip_id), "Đang đánh giá chuyến đi.")


@router.post("/{trip_id}/options/{option_id}/choose")
def choose(
    trip_id: int,
    option_id: int,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.choose_option(session, user, trip_id, option_id), "Đã chọn phương án.")


@router.get("/{trip_id}/map-links")
def map_links(
    trip_id: int,
    day_no: int | None = None,
    max_waypoints: int = Query(9),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.map_links(session, user, trip_id, day_no, max_waypoints))


@router.post("/{trip_id}/export-docx")
def export_docx(
    trip_id: int,
    body: ExportIn | None = None,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.export_docx(session, user, trip_id, bool(body and body.save_to_drive)), "Đã xuất Word.")


@router.post("/{trip_id}/to-calendar")
def to_calendar(
    trip_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.to_calendar(session, user, trip_id), "Đã đưa chuyến đi vào lịch.")
