"""Lịch (11 mục 3.11, 12 mục 5.5). Google Calendar làm gốc; máy chủ tự trải lần lặp (K1, QĐ-26).

Sự kiện lặp chỉ đến từ Google: app không sửa, xóa cả chuỗi (`RECURRING_SERIES_EDIT`), chỉ sửa một lần
bằng dòng ngoại lệ (`recurring_event_id`, `original_start_at`). Có khách mời thì phải duyệt (QĐ-23).
Ghi sang Google qua `integrations.google.outbox.enqueue` cùng giao dịch.
"""

import hashlib
import json
import logging
import re
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from app.core import clock
from app.core.context import UserContext
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.calendar.models import Event
from app.modules.setting import service as setting_service

log = logging.getLogger("troly.calendar")

MAX_RANGE_DAYS = 92
MAX_OCCURRENCES = 500
MAX_ATTENDEES = 50
UNDO_DAYS = 30
# Đổi các trường này không cần duyệt, kể cả trên bản gốc sự kiện lặp (chỉ ảnh hưởng nhắc trên máy).
LOCAL_FIELDS = frozenset({"remind_minutes", "is_alarm", "remind_source"})
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RecurringSeriesEdit(ConflictError):
    code = "RECURRING_SERIES_EDIT"
    message = "Đây là sự kiện lặp: sửa hoặc xóa cả chuỗi trên Google Calendar, trong app chỉ sửa từng lần."


# ---------- Google (tùy chọn) ----------


def _outbox():
    try:
        from app.integrations.google import outbox
    except ModuleNotFoundError:
        return None
    return outbox


def new_google_event_id() -> str | None:
    ob = _outbox()
    return ob.new_event_id() if ob else None


def enqueue(session: Session, user_id: int, op: str, e: Event, payload: dict | None = None) -> bool:
    ob = _outbox()
    queued = bool(ob) and ob.enqueue(session, user_id, "calendar", op, "event", e.id, payload)
    if queued:
        e.sync_status = "pending"
    elif e.google_etag is None:
        e.sync_status = "local_only"
    return queued


# ---------- Thời gian ----------


def _zone(name: str | None, fallback: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or fallback)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(fallback)


def _utc(at: datetime) -> datetime:
    return (at if at.tzinfo else at.replace(tzinfo=UTC)).astimezone(UTC)


def _date_key(d: date) -> datetime:
    """Khóa lần lặp cả ngày: 00:00 UTC của ngày đó (giống `original_start_at` Google gửi về)."""
    return datetime.combine(d, time.min, tzinfo=UTC)


def _normalize_rules(lines: list[str] | None, all_day: bool) -> str:
    out = []
    for line in lines or []:
        name = line.split(":", 1)[0].split(";", 1)[0].upper()
        if name not in ("RRULE", "EXRULE", "RDATE", "EXDATE"):
            continue
        if name in ("RRULE", "EXRULE"):
            if all_day:
                line = re.sub(r"(UNTIL=\d{8})T\d{6}Z?", r"\1", line)
            else:
                line = re.sub(r"UNTIL=(\d{8})(?=;|$)", r"UNTIL=\1T235959Z", line)
        out.append(line)
    return "\n".join(out)


def _span(e: Event) -> timedelta:
    if e.all_day:
        return timedelta(days=(e.end_date - e.start_date).days)
    return e.end_at - e.start_at


