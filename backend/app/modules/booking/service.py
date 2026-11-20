"""Đặt chỗ đọc từ thư (QĐ-49): khách sạn, vé máy bay, xe, tàu.

Luồng: lớp Gmail (integrations/google/gmail.scan_bookings) tìm thư nghi là đặt chỗ, kể cả ngoài hộp Chính,
giao cho STORE (google_store.py) -> handle_mail: AI bóc tách (app.ai.booking_extract) -> apply_booking:
ghi tab_booking, tạo sự kiện Lịch qua calendar.service (lên Google như sự kiện app tạo), gắn khách sạn
vào chuyến trùng ngày qua trip.service. Thư đổi thì sửa sự kiện; thư hủy thì xóa sự kiện.
Người dùng bấm Hoàn tác ở thông báo booking_added -> undo_booking.
"""

import importlib
import importlib.util
import logging
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.core import clock
from app.core.context import UserContext
from app.core.errors import ConflictError, NotFoundError
from app.modules.booking.models import Booking, BookingMail

log = logging.getLogger("troly.booking")

CHECK_IN = time(14, 0)
CHECK_OUT = time(12, 0)
MARK_MINUTES = 30  # sự kiện nhận, trả phòng dài 30 phút
TRAVEL_DEFAULT = timedelta(hours=2)
KIND_LABEL = {"flight": "Chuyến bay", "bus": "Xe", "train": "Tàu", "other": "Đặt chỗ"}
KINDS = ("hotel", "flight", "bus", "train", "other")


class BookingEdited(ConflictError):
    code = "BOOKING_EDITED"
    message = "Sự kiện đã được sửa, hãy xóa trong Lịch nếu muốn."


def _optional(name: str):
    try:
        if importlib.util.find_spec(name) is None:
            return None
    except ModuleNotFoundError:
        return None
    return importlib.import_module(name)


def _calendar():
    return importlib.import_module("app.modules.calendar.service")


def _trip():
    return importlib.import_module("app.modules.trip.service")


def _user(session: Session, user_id: int) -> UserContext:
    tz = session.execute(text("SELECT timezone FROM tab_user WHERE id = :u"), {"u": user_id}).scalar()
    return UserContext(user_id=user_id, timezone=tz or "Asia/Ho_Chi_Minh")


# ---------- Nhận thư ----------


def seen(session: Session, user_id: int, message_ids: list[str]) -> set[str]:
    return set(
        session.scalars(
            select(BookingMail.message_id).where(
                BookingMail.user_id == user_id, BookingMail.message_id.in_(message_ids)
            )
        )
    )


def _mark(session: Session, user_id: int, message_id: str, outcome: str, booking_id: int | None) -> None:
    session.add(BookingMail(user_id=user_id, message_id=message_id, outcome=outcome, booking_id=booking_id))
    session.flush()


def handle_mail(session: Session, user_id: int, mail) -> bool:
    """mail: gmail.BookingMail. Trả True khi là đặt chỗ. Chưa có bộ bóc tách thì không ghi đã xét."""
    ai = _optional("app.ai.booking_extract")
    if ai is None:
        return False
    if not ai.looks_like_booking(mail.subject, mail.sender):
        _mark(session, user_id, mail.message_id, "ignored", None)
        return False
    user = _user(session, user_id)
    found = ai.extract_booking(
        mail.text, mail.subject, mail.sender, user_id=user_id, received_at=mail.date, tz=user.timezone
    )
    if found is None:
        _mark(session, user_id, mail.message_id, "ignored", None)
        return False
    row = apply_booking(session, user, found, mail)
    _mark(session, user_id, mail.message_id, "booking", row.id)
    return True


# ---------- Ghi đặt chỗ ----------


def _title(b) -> str:
    if b.kind == "hotel":
        return (b.name or b.provider or "Khách sạn").strip()[:200]
    label = KIND_LABEL.get(b.kind, "Đặt chỗ")
    return f"{label} {b.name or b.booking_ref or b.provider or ''}".strip()[:200]


