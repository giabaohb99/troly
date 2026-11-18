from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.report import service

router = APIRouter()


@router.get("/reports/dashboard")
def get_dashboard(
    day: date | None = Query(default=None, alias="date"),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.dashboard(session, user, day))


@router.get("/reports/ai-cost")
def get_ai_cost(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.ai_cost(session, user, service.parse_month(month, user)))