def expand_starts(master: Event, lo: datetime, hi: datetime, user_tz: str) -> list[datetime | date]:
    """Giờ bắt đầu các lần lặp của bản gốc có phần nằm trong [lo, hi). Cả ngày trả `date`."""
    rules = _normalize_rules(master.recurrence, master.all_day)
    if not rules:
        return []
    tz = _zone(master.timezone, user_tz)
    span = _span(master)
    if master.all_day:
        dtstart = datetime.combine(master.start_date, time.min)
        lo_d, hi_d = lo.astimezone(tz).date(), (hi - timedelta(microseconds=1)).astimezone(tz).date()
        a, b = datetime.combine(lo_d, time.min) - span, datetime.combine(hi_d, time.min)
    else:
        dtstart = master.start_at.astimezone(tz)
        a, b = lo - span, hi
    try:
        rs = rrulestr(rules, dtstart=dtstart, forceset=True, tzids=ZoneInfo)
        starts = rs.between(a, b, inc=True)[:MAX_OCCURRENCES]
    except (ValueError, TypeError):
        log.warning("Không trải được luật lặp", extra={"event_id": master.id})
        return []
    if master.all_day:
        return [s.date() for s in starts if s.date() + span > lo_d and s.date() <= hi_d]
    return [s for s in starts if s < hi and (s + span > lo or (span == timedelta(0) and s >= lo))]


def _overlaps(e: Event, lo: datetime, hi: datetime, tz: str) -> bool:
    if e.all_day:
        zone = ZoneInfo(tz)
        lo_d, hi_d = lo.astimezone(zone).date(), (hi - timedelta(microseconds=1)).astimezone(zone).date()
        return e.start_date <= hi_d and e.end_date > lo_d
    return e.start_at < hi and (e.end_at > lo or (e.end_at == e.start_at and e.start_at >= lo))


def _sort_key(item: dict, tz: str) -> datetime:
    if item["all_day"]:
        return datetime.combine(item["start_date"], time.min, tzinfo=ZoneInfo(tz))
    return item["start_at"]


# ---------- Trả API ----------


def serialize(
    e: Event,
    *,
    display_id: int | None = None,
    occurrence_start: datetime | None = None,
    is_recurring: bool = False,
    times: dict | None = None,
) -> dict:
    times = times or {}
    return {
        "id": display_id or e.id,
        "occurrence_start": occurrence_start,
        "is_recurring": is_recurring,
        "title": e.title,
        "description": e.description,
        "location": e.location,
        "all_day": e.all_day,
        "start_at": times.get("start_at", e.start_at),
        "end_at": times.get("end_at", e.end_at),
        "start_date": times.get("start_date", e.start_date),
        "end_date": times.get("end_date", e.end_date),
        "status": e.status,
        "remind_minutes": list(e.remind_minutes or []),
        "remind_source": e.remind_source,
        "is_alarm": e.is_alarm,
        "is_organizer": e.is_organizer is not False,
        "attendees": e.attendees or [],
        "source": e.source,
        "task_id": e.task_id,
        "sync_status": e.sync_status,
        "google_html_link": e.google_html_link,
        "meet_url": e.meet_url,
    }


def _occurrence_times(master: Event, start: datetime | date) -> tuple[datetime, dict]:
    span = _span(master)
    if master.all_day:
        return _date_key(start), {
            "start_date": start,
            "end_date": start + span,
            "start_at": None,
            "end_at": None,
        }
    return _utc(start), {"start_at": _utc(start), "end_at": _utc(start) + span}


def _visible(e: Event) -> bool:
    return e.deleted_at is None and e.status != "cancelled"


