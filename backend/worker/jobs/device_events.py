"""Xử lý tab_device_event (10 mục 3.9): thông báo sang expense (kể cả ghép cặp chuyển nội bộ) hoặc inbox.

Điều phối ở worker để module device không phụ thuộc module nào (10 mục 3.4). `reminder_action`
(đánh dấu việc xong từ thông báo nhắc) nối vào task ở Phase 3; tới lúc đó bỏ qua.
"""

import logging

from sqlalchemy import select

from app.core.context import UserContext
from app.core.db import SessionLocal
from app.core.models import User
from app.modules.device import service as device_service
from app.modules.expense import service as expense_service
from app.modules.inbox import service as inbox_service

log = logging.getLogger("troly.device_events")
BATCH = 200


def _user(session, user_id: int, cache: dict) -> UserContext:
    if user_id not in cache:
        tz = session.scalar(select(User.timezone).where(User.id == user_id))
        cache[user_id] = UserContext(user_id=user_id, timezone=tz or "Asia/Ho_Chi_Minh")
    return cache[user_id]


def handle_event(session, ev, user: UserContext) -> dict:
    if ev.kind != "notification":
        return {
            "status": "ignored",
            "result_kind": "none",
            "result_id": None,
            "reason": "Chưa xử lý nhắc việc",
        }
    app = device_service.resolve_listened_app(session, ev.user_id, ev.device_id, ev.app_package)
    if app is None:
        return {
            "status": "ignored",
            "result_kind": "none",
            "result_id": None,
            "reason": "App không còn được nghe",
        }
    p = ev.payload
    if app.purpose == "expense":
        return expense_service.ingest_bank_notification(
            session,
            user,
            bank=app.parser,
            package=ev.app_package,
            title=p.get("title") or "",
            text=p.get("text") or "",
            posted_at=ev.posted_at,
            device_event_id=ev.id,
        )
    return inbox_service.ingest_notification(
        session,
        user,
        parser=app.parser,
        app_package=ev.app_package,
        payload=p,
        posted_at=ev.posted_at,
        device_id=ev.device_id,
        device_event_id=ev.id,
    )


def process_device_events() -> int:
    done = 0
    users: dict[int, UserContext] = {}
    with SessionLocal() as session:
        events = device_service.claim_pending_events(session, BATCH)
        session.commit()
        for ev in events:
            try:
                with session.begin_nested():
                    result = handle_event(session, ev, _user(session, ev.user_id, users))
                device_service.finish_event(
                    ev,
                    result["status"],
                    result["result_kind"],
                    result.get("result_id"),
                    None if result["status"] == "done" else result.get("reason"),
                )
            except Exception:
                log.exception("Xử lý sự kiện thiết bị lỗi", extra={"device_event_id": ev.id})
                device_service.retry_event(ev, "Xử lý lỗi, sẽ thử lại.")
            session.commit()
            done += 1
    return done
