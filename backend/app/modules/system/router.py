from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.system import service

router = APIRouter()


@router.get("/system/status")
def get_status(
    user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.system_status(session, user))


@router.post("/system/jobs/{name}/run", status_code=202)
def run_job(
    name: str, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    service.request_job_run(session, name)
    return ok({"queued": True}, "Đã xếp việc, chạy trong vài giây.")


@router.get("/chat/status")
def get_chat_status(
    user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.chat_status(session, user))