def collect(session: Session, user: UserContext, lo: datetime, hi: datetime) -> list[tuple[Event, dict]]:
    """Mọi lần xuất hiện trong [lo, hi): (dòng chứa nội dung, dict đã serialize)."""
    tz = user.timezone
    base = select(Event).where(Event.user_id == user.user_id)
    singles = session.scalars(
        base.where(
            Event.deleted_at.is_(None),
            Event.status != "cancelled",
            Event.recurrence.is_(None),
            Event.recurring_event_id.is_(None),
            or_(
                and_(Event.all_day.is_(False), Event.start_at < hi, Event.end_at >= lo),
                and_(
                    Event.all_day.is_(True),
                    Event.start_date <= hi.date() + timedelta(days=1),
                    Event.end_date >= lo.date() - timedelta(days=1),
                ),
            ),
        )
    ).all()
    out = [(e, serialize(e)) for e in singles if _overlaps(e, lo, hi, tz)]

    masters = session.scalars(
        base.where(Event.deleted_at.is_(None), Event.status != "cancelled", Event.recurrence.is_not(None))
    ).all()
    ids = [m.google_event_id for m in masters if m.google_event_id]
    exceptions: dict[tuple[str, datetime], Event] = {}
    if ids:
        for x in session.scalars(base.where(Event.recurring_event_id.in_(ids))):
            if x.original_start_at is not None:
                exceptions[(x.recurring_event_id, _utc(x.original_start_at))] = x
    used: set[int] = set()
    for m in masters:
        for start in expand_starts(m, lo, hi, tz):
            key, times = _occurrence_times(m, start)
            x = exceptions.get((m.google_event_id, key))
            if x is not None:
                used.add(x.id)
                if _visible(x) and _overlaps(x, lo, hi, tz):
                    out.append((x, serialize(x, display_id=m.id, occurrence_start=key, is_recurring=True)))
                continue
            out.append(
                (m, serialize(m, display_id=m.id, occurrence_start=key, is_recurring=True, times=times))
            )
    by_google = {m.google_event_id: m for m in masters}
    for (gid, key), x in exceptions.items():
        # Lần lặp dời vào khoảng đang xem từ ngoài khoảng.
        if x.id not in used and _visible(x) and _overlaps(x, lo, hi, tz) and gid in by_google:
            out.append(
                (x, serialize(x, display_id=by_google[gid].id, occurrence_start=key, is_recurring=True))
            )
    # Ngoại lệ mồ côi (bản gốc chưa về hoặc đã xóa): hiện như sự kiện đơn.
    orphans = session.scalars(
        base.where(
            Event.recurring_event_id.is_not(None),
            Event.deleted_at.is_(None),
            Event.status != "cancelled",
            Event.recurring_event_id.not_in(ids) if ids else Event.id.is_not(None),
        )
    ).all()
    out.extend((x, serialize(x)) for x in orphans if _overlaps(x, lo, hi, tz))
    out.sort(key=lambda pair: (_sort_key(pair[1], tz), pair[1]["id"]))
    return out


def list_events(session: Session, user: UserContext, start: datetime, end: datetime) -> list[dict]:
    if end <= start:
        raise ValidationError(fields={"to": "`to` phải sau `from`."})
    if end - start > timedelta(days=MAX_RANGE_DAYS):
        raise ValidationError(fields={"to": f"Xem tối đa {MAX_RANGE_DAYS} ngày một lần."})
    return [item for _, item in collect(session, user, start, end)]


