"""Chạy việc lịch đã duyệt (QĐ-23): thẻ từ API và từ công cụ AI dùng cùng `input`.

add_event: `{data}` như thân POST /calendar/events.
update_event: `{event_id, occurrence_start, changes}`.
delete_event: `{event_id, occurrence_start}` hoặc `{events: [...]}` (xóa nhiều).
Khách nhận email của Google (`sendUpdates=all`).
"""

from sqlalchemy.orm import Session

from app.core.context import UserContext
from app.modules.calendar import service


def add_event(session: Session, user: UserContext, input_: dict) -> dict:
    return service.create_event(session, user, input_["data"], approved=True)["event"]


def update_event(session: Session, user: UserContext, input_: dict) -> dict:
    return service.update_event(
        session,
        user,
        int(input_["event_id"]),
        input_.get("changes") or {},
        occurrence_start=input_.get("occurrence_start"),
        approved=True,
    )


def delete_event(session: Session, user: UserContext, input_: dict) -> dict:
    """Một sự kiện `{event_id, occurrence_start}` hoặc nhiều (công cụ AI xóa từ 2 sự kiện, QĐ-27)
    `{events: [{event_id, occurrence_start}, ...]}`."""
    items = input_["events"] if "events" in input_ else [input_]
    ids = []
    for item in items:
        service.delete_event(
            session, user, int(item["event_id"]), occurrence_start=item.get("occurrence_start"), approved=True
        )
        ids.append(int(item["event_id"]))
    return {"deleted": len(ids), "event_ids": ids}


EXECUTORS = {"add_event": add_event, "update_event": update_event, "delete_event": delete_event}
