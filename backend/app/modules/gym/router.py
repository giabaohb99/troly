from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.errors import ok
from app.modules.gym import service

router = APIRouter()


@router.get("/reports/gym")
def get_gym_report(
    period: Literal["week", "month"] | None = None,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Thẻ *Tập luyện* (QĐ-54). `period` (mặc định week) hoặc `from`, `to` (tối đa 92 ngày). Luôn 200 kèm thẻ
    `{status: ok|disabled|error, message, data}`; khoảng ngày sai thì 400."""
    return ok(service.gym_card(user.timezone, period, from_, to))
