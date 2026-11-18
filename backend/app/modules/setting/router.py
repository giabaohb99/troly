from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.setting import service

router = APIRouter()


@router.get("/settings")
def get_settings_values(
    user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.get_all(session, user.user_id))


@router.patch("/settings")
def patch_settings(
    changes: dict = Body(...),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok({"values": service.update(session, user.user_id, changes)}, "Đã lưu cài đặt.")
