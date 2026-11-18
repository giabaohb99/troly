"""Đồng bộ Google Calendar hai chiều, Google làm gốc (40 mục 4).

Sự kiện lặp: bản gốc có `recurrence` cộng ngoại lệ, `singleEvents=false` (QĐ-26, K1).
Kéo về bằng syncToken; 410 thì xóa và đồng bộ đủ lại. Đẩy lên qua hàng chờ, `If-Match` theo etag;
412 thì lấy bản Google, giữ thay đổi của app để áp lại.
"""

import logging
import random
import secrets
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.security import same_hash, sha256_hex
from app.integrations.google import outbox, stores
from app.integrations.google.client import CALENDAR, GoogleApi
from app.integrations.google.errors import GoogleHttpError
from app.integrations.google.models import GoogleAccount, GoogleOutbox, GoogleSyncState
from app.integrations.google.settings import get_google_settings
from app.integrations.google.stores import LocalEvent, RemoteEvent

log = logging.getLogger("troly.google")

FULL_SYNC_DAYS_BACK = 30
POLL_MINUTES = 15
PAGE_SIZE = 2500
RENEW_BEFORE = timedelta(hours=48)
DEFAULT_TZ = "Asia/Ho_Chi_Minh"


# ---------- Chuyển đổi ----------


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_time(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _point(raw: dict | None) -> tuple[datetime | None, date | None]:
    raw = raw or {}
    if raw.get("date"):
        return None, date.fromisoformat(raw["date"])
    return parse_time(raw.get("dateTime")), None


def to_remote(item: dict) -> RemoteEvent:
    start_at, start_date = _point(item.get("start"))
    end_at, end_date = _point(item.get("end"))
    original = item.get("originalStartTime") or {}
    original_at, original_date = _point(original)
    reminders = item.get("reminders") or {}
    return RemoteEvent(
        google_event_id=item["id"],
        etag=item.get("etag"),
        updated=parse_time(item.get("updated")),
        status=item.get("status", "confirmed"),
        title=item.get("summary") or "",
        description=item.get("description"),
        location=item.get("location"),
        all_day=start_date is not None,
        start_at=start_at,
        end_at=end_at,
        start_date=start_date,
        end_date=end_date,
        timezone=(item.get("start") or {}).get("timeZone"),
        recurrence=item.get("recurrence"),
        recurring_event_id=item.get("recurringEventId"),
        original_start_at=original_at
        or (datetime.combine(original_date, datetime.min.time()) if original_date else None),
        attendees=[
            {
                "email": a.get("email"),
                "name": a.get("displayName"),
                "response_status": a.get("responseStatus"),
                "is_self": bool(a.get("self")),
            }
            for a in item.get("attendees") or []
        ],
        organizer_self=bool((item.get("organizer") or {}).get("self", True)),
        reminders_use_default=bool(reminders.get("useDefault", True)),
        reminder_minutes=[o.get("minutes", 0) for o in reminders.get("overrides") or []],
        html_link=item.get("htmlLink"),
    )


def to_google_body(event: LocalEvent, payload: dict) -> dict:
    tz = event.timezone or DEFAULT_TZ
    if event.all_day:
        start = {"date": event.start_date.isoformat()}
        end = {"date": event.end_date.isoformat()}
    else:
        start = {"dateTime": format_time(event.start_at), "timeZone": tz}
        end = {"dateTime": format_time(event.end_at or event.start_at), "timeZone": tz}
    body: dict = {
        "summary": event.title,
        "description": event.description,
        "location": event.location,
        "start": start,
        "end": end,
        "status": event.status if event.status in ("confirmed", "tentative") else "confirmed",
        "extendedProperties": {"private": {"troly_event_id": str(event.id)}},
    }
    if event.recurrence and not event.recurring_event_id:
        body["recurrence"] = event.recurrence
    if event.attendees:
        body["attendees"] = [{"email": a["email"]} for a in event.attendees if a.get("email")]
    # Một nguồn nhắc (40 mục 4.5): app nhắc thì Google im; Google nhắc thì chỉ gửi khi người dùng đổi nguồn.
    if event.remind_source == "app":
        body["reminders"] = {"useDefault": False, "overrides": []}
    elif payload.get("remind_source_changed"):
        body["reminders"] = {"useDefault": True}
    return body


def _send_params(payload: dict) -> dict:
    value = payload.get("send_updates")
    return {"sendUpdates": value} if value in ("all", "externalOnly") else {}


# ---------- Kéo về ----------


def _next_poll(now: datetime) -> datetime:
    return now + timedelta(minutes=POLL_MINUTES * random.uniform(0.75, 1.25))


def _require_store() -> stores.CalendarStore:
    store = stores.calendar_store()
    if store is None:
        raise RuntimeError("Module calendar chưa đăng ký store")
    return store


def sync_calendar(session: Session, account: GoogleAccount, state: GoogleSyncState) -> int:
    """Đồng bộ một lịch; trả số sự kiện đã xử lý. 410 thì xóa sự kiện nguồn Google và đồng bộ đủ lại."""
    store = _require_store()
    api = GoogleApi(session, account)
    full = state.sync_token is None
    try:
        count, token = _pull(session, api, store, account, state, full)
    except GoogleHttpError as exc:
        if exc.status != 410:
            raise
        log.info("syncToken hết hạn, đồng bộ đủ lại", extra={"user_id": account.user_id})
        keep = set(
            session.scalars(
                select(GoogleOutbox.local_id).where(
                    GoogleOutbox.user_id == account.user_id,
                    GoogleOutbox.local_type == "event",
                    GoogleOutbox.status.in_(("pending", "processing")),
                )
            )
        )
        store.delete_remote_rows(session, account.user_id, account.id, keep)
        state.sync_token = None
        full = True
        count, token = _pull(session, api, store, account, state, full=True)
    now = clock.now()
    state.sync_token = token
    state.last_sync_at = now
    if full:
        state.last_full_sync_at = now
    state.needs_sync = False
    state.next_sync_at = _next_poll(now)
    state.status, state.last_error = "ok", None
    session.flush()
    return count


def _pull(
    session: Session,
    api: GoogleApi,
    store: stores.CalendarStore,
    account: GoogleAccount,
    state: GoogleSyncState,
    full: bool,
) -> tuple[int, str | None]:
    calendar_id = state.resource_id or "primary"
    base: dict = {"singleEvents": "false", "showDeleted": "true", "maxResults": PAGE_SIZE}
    if full:
        base["timeMin"] = format_time(clock.now() - timedelta(days=FULL_SYNC_DAYS_BACK))
    else:
        base = {"singleEvents": "false", "syncToken": state.sync_token, "maxResults": PAGE_SIZE}
    count, page_token = 0, None
    while True:
        params = dict(base)
        if page_token:
            params["pageToken"] = page_token
        data = api.request("GET", f"{CALENDAR}/calendars/{calendar_id}/events", params=params)
        for item in data.get("items", []):
            apply_item(session, store, account, calendar_id, item)
            count += 1
        page_token = data.get("nextPageToken")
        if not page_token:
            return count, data.get("nextSyncToken")


def apply_item(
    session: Session, store: stores.CalendarStore, account: GoogleAccount, calendar_id: str, item: dict
) -> None:
    remote = to_remote(item)
    user_id = account.user_id
    local = store.find_by_google_id(session, user_id, calendar_id, remote.google_event_id)
    waiting = outbox.waiting_row(session, "event", local.id) if local else None
    if remote.status == "cancelled":
        if local is not None:
            if waiting is not None and waiting.status == "pending":
                waiting.status, waiting.last_error = "failed", "Sự kiện đã bị xóa trên Google."
            store.mark_remote_cancelled(session, user_id, local.id)
        elif remote.recurring_event_id:
            store.write_remote(session, user_id, account.id, calendar_id, remote, None)  # ngoại lệ hủy
        return
    if local is not None and local.etag and local.etag == remote.etag:
        return  # tiếng vọng của lần ghi từ app
    if waiting is not None and waiting.status == "pending":
        outbox.mark_conflict(waiting, store.snapshot(session, user_id, local.id))
    store.write_remote(session, user_id, account.id, calendar_id, remote, local.id if local else None)


# ---------- Đẩy lên ----------


def push_event(session: Session, account: GoogleAccount, row: GoogleOutbox) -> None:
    store = _require_store()
    user_id = account.user_id
    event = store.get_for_push(session, user_id, row.local_id)
    if event is None:
        return
    api = GoogleApi(session, account)
    calendar_id = event.google_calendar_id or "primary"
    url = f"{CALENDAR}/calendars/{calendar_id}/events"
    payload = row.payload or {}
    params = _send_params(payload)

    if event.recurring_event_id and not event.google_etag:
        _resolve_instance(api, url, event)

    if event.deleted:
        if not event.google_etag or not event.google_event_id:
            return  # chưa từng lên Google
        try:
            api.request(
                "DELETE",
                f"{url}/{event.google_event_id}",
                params=params,
                headers={"If-Match": event.google_etag},
                ok=(200, 204),
            )
        except GoogleHttpError as exc:
            if exc.status in (404, 410):
                return
            if exc.status == 412:
                _take_google(session, api, store, account, calendar_id, url, event, {"deleted": True})
            raise
        return

    body = to_google_body(event, payload)
    if not event.google_etag:
        google_id = event.google_event_id or outbox.new_event_id()
        try:
            data = api.request("POST", url, params=params, json={**body, "id": google_id})
        except GoogleHttpError as exc:
            if exc.status != 409:
                raise
            data = api.request("GET", f"{url}/{google_id}")  # đã tạo ở lần gửi trước
        store.save_push_result(
            session, user_id, event.id, data["id"], data.get("etag"), parse_time(data.get("updated"))
        )
        return
    try:
        data = api.request(
            "PATCH",
            f"{url}/{event.google_event_id}",
            params=params,
            json=body,
            headers={"If-Match": event.google_etag},
        )
    except GoogleHttpError as exc:
        if exc.status in (404, 410):
            store.mark_remote_cancelled(session, user_id, event.id)
            return
        if exc.status == 412:
            _take_google(session, api, store, account, calendar_id, url, event, None)
        raise
    store.save_push_result(
        session, user_id, event.id, data["id"], data.get("etag"), parse_time(data.get("updated"))
    )


def _resolve_instance(api: GoogleApi, url: str, event: LocalEvent) -> None:
    """Ngoại lệ tạo trong app: tra id của lần lặp bằng events.instances quanh giờ gốc (40 mục 4.2)."""
    at = event.original_start_at
    data = api.request(
        "GET",
        f"{url}/{event.recurring_event_id}/instances",
        params={
            "timeMin": format_time(at - timedelta(minutes=1)),
            "timeMax": format_time(at + timedelta(minutes=1)),
        },
    )
    items = data.get("items") or []
    if not items:
        raise GoogleHttpError(404, "instanceNotFound")
    event.google_event_id = items[0]["id"]
    event.google_etag = items[0].get("etag")


def _take_google(
    session: Session,
    api: GoogleApi,
    store: stores.CalendarStore,
    account: GoogleAccount,
    calendar_id: str,
    url: str,
    event: LocalEvent,
    extra: dict | None,
) -> None:
    """412: Google làm gốc. Ghi bản Google vào app, ném PushConflict kèm thay đổi bị bỏ."""
    snapshot = {**store.snapshot(session, account.user_id, event.id), **(extra or {})}
    item = api.request("GET", f"{url}/{event.google_event_id}")
    store.write_remote(session, account.user_id, account.id, calendar_id, to_remote(item), event.id)
    raise outbox.PushConflict(snapshot)


# ---------- Kênh thông báo ----------


def ensure_watch(session: Session, account: GoogleAccount, state: GoogleSyncState) -> bool:
    """Tạo kênh mới nếu chưa có hoặc còn dưới 48 giờ; dừng kênh cũ. Máy dựng (http) thì bỏ qua."""
    address = get_google_settings().webhook_url
    if address is None:
        return False
    now = clock.now()
    if state.channel_id and state.channel_expires_at and state.channel_expires_at - RENEW_BEFORE > now:
        return False
    api = GoogleApi(session, account)
    channel_id = uuid.uuid4()
    token = secrets.token_urlsafe(32)
    data = api.request(
        "POST",
        f"{CALENDAR}/calendars/{state.resource_id or 'primary'}/events/watch",
        json={"id": str(channel_id), "type": "web_hook", "address": address, "token": token},
    )
    old_id, old_resource = state.channel_id, state.channel_resource_id
    state.channel_id = channel_id
    state.channel_resource_id = data.get("resourceId")
    state.channel_token_hash = sha256_hex(token)
    expiration = data.get("expiration")
    state.channel_expires_at = (
        datetime.fromtimestamp(int(expiration) / 1000, tz=now.tzinfo)
        if expiration
        else now + timedelta(days=7)
    )
    session.flush()
    if old_id is not None:
        stop_channel(api, old_id, old_resource)
    return True


def stop_channel(api: GoogleApi, channel_id: uuid.UUID, resource_id: str | None) -> None:
    try:
        api.request(
            "POST",
            f"{CALENDAR}/channels/stop",
            json={"id": str(channel_id), "resourceId": resource_id},
            ok=(200, 204),
        )
    except Exception:
        log.info("Dừng kênh Google không được, bỏ qua", extra={"channel_id": str(channel_id)})


def handle_webhook(
    session: Session, channel_id: str | None, token: str | None, resource_state: str | None
) -> bool:
    """Webhook chỉ đặt cờ; trả True khi kênh và token khớp (12 mục 5.6)."""
    try:
        cid = uuid.UUID(channel_id or "")
    except ValueError:
        return False
    state = session.scalar(select(GoogleSyncState).where(GoogleSyncState.channel_id == cid))
    if state is None or not token or not same_hash(state.channel_token_hash or "", sha256_hex(token)):
        return False
    if resource_state == "sync":
        return True
    soon = clock.now() + timedelta(seconds=10)  # gộp thông báo dồn trong 10 giây
    state.needs_sync = True
    if state.next_sync_at is None or state.next_sync_at > soon:
        state.next_sync_at = soon
    session.flush()
    return True
