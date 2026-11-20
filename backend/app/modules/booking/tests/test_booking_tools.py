"""Công cụ list_bookings (QĐ-49, agent AI) trên service giả theo hợp đồng của agent Google."""

import sys
import types
from datetime import UTC, date, datetime

import pytest

from app.ai.schemas import ToolContext
from app.modules.booking import tools

NOW = datetime(2026, 11, 20, 3, tzinfo=UTC)
ROW = {
    "id": 7,
    "kind": "hotel",
    "status": "confirmed",
    "title": "Khách sạn Biển Xanh Phước Hải",
    "provider": "Booking.com",
    "booking_ref": "4521389112",
    "name": "Khách sạn Biển Xanh Phước Hải",
    "address": "12 Võ Thị Sáu, Phước Hải, Bà Rịa - Vũng Tàu",
    "start_at": "2026-11-21T07:00:00+00:00",
    "start_date": None,
    "end_at": None,
    "end_date": date(2026, 11, 22),
    "guests": 2,
    "price": "1250000",
    "currency": "VND",
    "cancellation": "Miễn phí hủy trước 18:00 ngày 19/11/2026.",
    "contact_phone": "+842543888999",
    "trip_id": 3,
    "event_ids": [11, 12],
    "source_thread_id": "t1",
    "calendar_state": "added",
}


@pytest.fixture
def fake_service(monkeypatch):
    calls = []
    mod = types.ModuleType("app.modules.booking.service")

    def list_bookings(session, user, *, upcoming=True, kind=None, limit=20):
        calls.append({"upcoming": upcoming, "kind": kind, "limit": limit})
        return [ROW] if kind in (None, "hotel") else []

    mod.list_bookings = list_bookings
    monkeypatch.setitem(sys.modules, "app.modules.booking.service", mod)
    import app.modules.booking as pkg

    monkeypatch.setattr(pkg, "service", mod, raising=False)
    return calls


@pytest.fixture
def ctx(db, user):
    return ToolContext(session=db, user=user, conversation_id=None, now=NOW)


def _call(ctx, **data):
    spec = tools.TOOLS[0]
    return spec.run(ctx, spec.input_model.model_validate(data))


def test_check_in_time_in_local_time(ctx, fake_service):
    out = _call(ctx)
    item = out.result["items"][0]
    assert fake_service == [{"upcoming": True, "kind": None, "limit": 10}]
    assert item["bat_dau"] == "14:00 21/11/2026" and item["ket_thuc"] == "22/11/2026"
    assert (
        item["price"] == "1250000 VND" and item["lich"] == "đã thêm vào lịch" and item["kind"] == "khách sạn"
    )
    assert out.actions[0]["screen"] == "trip_detail" and out.actions[0]["params"] == {"trip_id": 3}


def test_empty_list_points_to_gmail_search(ctx, fake_service):
    out = _call(ctx, kind="flight")
    assert out.result["items"] == [] and "search_gmail" in out.result["ghi_chu"]


def test_prompt_prefers_list_bookings():
    from app.ai.prompt import STATIC_PROMPT

    assert "list_bookings trước" in STATIC_PROMPT and "search_gmail" in STATIC_PROMPT


def test_list_bookings_on_real_service(db, user):
    """Chạy trên service thật của agent Google: dòng Booking trong DB, giờ nhận phòng theo giờ người dùng."""
    from app.modules.booking.models import Booking

    db.add(
        Booking(
            user_id=user.user_id,
            kind="hotel",
            status="confirmed",
            title="Khách sạn Biển Xanh Phước Hải",
            name="Khách sạn Biển Xanh Phước Hải",
            booking_ref="4521389112",
            start_at=datetime(2099, 11, 21, 7, tzinfo=UTC),
            end_date=date(2099, 11, 22),
            price=1250000,
            currency="VND",
            source_message_id="m-real-1",
        )
    )
    db.flush()
    ctx = ToolContext(session=db, user=user, conversation_id=None, now=NOW)
    out = tools.TOOLS[0].run(ctx, tools.ListBookingsInput())
    item = next(i for i in out.result["items"] if i["booking_ref"] == "4521389112")
    assert item["bat_dau"] == "14:00 21/11/2099" and item["ket_thuc"] == "22/11/2099"
    assert item["price"].startswith("1250000") and item["price"].endswith("VND")
