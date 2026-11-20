"""QĐ-49: thư đặt chỗ (kể cả ngoài hộp Chính) vào Lịch và chuyến đi; đổi, hủy, Hoàn tác."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.ai import booking_extract
from app.ai.booking_extract import Booking as AiBooking
from app.integrations.google import gmail, stores
from app.integrations.google.tests.conftest import GMAIL_SCOPES, connect_account
from app.modules.booking import service
from app.modules.booking.google_store import STORE
from app.modules.booking.models import Booking, BookingMail
from app.modules.calendar.models import Event
from app.modules.trip.models import Trip, TripStop

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def _hotel(**extra) -> AiBooking:
    data = {
        "kind": "hotel",
        "status": "confirmed",
        "provider": "Booking.com",
        "booking_ref": "4321987",
        "name": "Hotel Quốc Hương",
        "address": "12 Lê Lợi, Phước Hải",
        "area": "Phước Hải, Bà Rịa - Vũng Tàu",
        "start_date": date(2026, 11, 21),
        "end_date": date(2026, 11, 22),
        "guests": 2,
        "price": Decimal("850000"),
        "currency": "VND",
        "cancellation": "Hủy miễn phí trước 19/11",
        "contact_phone": "0254 3886 123",
        "confidence": 0.95,
    }
    return AiBooking(**{**data, **extra})


@pytest.fixture
def account(db, user, fake):
    acc, result = connect_account(db, user, fake, packs=("calendar", "gmail"), scope=GMAIL_SCOPES)
    assert result.ket_qua == "ok"
    return acc


@pytest.fixture
def booking_store():
    stores.register_booking_store(STORE)
    yield STORE
    stores.register_booking_store(None)


@pytest.fixture
def ai(monkeypatch):
    """Bộ bóc tách giả: trả đặt chỗ theo tiêu đề thư; đếm số lần gọi."""
    answers: dict[str, AiBooking | None] = {}
    calls: list[str] = []

    def extract(text, subject, sender, **kw):
        calls.append(subject)
        return answers.get(subject)

    monkeypatch.setattr(booking_extract, "extract_booking", extract)
    return answers, calls


_clock = {"ms": int(datetime.now(UTC).timestamp() * 1000)}


def _mail(fake, subject, sender="Booking.com <noreply@booking.com>", labels=("INBOX", "CATEGORY_UPDATES")):
    """Thư mới đến (sau lần quét trước), mỗi thư cách nhau 1 giây."""
    _clock["ms"] += 1000
    return fake.gmail.add_mail(
        subject=subject, sender=sender, labels=labels, text="Mã đặt chỗ 4321987", at_ms=_clock["ms"]
    )


def _events(db, user):
    return list(db.scalars(select(Event).where(Event.user_id == user.user_id, Event.deleted_at.is_(None))))


def test_booking_mail_outside_primary_adds_check_in_and_out(db, user, fake, account, booking_store, ai):
    answers, calls = ai
    subject = "Đặt phòng của bạn ở Hotel Quốc Hương đã được xác nhận"
    answers[subject] = _hotel()
    _mail(fake, subject)
    _mail(fake, "Ưu đãi cuối tuần", sender="Shopee <km@shopee.vn>", labels=("INBOX", "CATEGORY_PROMOTIONS"))
    assert gmail.scan_bookings(db, account) == 1
    row = db.scalar(select(Booking))
    assert (row.kind, row.status, row.calendar_state, row.title) == (
        "hotel",
        "confirmed",
        "added",
        "Hotel Quốc Hương",
    )
    events = {e.id: e for e in _events(db, user)}
    check_in, check_out = events[row.event_id], events[row.end_event_id]
    assert check_in.title == "Nhận phòng Hotel Quốc Hương" and check_in.start_at.astimezone(VN).hour == 14
    assert check_out.title == "Trả phòng Hotel Quốc Hương" and check_out.start_at.astimezone(VN).hour == 12
    assert "Mã đặt chỗ: 4321987" in check_in.description and "mail.google.com" in check_in.description
    assert check_in.location == "Hotel Quốc Hương, 12 Lê Lợi, Phước Hải"
    q = fake.calls("GET", r"/gmail/v1/users/me/messages$")[-1].url.params["q"]
    assert "from:booking.com" in q and "in:inbox" not in q and "after:" in q

    assert gmail.scan_bookings(db, account) == 0 and calls == [subject]  # không gửi AI lần hai


def test_not_a_booking_is_marked_and_skipped(db, fake, account, booking_store, ai):
    _, calls = ai
    _mail(fake, "Xác nhận đăng ký nhận bản tin")
    assert gmail.scan_bookings(db, account) == 0
    assert db.scalar(select(BookingMail)).outcome == "ignored" and db.scalar(select(Booking)) is None
    gmail.scan_bookings(db, account)
    assert len(calls) == 1


def test_changed_then_cancelled_mail_updates_same_booking(db, user, fake, account, booking_store, ai):
    answers, _ = ai
    answers["Xác nhận đặt phòng 4321987"] = _hotel()
    _mail(fake, "Xác nhận đặt phòng 4321987")
    gmail.scan_bookings(db, account)
    row = db.scalar(select(Booking))
    answers["Thay đổi đặt phòng 4321987"] = _hotel(status="changed", start_date=date(2026, 11, 28),
                                                   end_date=date(2026, 11, 29))  # fmt: skip
    _mail(fake, "Thay đổi đặt phòng 4321987")
    gmail.scan_bookings(db, account)
    assert db.scalars(select(Booking)).all() == [row]
    db.refresh(row)
    check_in = db.get(Event, row.event_id)
    assert row.status == "changed" and check_in.start_at.astimezone(VN).date() == date(2026, 11, 28)
    answers["Đã hủy đặt phòng 4321987"] = _hotel(status="cancelled")
    _mail(fake, "Đã hủy đặt phòng 4321987")
    gmail.scan_bookings(db, account)
    db.refresh(row)
    assert row.status == "cancelled" and row.calendar_state == "none" and row.event_id is None
    assert _events(db, user) == []


def _trip(db, user, with_hotel: bool):
    trip = Trip(user_id=user.user_id, title="Phước Hải", status="draft",
                start_date=date(2026, 11, 21), end_date=date(2026, 11, 22))  # fmt: skip
    db.add(trip)
    db.flush()
    db.add(
        TripStop(user_id=user.user_id, trip_id=trip.id, day_no=1, seq=1, title="Ăn trưa", category="an_uong")
    )
    if with_hotel:
        db.add(TripStop(user_id=user.user_id, trip_id=trip.id, day_no=1, seq=2, title="Nghỉ Hotel Quốc Hương",
                        category="khach_san", place_query="Hotel Quốc Hương"))  # fmt: skip
    db.flush()
    return trip


def test_hotel_attaches_to_trip_stop_and_undo_detaches(db, user, fake, account, booking_store, ai):
    from app.modules.trip import service as trip_service

    trip = _trip(db, user, with_hotel=True)
    answers, _ = ai
    answers["Xác nhận đặt phòng"] = _hotel()
    _mail(fake, "Xác nhận đặt phòng")
    gmail.scan_bookings(db, account)
    row = db.scalar(select(Booking))
    stop = db.get(TripStop, row.trip_stop_id)
    assert row.trip_id == trip.id and stop.title == "Nghỉ Hotel Quốc Hương" and stop.phone == "0254 3886 123"
    shown = trip_service.serialize_stop(stop)["booking"]
    assert shown["booking_ref"] == "4321987" and shown["price"] == "850000.00" and shown["source"] == "email"
    assert shown["check_in"].startswith("2026-11-21T14:00:00+07:00") and "added_stop" not in shown

    assert service.undo_booking(db, user, row.id) == {"undone": True}
    assert service.undo_booking(db, user, row.id) == {"undone": True}  # gọi lại vẫn ổn
    db.refresh(stop)
    assert stop.booking is None and _events(db, user) == [] and row.calendar_state == "undone"


def test_trip_without_hotel_gets_new_stop_removed_on_undo(db, user, fake, account, booking_store, ai):
    trip = _trip(db, user, with_hotel=False)
    answers, _ = ai
    answers["Xác nhận đặt phòng"] = _hotel()
    _mail(fake, "Xác nhận đặt phòng")
    gmail.scan_bookings(db, account)
    row = db.scalar(select(Booking))
    stop = db.get(TripStop, row.trip_stop_id)
    assert stop.category == "khach_san" and stop.seq == 2 and stop.area == "Phước Hải, Bà Rịa - Vũng Tàu"
    service.undo_booking(db, user, row.id)
    assert [s.title for s in db.scalars(select(TripStop).where(TripStop.trip_id == trip.id))] == ["Ăn trưa"]


def test_undo_refuses_when_user_edited_event(db, user, fake, account, booking_store, ai):
    from app.modules.calendar import service as calendar

    answers, _ = ai
    answers["Xác nhận đặt phòng"] = _hotel()
    _mail(fake, "Xác nhận đặt phòng")
    gmail.scan_bookings(db, account)
    row = db.scalar(select(Booking))
    calendar.update_event(db, user, row.event_id, {"title": "Nhận phòng, nhớ mang CCCD"})
    with pytest.raises(service.BookingEdited) as exc:
        service.undo_booking(db, user, row.id)
    assert exc.value.code == "BOOKING_EDITED" and exc.value.status == 409


def test_undo_other_users_booking_is_not_found(db, user, fake, account, booking_store, ai):
    from app.core.context import UserContext
    from app.core.errors import NotFoundError

    answers, _ = ai
    answers["Xác nhận đặt phòng"] = _hotel()
    _mail(fake, "Xác nhận đặt phòng")
    gmail.scan_bookings(db, account)
    row = db.scalar(select(Booking))
    with pytest.raises(NotFoundError):
        service.undo_booking(db, UserContext(user_id=user.user_id + 999, timezone="Asia/Ho_Chi_Minh"), row.id)


def test_flight_is_one_event_and_listed(db, user, fake, account, booking_store, ai):
    answers, _ = ai
    dep = datetime(2026, 11, 25, 6, 15, tzinfo=VN)
    answers["Vé điện tử VJ123"] = AiBooking(kind="flight", status="confirmed", provider="Vietjet Air",
                                            booking_ref="ABC123", name="VJ123 SGN → HAN", start_at=dep,
                                            end_at=dep + timedelta(hours=2, minutes=10), confidence=0.9)  # fmt: skip
    _mail(fake, "Vé điện tử VJ123", sender="Vietjet <noreply@vietjetair.com>")
    gmail.scan_bookings(db, account)
    row = db.scalar(select(Booking))
    assert row.title == "Chuyến bay VJ123 SGN → HAN" and row.end_event_id is None and row.trip_id is None
    event = db.get(Event, row.event_id)
    assert event.start_at == dep.astimezone(UTC) and event.end_at == (dep + timedelta(hours=2, minutes=10))
    [listed] = service.list_bookings(db, user)
    assert listed["booking_ref"] == "ABC123" and listed["event_ids"] == [row.event_id]
    assert service.list_bookings(db, user, kind="hotel") == []


def test_inbox_sync_runs_booking_scan_and_survives_errors(db, user, fake, account, booking_store, ai, mail_store,
                                                         monkeypatch):  # fmt: skip
    from app.integrations.google.models import GoogleSyncState

    answers, _ = ai
    answers["Xác nhận đặt phòng"] = _hotel()
    _mail(fake, "Xác nhận đặt phòng")
    state = db.scalar(select(GoogleSyncState).where(GoogleSyncState.service == "gmail",
                                                    GoogleSyncState.resource_id == "me"))  # fmt: skip
    gmail.sync_gmail(db, account, state)
    assert db.scalar(select(Booking)) is not None

    def boom(*a, **k):
        raise RuntimeError("AI hỏng")

    monkeypatch.setattr(booking_extract, "extract_booking", boom)
    _mail(fake, "Xác nhận đặt phòng khác")
    gmail.sync_gmail(db, account, state)  # không ném lỗi
    assert state.status == "ok"


def test_reset_scan_reads_back_60_days(db, fake, account, booking_store, ai):
    answers, _ = ai
    answers["Xác nhận đặt phòng"] = _hotel()
    gmail.scan_bookings(db, account)  # lần đầu chưa có thư
    old_ms = int((datetime.now(UTC) - timedelta(days=30)).timestamp() * 1000)
    fake.gmail.add_mail(subject="Xác nhận đặt phòng", sender="noreply@booking.com",
                        labels=("INBOX", "CATEGORY_UPDATES"), at_ms=old_ms)  # fmt: skip
    assert gmail.scan_bookings(db, account) == 0  # thư cũ hơn lần quét trước
    gmail.reset_booking_scan(db, account.user_id, 60)
    assert gmail.scan_bookings(db, account) == 1