def _find(session: Session, user_id: int, b, thread_id: str | None) -> Booking | None:
    if b.booking_ref:
        stmt = select(Booking).where(
            Booking.user_id == user_id, Booking.kind == b.kind, Booking.booking_ref == b.booking_ref
        )
        if b.provider:
            stmt = stmt.where(or_(Booking.provider == b.provider, Booking.provider.is_(None)))
        row = session.scalar(stmt.limit(1))
        if row is not None:
            return row
    if thread_id:
        return session.scalar(
            select(Booking).where(Booking.user_id == user_id, Booking.source_thread_id == thread_id)
        )
    return None


FIELDS = ("provider", "booking_ref", "name", "address", "area", "start_at", "start_date", "end_at", "end_date",
          "guests", "price", "currency", "cancellation", "contact_phone", "confidence")  # fmt: skip


def apply_booking(session: Session, user: UserContext, b, mail) -> Booking:
    """b: app.ai.booking_extract.Booking. Thư đổi, hủy cùng mã đặt chỗ (hoặc cùng luồng) thì sửa dòng cũ."""
    row = _find(session, user.user_id, b, getattr(mail, "thread_id", None))
    created = row is None
    if created:
        row = Booking(user_id=user.user_id, kind=b.kind, status=b.status, title=_title(b))
        session.add(row)
    for key in FIELDS:
        value = getattr(b, key, None)
        if value is not None or created:
            setattr(row, key, value)
    if row.start_date is None and row.start_at is not None:
        row.start_date = row.start_at.astimezone(ZoneInfo(user.timezone)).date()
    if row.end_date is None and row.end_at is not None:
        row.end_date = row.end_at.astimezone(ZoneInfo(user.timezone)).date()
    row.status = b.status
    row.title = _title(b) if b.name or created else row.title
    row.source_message_id = mail.message_id
    row.source_thread_id = getattr(mail, "thread_id", None) or row.source_thread_id
    session.flush()
    url = getattr(mail, "url", None)
    if row.status == "cancelled":
        if row.calendar_state == "added":
            _delete_events(session, user, row)
            row.calendar_state = "none"
        _sync_trip(session, user, row, url)
    elif row.calendar_state == "added":
        _update_events(session, user, row, url)
        _sync_trip(session, user, row, url)
    elif row.calendar_state == "none" and (row.start_at or row.start_date):
        _create_events(session, user, row, url)
        row.calendar_state = "added"
        _attach_trip(session, user, row, url)
    session.flush()
    return row


# ---------- Lịch ----------


def _at(d: date | None, at: datetime | None, default: time, tz: str) -> datetime | None:
    if at is not None:
        return at
    return datetime.combine(d, default, ZoneInfo(tz)) if d else None


def _description(row: Booking, url: str | None) -> str:
    lines = [
        f"Mã đặt chỗ: {row.booking_ref}" if row.booking_ref else None,
        f"Nơi đặt: {row.provider}" if row.provider else None,
        f"Số khách: {row.guests}" if row.guests else None,
        f"Giá: {row.price:,.0f} {row.currency or ''}".replace(",", ".").strip()
        if row.price is not None
        else None,
        f"Hủy: {row.cancellation}" if row.cancellation else None,
        f"Điện thoại: {row.contact_phone}" if row.contact_phone else None,
        f"Thư gốc: {url}" if url else None,
        "Thêm tự động từ thư đặt chỗ.",
    ]
    return "\n".join(x for x in lines if x)


