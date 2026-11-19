"""Việc Google gọi từ router và worker: trạng thái, đồng bộ ngay, hàng chờ lỗi, ngắt kết nối,
đồng bộ lần đầu (12 mục 5.6, 40 mục 3 tới 5)."""

import json
import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.integrations.google import calendar_sync, gmail, oauth, outbox, stores, tasks_sync
from app.integrations.google.client import GoogleApi
from app.integrations.google.errors import GoogleNotConnected, GoogleReauthRequired
from app.integrations.google.models import PACKS, GoogleAccount, GoogleOutbox, GoogleSyncState

log = logging.getLogger("troly.google")

INITIAL_MESSAGES = {
    "pending": "Đang chờ lấy dữ liệu Google lần đầu.",
    "running": "Đang lấy lịch và việc lần đầu.",
    "done": "",
    "failed": "Lấy dữ liệu Google lần đầu bị lỗi, sẽ thử lại.",
}


def _states(session: Session, account_id: int) -> list[GoogleSyncState]:
    return list(
        session.scalars(select(GoogleSyncState).where(GoogleSyncState.google_account_id == account_id))
    )


def get_status(session: Session, user_id: int) -> dict:
    account = oauth.get_account(session, user_id)
    if account is None:
        return {
            "connected": False,
            "email": None,
            "status": None,
            "packs": [],
            "initial_sync": {"state": None, "message": ""},
            "failed_outbox_count": 0,
        }
    granted = set(oauth.granted_packs(account.granted_scopes))
    by_service = {s.service: s for s in _states(session, account.id)}
    packs = []
    for pack in PACKS:
        if pack == "base":
            continue
        state = by_service.get(pack)
        packs.append(
            {
                "name": pack,
                "enabled": pack in account.enabled_packs,
                "granted": pack in granted,
                "last_sync_at": state.last_sync_at if state else None,
                "status": state.status if state else None,
                "last_error": state.last_error if state else None,
            }
        )
    initial = [s.initial_sync_state for s in by_service.values() if s.initial_sync_state]
    overall = next((v for v in ("failed", "running", "pending") if v in initial), "done" if initial else None)
    failed = session.scalar(
        select(func.count())
        .select_from(GoogleOutbox)
        .where(GoogleOutbox.user_id == user_id, GoogleOutbox.status.in_(("failed", "conflict")))
    )
    return {
        "connected": account.status != "revoked",
        "email": account.email,
        "status": account.status,
        "packs": packs,
        "initial_sync": {"state": overall, "message": INITIAL_MESSAGES.get(overall or "done", "")},
        "failed_outbox_count": failed or 0,
    }


def connect(session: Session, user_id: int, packs: list[str]) -> dict:
    unknown = [p for p in packs if p not in PACKS]
    if unknown:
        raise ValidationError("Gói không hợp lệ: " + ", ".join(unknown), fields={"packs": "Không hợp lệ"})
    return {"auth_url": oauth.start_connect(session, user_id, packs)}


def request_sync(session: Session, user_id: int, service: str) -> dict:
    account = oauth.require_account(session, user_id, service if service in PACKS else None)
    state = session.scalar(
        select(GoogleSyncState).where(
            GoogleSyncState.google_account_id == account.id, GoogleSyncState.service == service
        )
    )
    if state is None:
        raise NotFoundError("Dịch vụ này chưa đồng bộ.")
    state.needs_sync = True
    state.next_sync_at = clock.now()
    session.flush()
    return {"queued": True}


def serialize_outbox(row: GoogleOutbox) -> dict:
    return {
        "id": row.id,
        "service": row.service,
        "op": row.op,
        "local_type": row.local_type,
        "local_id": row.local_id,
        "status": row.status,
        "attempts": row.attempts,
        "last_error": None if row.status == "conflict" else row.last_error,
        "has_discarded_change": row.status == "conflict",
        "updated_at": row.updated_at,
    }


def list_outbox(session: Session, user_id: int, statuses: list[str]) -> list[dict]:
    rows = session.scalars(
        select(GoogleOutbox)
        .where(GoogleOutbox.user_id == user_id, GoogleOutbox.status.in_(statuses))
        .order_by(GoogleOutbox.id.desc())
        .limit(100)
    )
    return [serialize_outbox(r) for r in rows]


def retry_outbox(session: Session, user_id: int, outbox_id: int, reapply: bool) -> dict:
    row = session.scalar(
        select(GoogleOutbox)
        .where(GoogleOutbox.id == outbox_id, GoogleOutbox.user_id == user_id)
        .with_for_update()
    )
    if row is None:
        raise NotFoundError()
    if row.status not in ("failed", "conflict"):
        raise ConflictError("Lệnh này không ở trạng thái lỗi.")
    if reapply and row.status == "conflict" and row.local_type == "event":
        store = stores.calendar_store()
        if store is not None and row.last_error:
            store.restore_snapshot(session, user_id, row.local_id, json.loads(row.last_error))
    other = outbox.waiting_row(session, row.local_type, row.local_id)
    if other is not None:
        row.status = "done"  # đã có lệnh mới hơn đang chờ, lệnh đó mang trạng thái mới nhất
        session.flush()
        return serialize_outbox(other)
    row.status, row.attempts, row.last_error, row.locked_at = "pending", 0, None, None
    row.next_attempt_at = clock.now()
    session.flush()
    return serialize_outbox(row)