def _get(session: Session, user_id: int, event_id: int, include_deleted: bool = False) -> Event:
    stmt = select(Event).where(Event.id == event_id, Event.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(Event.deleted_at.is_(None))
    e = session.scalar(stmt)
    if e is None:
        raise NotFoundError("Không tìm thấy sự kiện.")
    return e


def _exception_for(
    session: Session, user: UserContext, master: Event, occurrence_start: datetime, create: bool
) -> tuple[Event | None, dict]:
    key = _utc(occurrence_start)
    starts = expand_starts(
        master, key - timedelta(minutes=1), key + timedelta(days=1, minutes=1), user.timezone
    )
    match = next((s for s in starts if _occurrence_times(master, s)[0] == key), None)
    if match is None:
        raise NotFoundError("Không có lần lặp này.")
    _, times = _occurrence_times(master, match)
    x = session.scalar(
        select(Event).where(
            Event.user_id == user.user_id,
            Event.recurring_event_id == master.google_event_id,
            Event.original_start_at == key,
        )
    )
    if x is None and create:
        x = Event(
            user_id=user.user_id,
            title=master.title,
            description=master.description,
            location=master.location,
            all_day=master.all_day,
            timezone=master.timezone,
            status="confirmed",
            recurring_event_id=master.google_event_id,
            original_start_at=key,
            attendees=master.attendees or [],
            remind_minutes=list(master.remind_minutes or []),
            remind_source=master.remind_source,
            is_alarm=master.is_alarm,
            is_organizer=master.is_organizer,
            source=master.source,
            google_account_id=master.google_account_id,
            google_calendar_id=master.google_calendar_id,
            google_html_link=master.google_html_link,
            meet_url=master.meet_url,
            sync_status="local_only",
            **times,
        )
        session.add(x)
        session.flush()
    return x, times


def get_event(
    session: Session, user: UserContext, event_id: int, occurrence_start: datetime | None = None
) -> dict:
    e = _get(session, user.user_id, event_id)
    if e.recurrence and occurrence_start is not None:
        x, times = _exception_for(session, user, e, occurrence_start, create=False)
        key = _utc(occurrence_start)
        if x is not None:
            return serialize(x, display_id=e.id, occurrence_start=key, is_recurring=True)
        return serialize(e, display_id=e.id, occurrence_start=key, is_recurring=True, times=times)
    return serialize(e, is_recurring=bool(e.recurrence))


# ---------- Ghi ----------


def _attendees(raw: list | None) -> list[dict]:
    out, seen = [], set()
    for a in raw or []:
        email = (a.get("email") if isinstance(a, dict) else str(a) or "").strip().lower()
        if not _EMAIL.match(email):
            raise ValidationError(fields={"attendees": f"Email không hợp lệ: {email or '(trống)'}."})
        if email in seen:
            continue
        seen.add(email)
        out.append(
            {
                "email": email,
                "name": (a.get("name") if isinstance(a, dict) else None),
                "response_status": (a.get("response_status") if isinstance(a, dict) else None)
                or "needsAction",
                "is_self": bool(a.get("is_self")) if isinstance(a, dict) else False,
            }
        )
    if len(out) > MAX_ATTENDEES:
        raise ValidationError(fields={"attendees": f"Tối đa {MAX_ATTENDEES} khách."})
    return out


def _times(data: dict) -> dict:
    """Kiểm giờ theo CK của tab_event; thiếu giờ kết thúc thì mặc định 1 giờ (cả ngày: 1 ngày)."""
    if data.get("all_day"):
        start = data.get("start_date")
        if start is None:
            raise ValidationError(fields={"start_date": "Sự kiện cả ngày cần ngày bắt đầu."})
        end = data.get("end_date") or start + timedelta(days=1)
        if end <= start:
            raise ValidationError(
                fields={"end_date": "Ngày kết thúc phải sau ngày bắt đầu (không tính ngày cuối)."}
            )
        return {"all_day": True, "start_date": start, "end_date": end, "start_at": None, "end_at": None}
    start = data.get("start_at")
    if start is None:
        raise ValidationError(fields={"start_at": "Cần giờ bắt đầu."})
    if start.tzinfo is None:
        raise ValidationError(fields={"start_at": "Giờ cần có múi giờ."})
    end = data.get("end_at") or start + timedelta(hours=1)
    if end < start:
        raise ValidationError(fields={"end_at": "Giờ kết thúc phải sau giờ bắt đầu."})
    return {"all_day": False, "start_at": start, "end_at": end, "start_date": None, "end_date": None}


def _remind_minutes(session: Session, user_id: int, value) -> list[int]:
    if value is None:
        return list(setting_service.get_value(session, user_id, "calendar.default_remind_minutes"))
    minutes = sorted({int(m) for m in value})
    if len(minutes) > 5 or any(m < 0 or m > 40320 for m in minutes):
        raise ValidationError(fields={"remind_minutes": "Tối đa 5 mốc, mỗi mốc từ 0 tới 40320 phút."})
    return minutes


def _default_safe_minutes(session: Session, user_id: int, value, times: dict) -> list[int]:
    """Không chỉ định phút nhắc mà mốc mặc định đã qua (sự kiện *3 phút nữa*): nhắc thêm đúng giờ (0)."""
    minutes = _remind_minutes(session, user_id, value)
    if value is None and not times["all_day"]:
        now = clock.now()
        future = [m for m in minutes if times["start_at"] - timedelta(minutes=m) > now]
        if times["start_at"] > now and len(future) < len(minutes):
            minutes = future or [0]
    return minutes


def _jsonable(data: dict) -> dict:
    return json.loads(json.dumps(data, default=lambda v: v.isoformat()))


def _parse_json_times(data: dict) -> dict:
    out = dict(data)
    for key in ("start_at", "end_at"):
        if isinstance(out.get(key), str):
            out[key] = datetime.fromisoformat(out[key])
    for key in ("start_date", "end_date"):
        if isinstance(out.get(key), str):
            out[key] = date.fromisoformat(out[key])
    return out


def _when_text(data: dict, tz: str) -> str:
    if data.get("all_day"):
        return f"Cả ngày {data['start_date']:%d/%m/%Y}"
    return f"{clock.to_local(data['start_at'], tz):%H:%M %d/%m/%Y}"


def _ask(
    session: Session,
    user: UserContext,
    tool_name: str,
    input_: dict,
    title: str,
    event: dict,
    guests: list[dict],
    conversation_id: int | None = None,
) -> dict:
    from app.modules.chat import service as chat_service

    details = [
        {"label": "Sự kiện", "value": event.get("title") or ""},
        {"label": "Khách", "value": ", ".join(g["email"] for g in guests) or "(không)"},
    ]
    if event.get("start_at") or event.get("start_date"):
        details.insert(1, {"label": "Thời gian", "value": _when_text(event, user.timezone)})
    return chat_service.create_pending_action(
        session,
        user.user_id,
        tool_name,
        _jsonable(input_),
        title=title,
        summary="Google sẽ gửi email cho khách sau khi duyệt.",
        details=details,
        danger=tool_name == "delete_event",
        conversation_id=conversation_id,
    )


def create_event(
    session: Session,
    user: UserContext,
    data: dict,
    *,
    approved: bool = False,
    conversation_id: int | None = None,
    task_id: int | None = None,
) -> dict:
    """`data`: title, description, location, all_day, start_at, end_at, start_date, end_date,
    remind_minutes, is_alarm, attendees. Có khách mà chưa duyệt thì trả `{pending_action}`."""
    data = _parse_json_times(data)
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError(fields={"title": "Nhập tên sự kiện."})
    times = _times(data)
    guests = _attendees(data.get("attendees"))
    if guests and not approved:
        draft = {**data, **times, "title": title}
        return {
            "pending_action": _ask(
                session,
                user,
                "add_event",
                {"data": data},
                "Tạo sự kiện có khách mời",
                draft,
                guests,
                conversation_id=conversation_id,
            )
        }
    e = Event(
        user_id=user.user_id,
        title=title[:1024],
        description=data.get("description"),
        location=data.get("location"),
        timezone=user.timezone,
        status="confirmed",
        attendees=guests,
        remind_minutes=_default_safe_minutes(session, user.user_id, data.get("remind_minutes"), times),
        remind_source="app",
        is_alarm=bool(data.get("is_alarm")),
        source="app",
        task_id=task_id,
        google_calendar_id="primary",
        google_event_id=new_google_event_id(),
        sync_status="local_only",
        **times,
    )
    session.add(e)
    session.flush()
    payload = {"send_updates": "all"} if guests else {}
    if data.get("meet"):
        payload["meet"] = True  # integrations gửi conferenceData.createRequest (hangoutsMeet)
    enqueue(session, user.user_id, "insert", e, payload or None)
    return {"event": serialize(e)}


def _sync_task(session: Session, e: Event) -> None:
    """Sự kiện của việc có giờ: giữ hạn và tên việc khớp (bảng của task, không import model)."""
    if e.task_id is None or e.all_day:
        return
    session.execute(
        text(
            "UPDATE tab_task SET due_at = :at, title = :title, updated_at = now() WHERE id = :tid AND event_id = :eid"
        ),
        {"at": e.start_at, "title": e.title, "tid": e.task_id, "eid": e.id},
    )


def update_event(
    session: Session,
    user: UserContext,
    event_id: int,
    changes: dict,
    *,
    occurrence_start: datetime | None = None,
    approved: bool = False,
    conversation_id: int | None = None,
) -> dict:
    changes = _parse_json_times({k: v for k, v in changes.items()})
    row = _get(session, user.user_id, event_id)
    if isinstance(occurrence_start, str):
        occurrence_start = datetime.fromisoformat(occurrence_start)
    want_meet = bool(changes.pop("meet", False))
    content_changes = set(changes) - LOCAL_FIELDS
    if want_meet:
        content_changes.add("meet")
    if row.recurrence and occurrence_start is None and content_changes:
        raise RecurringSeriesEdit(data={"google_html_link": row.google_html_link})
    if row.is_organizer is False and content_changes:
        raise ConflictError(
            "Sự kiện người khác mời: trong app chỉ đổi được nhắc.", code="EVENT_NOT_ORGANIZER"
        )
    guests = _attendees(changes["attendees"]) if "attendees" in changes else (row.attendees or [])
    if (guests or row.attendees) and content_changes and not approved:
        draft = {
            "title": changes.get("title", row.title),
            **{k: changes[k] for k in changes if k in ("start_at", "start_date", "all_day")},
        }
        if "start_at" not in draft and "start_date" not in draft:
            draft.update(all_day=row.all_day, start_at=row.start_at, start_date=row.start_date)
        return {
            "pending_action": _ask(
                session,
                user,
                "update_event",
                {
                    "event_id": event_id,
                    "occurrence_start": occurrence_start,
                    "changes": {**changes, **({"meet": True} if want_meet else {})},
                },
                "Sửa sự kiện có khách mời",
                draft,
                guests,
                conversation_id=conversation_id,
            )
        }
    target = row
    if row.recurrence and occurrence_start is not None:
        target, _ = _exception_for(session, user, row, occurrence_start, create=True)
    if {"all_day", "start_at", "end_at", "start_date", "end_date"} & set(changes):
        merged = {
            "all_day": changes.get("all_day", target.all_day),
            "start_at": changes.get("start_at", target.start_at),
            "end_at": changes.get("end_at", target.end_at),
            "start_date": changes.get("start_date", target.start_date),
            "end_date": changes.get("end_date", target.end_date),
        }
        if "start_at" in changes and "end_at" not in changes and target.start_at and target.end_at:
            merged["end_at"] = changes["start_at"] + (target.end_at - target.start_at)
        if "start_date" in changes and "end_date" not in changes and target.start_date:
            merged["end_date"] = changes["start_date"] + (target.end_date - target.start_date)
        for key, value in _times(merged).items():
            setattr(target, key, value)
    if "title" in changes:
        title = (changes["title"] or "").strip()
        if not title:
            raise ValidationError(fields={"title": "Nhập tên sự kiện."})
        target.title = title[:1024]
    for key in ("description", "location"):
        if key in changes:
            setattr(target, key, changes[key])
    if "attendees" in changes:
        target.attendees = guests
    reminders_changed = alarm_changed = False
    if "remind_minutes" in changes:
        new_minutes = _remind_minutes(session, user.user_id, changes["remind_minutes"])
        reminders_changed = new_minutes != list(target.remind_minutes or [])
        target.remind_minutes = new_minutes
    if "is_alarm" in changes:
        alarm_changed = bool(changes["is_alarm"]) != bool(target.is_alarm)
        target.is_alarm = bool(changes["is_alarm"])
    source_changed = "remind_source" in changes and changes["remind_source"] != target.remind_source
    if source_changed:
        if changes["remind_source"] not in ("app", "google"):
            raise ValidationError(fields={"remind_source": "Nguồn nhắc là app hoặc google."})
        target.remind_source = changes["remind_source"]
    if target.recurrence and LOCAL_FIELDS & set(changes):
        # Nhắc của cả chuỗi áp cho mọi lần lặp, kể cả lần đã sửa riêng.
        for x in session.scalars(
            select(Event).where(
                Event.user_id == user.user_id, Event.recurring_event_id == target.google_event_id
            )
        ):
            x.remind_source, x.remind_minutes, x.is_alarm = (
                target.remind_source,
                target.remind_minutes,
                target.is_alarm,
            )
    session.flush()
    _sync_task(session, target)
    if content_changes or source_changed:
        payload = {}
        if target.attendees:
            payload["send_updates"] = "all"
        if want_meet and not target.meet_url:
            payload["meet"] = True
        if source_changed:
            payload["remind_source_changed"] = True
        if reminders_changed and target.remind_source == "google":
            payload["reminders_changed"] = True
        enqueue(session, user.user_id, "patch", target, payload or None)
    elif (reminders_changed and target.remind_source == "google") or alarm_changed:
        # QĐ-39: Google nhắc thì phút nhắc lên Google (popup); cờ báo thức giữ trên Google để đồng bộ lại
        # (410) không mất. Không cần duyệt.
        payload = (
            {"reminders_changed": True} if reminders_changed and target.remind_source == "google" else None
        )
        enqueue(session, user.user_id, "patch", target, payload)
    if target is not row:
        return serialize(
            target, display_id=row.id, occurrence_start=_utc(occurrence_start), is_recurring=True
        )
    return serialize(target, is_recurring=bool(target.recurrence))


def delete_event(
    session: Session,
    user: UserContext,
    event_id: int,
    *,
    occurrence_start: datetime | None = None,
    approved: bool = False,
    conversation_id: int | None = None,
) -> dict | None:
    row = _get(session, user.user_id, event_id)
    if isinstance(occurrence_start, str):
        occurrence_start = datetime.fromisoformat(occurrence_start)
    if row.recurrence and occurrence_start is None:
        raise RecurringSeriesEdit(data={"google_html_link": row.google_html_link})
    if row.attendees and not approved:
        draft = {
            "title": row.title,
            "all_day": row.all_day,
            "start_at": row.start_at,
            "start_date": row.start_date,
        }
        return {
            "pending_action": _ask(
                session,
                user,
                "delete_event",
                {"event_id": event_id, "occurrence_start": occurrence_start},
                "Xóa sự kiện có khách mời",
                draft,
                row.attendees,
                conversation_id=conversation_id,
            )
        }
    payload = {"send_updates": "all"} if row.attendees else None
    if row.recurrence:
        x, _ = _exception_for(session, user, row, occurrence_start, create=True)
        x.status = "cancelled"
        session.flush()
        enqueue(session, user.user_id, "delete", x, payload)
        return None
    row.deleted_at = clock.now()
    if row.task_id is not None:
        session.execute(
            text(
                "UPDATE tab_task SET event_id = NULL, updated_at = now() WHERE id = :tid AND event_id = :eid"
            ),
            {"tid": row.task_id, "eid": row.id},
        )
    session.flush()
    enqueue(session, user.user_id, "delete", row, payload)
    return None


def restore_event(session: Session, user: UserContext, event_id: int) -> dict:
    e = _get(session, user.user_id, event_id, include_deleted=True)
    if e.deleted_at is None:
        return serialize(e, is_recurring=bool(e.recurrence))
    if e.deleted_at < clock.now() - timedelta(days=UNDO_DAYS):
        raise NotFoundError("Sự kiện đã xóa quá 30 ngày, không khôi phục được.")
    e.deleted_at = None
    if e.source == "app":
        # Bản trên Google đã bị xóa: tạo lại với id mới.
        e.google_event_id, e.google_etag, e.google_updated_at = new_google_event_id(), None, None
        session.flush()
        enqueue(session, user.user_id, "insert", e, {"send_updates": "all"} if e.attendees else None)
    session.flush()
    return serialize(e, is_recurring=bool(e.recurrence))


# ---------- Cho module task (việc có giờ sinh sự kiện) ----------


def create_task_event(
    session: Session,
    user: UserContext,
    task_id: int,
    title: str,
    due_at: datetime,
    remind_minutes: list[int] | None,
) -> int:
    out = create_event(
        session,
        user,
        {"title": title, "start_at": due_at, "end_at": due_at, "remind_minutes": remind_minutes},
        task_id=task_id,
    )
    return out["event"]["id"]


def update_task_event(
    session: Session,
    user: UserContext,
    event_id: int,
    *,
    title: str | None = None,
    due_at: datetime | None = None,
    remind_minutes: list[int] | None = None,
) -> None:
    e = session.scalar(select(Event).where(Event.id == event_id, Event.user_id == user.user_id))
    if e is None or e.deleted_at is not None:
        return
    changed = False
    if title is not None and title != e.title:
        e.title, changed = title[:1024], True
    if due_at is not None and due_at != e.start_at:
        e.start_at, e.end_at, changed = due_at, due_at, True
    if remind_minutes is not None:
        e.remind_minutes = _remind_minutes(session, user.user_id, remind_minutes)
    session.flush()
    if changed:
        enqueue(session, user.user_id, "patch", e)


def delete_task_event(session: Session, user: UserContext, event_id: int) -> None:
    e = session.scalar(select(Event).where(Event.id == event_id, Event.user_id == user.user_id))
    if e is None or e.deleted_at is not None:
        return
    e.deleted_at = clock.now()
    session.flush()
    enqueue(session, user.user_id, "delete", e)


# ---------- Nhắc trên máy (12 mục 5.5) ----------


def list_reminders(session: Session, user: UserContext, start: datetime, days: int) -> dict:
    """Chỉ sự kiện `remind_source = app` (Google tự nhắc sự kiện của nó, QĐ-26), trải cả lần lặp."""
    end = start + timedelta(days=days)
    tz = ZoneInfo(user.timezone)
    items = []
    # QĐ-38: bật `calendar.app_reminds_google` thì app nhắc cả sự kiện tạo trên Google.
    with_google = bool(setting_service.get_value(session, user.user_id, "calendar.app_reminds_google"))
    default_minutes = list(
        setting_service.get_value(session, user.user_id, "calendar.default_remind_minutes")
    )
    for row, occ in collect(session, user, start, end + timedelta(days=28)):
        if row.remind_source == "app":
            minutes_list = list(row.remind_minutes or [])
        elif with_google:
            minutes_list = list(row.remind_minutes or []) or default_minutes
        else:
            continue
        if not minutes_list:
            continue
        begin = (
            datetime.combine(occ["start_date"], time.min, tzinfo=tz) if occ["all_day"] else occ["start_at"]
        )
        occ_key = (occ["occurrence_start"] or begin).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        when = f"{begin.astimezone(tz):%H:%M}" if not occ["all_day"] else "Cả ngày"
        body = f"{when} - {row.location}" if row.location else when
        for minutes in minutes_list:
            fire = begin - timedelta(minutes=minutes)
            if not (start <= fire < end):
                continue
            if row.task_id:
                key = f"task:{row.task_id}:{occ_key}:{minutes}"
                source, source_id, link = "task", row.task_id, f"troly://lich/viec/{row.task_id}"
            else:
                key = f"event:{occ['id']}:{occ_key}:{minutes}"
                source, source_id, link = "event", occ["id"], f"troly://lich/su-kien/{occ['id']}"
                if occ["occurrence_start"] is not None:
                    link += "?lan=" + occ["occurrence_start"].astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            items.append(
                {
                    "reminder_key": key,
                    "source": source,
                    "source_id": source_id,
                    "fire_at": fire.astimezone(UTC),
                    "title": row.title,
                    "body": body,
                    "kind": "alarm" if row.is_alarm else "normal",
                    "deep_link": link,
                }
            )
    items.sort(key=lambda i: (i["fire_at"], i["reminder_key"]))
    revision = hashlib.sha256(json.dumps(items, default=str, sort_keys=True).encode()).hexdigest()[:16]
    return {"revision": revision, "items": items}
