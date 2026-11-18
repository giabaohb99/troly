"""Hàng chờ ghi lên Google (11 mục 3.12, 40 mục 4.3).

Module ghi dòng nghiệp vụ rồi gọi `enqueue` trong cùng giao dịch. Worker (`push_due`) đọc trạng thái mới
nhất của dòng gốc lúc đẩy, nên sửa nhiều lần liền chỉ còn một dòng chờ.
"""

import json
import logging
import uuid
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core import clock
from app.integrations.google import oauth
from app.integrations.google.errors import (
    GoogleHttpError,
    GoogleNotConnected,
    GoogleReauthRequired,
    GoogleScopeMissing,
    GoogleUnavailable,
)
from app.integrations.google.models import GoogleAccount, GoogleOutbox

log = logging.getLogger("troly.google")

MAX_ATTEMPTS = 5
BATCH = 20
SERVICE_PACK = {"calendar": "calendar", "tasks": "tasks"}
REAUTH_PAUSE = timedelta(hours=1)
STORE_PAUSE = timedelta(minutes=5)


class StoreMissing(RuntimeError):
    """Module calendar hoặc task chưa đăng ký store (registry.register_integrations)."""


class PushConflict(Exception):
    """Google đã đổi trước (412): bản Google đã ghi vào app, thay đổi của app giữ ở last_error."""

    def __init__(self, snapshot: dict):
        self.snapshot = snapshot
        super().__init__("conflict")


def new_event_id() -> str:
    """Id sự kiện đặt sẵn: hex của UUID nằm trong bảng chữ base32hex Google cho phép (40 mục 4.1)."""
    return uuid.uuid4().hex


def enqueue(
    session: Session,
    user_id: int,
    service: str,
    op: str,
    local_type: str,
    local_id: int,
    payload: dict | None = None,
) -> bool:
    """Đặt một lệnh ghi lên Google. Chưa nối hoặc gói chưa bật thì không làm gì, trả False."""
    account = oauth.get_account(session, user_id)
    pack = SERVICE_PACK.get(service, service)
    if account is None or account.status == "revoked" or pack not in account.enabled_packs:
        return False
    waiting = session.scalars(
        select(GoogleOutbox)
        .where(
            GoogleOutbox.local_type == local_type,
            GoogleOutbox.local_id == local_id,
            GoogleOutbox.status.in_(("pending", "processing")),
        )
        .with_for_update()
    ).all()
    pending = next((r for r in waiting if r.status == "pending"), None)
    if pending is not None:
        # Xóa thắng mọi lệnh; chưa đẩy lần nào thì vẫn là insert.
        if op == "delete":
            pending.op = "delete"
        elif pending.op not in ("insert", "delete"):
            pending.op = op
        pending.payload = {**(pending.payload or {}), **(payload or {})}
        pending.next_attempt_at = clock.now()
    else:
        processing = next((r for r in waiting if r.status == "processing"), None)
        if processing is not None and processing.op == op:
            # Đang đẩy đúng lệnh này: đánh dấu để worker đẩy lại khi xong.
            processing.payload = {**(processing.payload or {}), **(payload or {}), "_again": True}
        else:
            session.add(
                GoogleOutbox(
                    user_id=user_id,
                    google_account_id=account.id,
                    service=service,
                    op=op,
                    local_type=local_type,
                    local_id=local_id,
                    payload=payload or {},
                    next_attempt_at=clock.now(),
                )
            )
    session.flush()
    session.execute(text("NOTIFY troly_wake, 'google'"))
    return True


def waiting_row(session: Session, local_type: str, local_id: int) -> GoogleOutbox | None:
    return session.scalar(
        select(GoogleOutbox).where(
            GoogleOutbox.local_type == local_type,
            GoogleOutbox.local_id == local_id,
            GoogleOutbox.status.in_(("pending", "processing")),
        )
    )