def disconnect(session: Session, user_id: int, keep_data: bool) -> None:
    account = oauth.get_account(session, user_id)
    if account is None:
        raise GoogleNotConnected()
    if account.status == "active":
        api = GoogleApi(session, account)
        for state in _states(session, account.id):
            if state.channel_id is not None:
                calendar_sync.stop_channel(api, state.channel_id, state.channel_resource_id)
    oauth.revoke_account_tokens(account)
    for store in (stores.calendar_store(), stores.task_store()):
        if store is not None:
            store.on_disconnect(session, user_id, keep_data)
    session.delete(account)  # CASCADE: trạng thái đồng bộ, hàng chờ, danh bạ (11 mục 3.15)
    session.flush()


# ---------- Worker ----------


def run_initial_sync(session: Session, job) -> dict:
    """Việc `google_initial_sync`: lần đầu kéo lịch, tạo kênh, tạo danh sách *Trợ lý*, đẩy việc sẵn có."""
    account = oauth.get_account(session, job.user_id)
    if account is None or account.status != "active":
        return {"skipped": True}
    result: dict = {}
    for state in _states(session, account.id):
        if state.initial_sync_state == "done":
            continue
        if not _store_ready(state.service):
            log.info("Chưa có store, để đồng bộ lần đầu chờ", extra={"service": state.service})
            continue
        state.initial_sync_state = "running"
        session.flush()
        try:
            if state.service == "calendar":
                state.sync_token = None
                result["events"] = calendar_sync.sync_calendar(session, account, state)
                calendar_sync.ensure_watch(session, account, state)
            elif state.service == "tasks":
                tasks_sync.ensure_tasklist(session, account, state)
                store = stores.task_store()
                if store is not None:
                    for task_id in store.list_unlinked(session, account.user_id):
                        outbox.enqueue(session, account.user_id, "tasks", "insert", "task", task_id)
                result["tasks"] = tasks_sync.pull_status(session, account, state)
            elif state.service == "gmail":
                state.history_id = None
                result["gmail"] = gmail.sync_gmail(session, account, state)
            state.initial_sync_state = "done"
        except Exception:
            state.initial_sync_state = "failed"
            state.status, state.last_error = "error", "Lấy dữ liệu lần đầu lỗi."
            session.flush()
            raise
    return result


def _store_ready(service: str) -> bool:
    if service == "calendar":
        return stores.calendar_store() is not None
    if service == "tasks":
        return stores.task_store() is not None
    if service == "gmail":
        return stores.mail_store() is not None
    return False


def _due_states(session: Session, service: str) -> list[GoogleSyncState]:
    if not _store_ready(service):
        log.info("Chưa có store cho dịch vụ Google, bỏ qua lượt đồng bộ", extra={"service": service})
        return []
    return list(
        session.scalars(
            select(GoogleSyncState)
            .join(GoogleAccount, GoogleAccount.id == GoogleSyncState.google_account_id)
            .where(
                GoogleSyncState.service == service,
                GoogleSyncState.initial_sync_state == "done",
                GoogleSyncState.next_sync_at <= clock.now(),
                GoogleAccount.status == "active",
            )
            .order_by(GoogleSyncState.next_sync_at)
            .limit(20)
        )
    )


def sync_due(session: Session, service: str, min_seconds: int) -> int:
    """Đồng bộ các tài nguyên tới hạn. Quét định kỳ cách nhau ít nhất min_seconds; webhook thì không."""
    done = 0
    for state in _due_states(session, service):
        if (
            not state.needs_sync
            and state.last_sync_at is not None
            and (clock.now() - state.last_sync_at).total_seconds() < min_seconds
        ):
            continue
        account = session.get(GoogleAccount, state.google_account_id)
        try:
            if service == "calendar":
                done += calendar_sync.sync_calendar(session, account, state)
            elif service == "gmail":
                done += gmail.sync_gmail(session, account, state)
            else:
                done += tasks_sync.pull_status(session, account, state)
            session.commit()
        except GoogleReauthRequired:
            session.rollback()
            oauth.persist_reauth(session, state.google_account_id)
            session.commit()
        except Exception as exc:
            session.rollback()
            state = session.get(GoogleSyncState, state.id)
            if state is not None:
                state.status, state.last_error = "error", type(exc).__name__
                state.next_sync_at = clock.now() + timedelta(minutes=calendar_sync.POLL_MINUTES)
                session.commit()
            log.warning("Đồng bộ Google lỗi", extra={"service": service, "error": type(exc).__name__})
    return done


def renew_watches(session: Session) -> int:
    renewed = 0
    states = session.scalars(
        select(GoogleSyncState)
        .join(GoogleAccount, GoogleAccount.id == GoogleSyncState.google_account_id)
        .where(GoogleSyncState.service == "calendar", GoogleAccount.status == "active")
    )
    for state in list(states):
        account = session.get(GoogleAccount, state.google_account_id)
        try:
            if calendar_sync.ensure_watch(session, account, state):
                renewed += 1
            session.commit()
        except Exception:
            session.rollback()
            log.warning("Gia hạn kênh Google lỗi", extra={"user_id": state.user_id})
    return renewed
