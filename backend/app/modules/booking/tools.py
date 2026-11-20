"""Công cụ AI của module booking (QĐ-49, agent AI): xem đặt chỗ sắp tới (khách sạn, vé) bóc từ Gmail."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import ToolContext, ToolOutput, ToolSpec
from app.core import clock

Kind = Literal["hotel", "flight", "bus", "train", "other"]
KIND_TEXT = {"hotel": "khách sạn", "flight": "máy bay", "bus": "xe", "train": "tàu", "other": "khác"}
STATUS_TEXT = {"confirmed": "đã xác nhận", "changed": "đã đổi", "cancelled": "đã hủy"}
CALENDAR_TEXT = {"added": "đã thêm vào lịch", "undone": "đã bỏ khỏi lịch", "none": "chưa vào lịch"}


class ListBookingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind | None = Field(default=None, description="Chỉ một loại; null là mọi loại")
    upcoming: bool = Field(default=True, description="true: sắp tới (từ hôm nay); false: cả đặt chỗ đã qua")
    limit: int | None = Field(default=None, description="Số đặt chỗ, mặc định 10, tối đa 30")


def _service():
    from app.modules.booking import service

    return service


def _when(at, day, tz: str) -> str | None:
    if at is not None:
        from datetime import datetime

        value = datetime.fromisoformat(at) if isinstance(at, str) else at
        return clock.to_local(value, tz).strftime("%H:%M %d/%m/%Y")
    if day is not None:
        return day.strftime("%d/%m/%Y") if hasattr(day, "strftime") else str(day)
    return None


def run_list_bookings(ctx: ToolContext, data: ListBookingsInput) -> ToolOutput:
    rows = _service().list_bookings(
        ctx.session, ctx.user, upcoming=data.upcoming, kind=data.kind, limit=min(max(data.limit or 10, 1), 30)
    )
    tz = ctx.user.timezone
    items = [
        {
            "booking_id": b["id"],
            "kind": KIND_TEXT.get(b["kind"], b["kind"]),
            "status": STATUS_TEXT.get(b["status"], b["status"]),
            "name": b.get("name") or b.get("title"),
            "provider": b.get("provider"),
            "booking_ref": b.get("booking_ref"),
            "address": b.get("address"),
            # khách sạn: bắt đầu là nhận phòng, kết thúc là trả phòng; vé: khởi hành, đến nơi
            "bat_dau": _when(b.get("start_at"), b.get("start_date"), tz),
            "ket_thuc": _when(b.get("end_at"), b.get("end_date"), tz),
            "guests": b.get("guests"),
            "price": f"{b['price']} {b.get('currency') or ''}".strip() if b.get("price") else None,
            "cancellation": b.get("cancellation"),
            "contact_phone": b.get("contact_phone"),
            "lich": CALENDAR_TEXT.get(b.get("calendar_state") or "none"),
            "trip_id": b.get("trip_id"),
        }
        for b in rows
    ]
    result: dict = {"items": items}
    if not items:
        result["ghi_chu"] = (
            "Chưa thấy đặt chỗ nào trong app. Có thể thư xác nhận chưa được quét: tìm thêm bằng search_gmail "
            "(ví dụ: subject:xác nhận đặt phòng newer_than:60d) nếu đã bật Gmail."
        )
    actions = []
    trips = {i["trip_id"] for i in items if i["trip_id"]}
    if len(trips) == 1:
        actions.append(act.open_screen("Xem chuyến đi", "trip_detail", {"trip_id": trips.pop()}))
    return ToolOutput(result=result, actions=actions)


TOOLS = [
    ToolSpec(
        name="list_bookings",
        label="Đang xem đặt chỗ",
        description=(
            "Xem đặt chỗ (khách sạn, vé máy bay, xe, tàu) app đã nhận từ thư xác nhận: giờ nhận, trả phòng, giờ khởi "
            "hành, địa chỉ, mã đặt chỗ, giá, chính sách hủy. Hỏi về đặt phòng, vé (mấy giờ nhận phòng, mã đặt chỗ) "
            "thì gọi công cụ này trước; không thấy mới dùng search_gmail."
        ),
        input_model=ListBookingsInput,
        run=run_list_bookings,
        phase=5,
    ),
]