def _plan(row: Booking, tz: str) -> list[dict]:
    """Sự kiện cần có: khách sạn thì nhận phòng (14:00) và trả phòng (12:00); vé thì giờ đi tới giờ đến."""
    location = ", ".join(x for x in (row.name if row.kind == "hotel" else None, row.address) if x) or None
    if row.kind == "hotel":
        out = []
        check_in = _at(row.start_date, row.start_at, CHECK_IN, tz)
        if check_in:
            out.append({"title": f"Nhận phòng {row.title}", "start_at": check_in,
                        "end_at": check_in + timedelta(minutes=MARK_MINUTES), "location": location})  # fmt: skip
        check_out = _at(row.end_date, row.end_at, CHECK_OUT, tz)
        if check_out:
            out.append({"title": f"Trả phòng {row.title}", "start_at": check_out,
                        "end_at": check_out + timedelta(minutes=MARK_MINUTES), "location": location})  # fmt: skip
        return out
    if row.start_at:
        end = row.end_at if row.end_at and row.end_at > row.start_at else row.start_at + TRAVEL_DEFAULT
        return [{"title": row.title, "start_at": row.start_at, "end_at": end, "location": location}]
    end_date = (row.end_date or row.start_date) + timedelta(days=1)
    return [{"title": row.title, "all_day": True, "start_date": row.start_date, "end_date": end_date,
             "location": location}]  # fmt: skip


def _snap(event: dict) -> dict:
    def iso(v):
        if isinstance(v, datetime):
            return v.astimezone(UTC).isoformat()  # so theo UTC: bản tạo có +07:00, bản đọc lại là UTC
        return v.isoformat() if hasattr(v, "isoformat") else v

    return {k: iso(event.get(k)) for k in ("title", "start_at", "end_at", "start_date", "end_date")}


def _create_events(session: Session, user: UserContext, row: Booking, url: str | None) -> None:
    cal = _calendar()
    snapshot, ids = {}, []
    for plan in _plan(row, user.timezone):
        made = cal.create_event(session, user, {**plan, "description": _description(row, url)})["event"]
        ids.append(made["id"])
        snapshot[str(made["id"])] = _snap(made)
    row.event_id = ids[0] if ids else None
    row.end_event_id = ids[1] if len(ids) > 1 else None
    row.event_snapshot = snapshot


def _event_ids(row: Booking) -> list[int]:
    return [i for i in (row.event_id, row.end_event_id) if i]


def _update_events(session: Session, user: UserContext, row: Booking, url: str | None) -> None:
    """Thư đổi: dời giờ, đổi tên sự kiện đã tạo; thiếu sự kiện (đã xóa tay) thì thôi."""
    cal = _calendar()
    snapshot = dict(row.event_snapshot or {})
    for event_id, plan in zip(_event_ids(row), _plan(row, user.timezone), strict=False):
        try:
            changed = cal.update_event(
                session, user, event_id, {**plan, "description": _description(row, url)}
            )
        except NotFoundError:
            continue
        snapshot[str(event_id)] = _snap(changed)
    row.event_snapshot = snapshot


def _delete_events(session: Session, user: UserContext, row: Booking) -> None:
    cal = _calendar()
    for event_id in _event_ids(row):
        try:
            cal.delete_event(session, user, event_id)
        except NotFoundError:
            pass
    row.event_id = row.end_event_id = None
    row.event_snapshot = {}


# ---------- Chuyến đi ----------


def _price(value) -> str | None:
    return None if value is None else str(Decimal(value).quantize(Decimal("0.01")))


def _stop_booking(row: Booking) -> dict:
    tz_in = row.start_at or (datetime.combine(row.start_date, CHECK_IN) if row.start_date else None)
    tz_out = row.end_at or (datetime.combine(row.end_date, CHECK_OUT) if row.end_date else None)
    return {
        "booking_id": row.id,
        "provider": row.provider,
        "booking_ref": row.booking_ref,
        "check_in": tz_in,
        "check_out": tz_out,
        "guests": row.guests,
        "price": _price(row.price),
        "currency": row.currency,
        "cancellation": row.cancellation,
        "status": row.status,
        "source": "email",
    }


