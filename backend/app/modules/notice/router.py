from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_device
from app.core.context import DeviceContext
from app.core.db import get_session
from app.core.errors import AppError, ok
from app.modules.notice import service

router = APIRouter()


@router.get("/device/notices")
def list_notices(
    after: str | None = Query(default=None, max_length=60),
    device: DeviceContext = Depends(get_current_device),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.list_notices(session, device.user_id, after, device.timezone))


@router.post("/device/bookings/{booking_id}/undo")
def undo_booking(
    booking_id: int = Path(ge=1),
    device: DeviceContext = Depends(get_current_device),
    session: Session = Depends(get_session),
) -> dict:
    """Nút Hoàn tác trên notice `booking_added` (QĐ-49): xóa sự kiện Lịch đã tạo, gỡ khỏi chuyến,
    `calendar_state = undone` để lần quét Gmail sau không thêm lại. Việc làm ở module booking (agent Google);
    sự kiện đã bị sửa thì 409 `BOOKING_EDITED`. Trả `{undone: true}`."""
    try:
        from app.modules.booking import service as booking_service
    except ImportError as exc:
        raise AppError("Máy chủ chưa có phần đặt chỗ.", code="NOT_AVAILABLE", status=409) from exc
    return ok(booking_service.undo_booking(session, device.user, booking_id))