def mark_conflict(row: GoogleOutbox, snapshot: dict) -> None:
    row.status = "conflict"
    row.last_error = json.dumps(snapshot, ensure_ascii=False, default=str)
    row.locked_at = None


def push_due(session: Session) -> int:
    """Lấy tối đa 20 dòng tới hạn, đẩy từng dòng trong giao dịch riêng."""
    rows = list(
        session.scalars(
            select(GoogleOutbox)
            .where(GoogleOutbox.status == "pending", GoogleOutbox.next_attempt_at <= clock.now())
            .order_by(GoogleOutbox.id)
            .limit(BATCH)
            .with_for_update(skip_locked=True)
        )
    )
    now = clock.now()
    for row in rows:
        row.status, row.locked_at = "processing", now
        row.attempts += 1
    session.commit()
    for row in rows:
        _push_one(session, row)
        session.commit()
    return len(rows)


def _push_one(session: Session, row: GoogleOutbox) -> None:
    from app.integrations.google import calendar_sync, stores, tasks_sync

    account = session.get(GoogleAccount, row.google_account_id)
    try:
        if account is None:
            raise GoogleNotConnected()
        if account.status != "active":
            raise GoogleReauthRequired()
        if row.service == "calendar":
            if stores.calendar_store() is None:
                raise StoreMissing()
            calendar_sync.push_event(session, account, row)
        elif row.service == "tasks":
            if stores.task_store() is None:
                raise StoreMissing()
            tasks_sync.push_task(session, account, row)
        elif row.service == "drive" and row.op == "file_upload":
            from app.integrations.google import drive

            if stores.file_store() is None:
                raise StoreMissing()
            drive.push_upload(session, account, row)
        else:
            raise RuntimeError(f"Chưa hỗ trợ dịch vụ {row.service}")
        _finish(row)
    except PushConflict as exc:
        mark_conflict(row, exc.snapshot)
    except GoogleReauthRequired:
        # Giữ lệnh chờ tới khi nối lại (40 mục 3.3); không tính lần thử.
        _hold(row, REAUTH_PAUSE)
    except StoreMissing:
        log.info("Chưa có store, giữ lệnh Google chờ", extra={"outbox_id": row.id})
        _hold(row, STORE_PAUSE)
    except GoogleUnavailable:
        _retry_or_fail(session, row, "Google đang không phản hồi.")
    except (GoogleHttpError, GoogleScopeMissing, GoogleNotConnected, RuntimeError) as exc:
        log.warning("Lệnh Google hỏng hẳn", extra={"outbox_id": row.id, "error": str(exc)[:200]})
        _fail(session, row, str(exc)[:500])


def _hold(row: GoogleOutbox, pause: timedelta) -> None:
    row.status, row.locked_at = "pending", None
    row.attempts = max(0, row.attempts - 1)
    row.next_attempt_at = clock.now() + pause


def _finish(row: GoogleOutbox) -> None:
    payload = dict(row.payload or {})
    if payload.pop("_again", False):
        row.payload = payload
        row.status, row.locked_at = "pending", None
        row.next_attempt_at = clock.now()
        return
    row.status, row.locked_at, row.last_error = "done", None, None


def _retry_or_fail(session: Session, row: GoogleOutbox, error: str) -> None:
    if row.attempts >= MAX_ATTEMPTS:
        _fail(session, row, error)
        return
    row.status, row.locked_at, row.last_error = "pending", None, error
    row.next_attempt_at = clock.now() + timedelta(seconds=30 * 2 ** (row.attempts - 1))


def _fail(session: Session, row: GoogleOutbox, error: str) -> None:
    from app.integrations.google import stores

    row.status, row.locked_at, row.last_error = "failed", None, error
    store = stores.calendar_store() if row.local_type == "event" else stores.task_store()
    if store is not None and row.local_type in ("event", "task"):
        store.set_sync_status(session, row.user_id, row.local_id, "error", error)
