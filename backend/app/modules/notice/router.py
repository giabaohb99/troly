from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_device
from app.core.context import DeviceContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.notice import service

router = APIRouter()


@router.get("/device/notices")
def list_notices(
    after: str | None = Query(default=None, max_length=60),
    device: DeviceContext = Depends(get_current_device),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.list_notices(session, device.user_id, after))