def _local(value: dict, tz: str) -> dict:
    """Giờ nhận, trả phòng ghép từ ngày thì theo múi giờ người dùng."""
    for key in ("check_in", "check_out"):
        v = value[key]
        if isinstance(v, datetime) and v.tzinfo is None:
            value[key] = v.replace(tzinfo=ZoneInfo(tz))
        if isinstance(value[key], datetime):
            value[key] = value[key].isoformat()
    return value


def _attach_trip(session: Session, user: UserContext, row: Booking, url: str | None) -> None:
    if row.kind != "hotel" or row.start_date is None:
        return
    attached = _trip().attach_booking(
        session,
        user,
        night=row.start_date,
        name=row.title,
        area=row.area,
        address=row.address,
        phone=row.contact_phone,
        booking=_local(_stop_booking(row), user.timezone),
    )
    if attached:
        row.trip_id, row.trip_stop_id = attached


def _sync_trip(session: Session, user: UserContext, row: Booking, url: str | None) -> None:
    if row.trip_stop_id:
        _trip().update_stop_booking(
            session, user, row.trip_stop_id, _local(_stop_booking(row), user.timezone)
        )


# ---------- Hoàn tác, liệt kê ----------


def _get(session: Session, user_id: int, booking_id: int) -> Booking:
    row = session.scalar(select(Booking).where(Booking.id == booking_id, Booking.user_id == user_id))
    if row is None:
        raise NotFoundError("Không tìm thấy đặt chỗ.")
    return row


def undo_booking(session: Session, user: UserContext, booking_id: int) -> dict:
    """Hoàn tác từ thông báo booking_added: xóa sự kiện app đã thêm, gỡ khỏi chuyến. Gọi lại vẫn ổn."""
    row = _get(session, user.user_id, booking_id)
    if row.calendar_state == "undone":
        return {"undone": True}
    cal = _calendar()
    for event_id in _event_ids(row):
        try:
            now = _snap(cal.get_event(session, user, event_id))
        except NotFoundError:
            continue  # người dùng đã tự xóa
        if now != (row.event_snapshot or {}).get(str(event_id)):
            raise BookingEdited()
    _delete_events(session, user, row)
    if row.trip_stop_id:
        _trip().detach_booking(session, user, row.trip_stop_id)
    row.trip_id = row.trip_stop_id = None
    row.calendar_state = "undone"
    session.flush()
    return {"undone": True}


def serialize(row: Booking) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "status": row.status,
        "calendar_state": row.calendar_state,
        "title": row.title,
        "provider": row.provider,
        "booking_ref": row.booking_ref,
        "name": row.name,
        "address": row.address,
        "start_at": row.start_at,
        "start_date": row.start_date,
        "end_at": row.end_at,
        "end_date": row.end_date,
        "guests": row.guests,
        "price": _price(row.price),
        "currency": row.currency,
        "cancellation": row.cancellation,
        "contact_phone": row.contact_phone,
        "trip_id": row.trip_id,
        "event_ids": _event_ids(row),
        "source_thread_id": row.source_thread_id,
    }


def list_bookings(
    session: Session, user: UserContext, *, upcoming: bool = True, kind: str | None = None, limit: int = 20
) -> list[dict]:
    """Công cụ list_bookings. upcoming: ngày kết thúc (không có thì ngày bắt đầu) từ hôm nay theo giờ người dùng."""
    stmt = select(Booking).where(Booking.user_id == user.user_id)
    if kind:
        stmt = stmt.where(Booking.kind == kind)
    today = clock.now().astimezone(ZoneInfo(user.timezone)).date()
    if upcoming:
        stmt = stmt.where(
            or_(Booking.end_date >= today, Booking.end_date.is_(None) & (Booking.start_date >= today))
        )
        stmt = stmt.order_by(Booking.start_date.asc().nulls_last(), Booking.id)
    else:
        stmt = stmt.order_by(Booking.start_date.desc().nulls_last(), Booking.id.desc())
    return [serialize(r) for r in session.scalars(stmt.limit(max(1, min(limit, 100))))]
