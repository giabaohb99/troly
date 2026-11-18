"""API của core: đăng nhập, phiên, client-logs, việc nền (12 mục 5.1)."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import auth, clock
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import NotFoundError, ok
from app.core.middleware import client_ip
from app.core.models import ClientLog, JobQueue, User
from app.core.ratelimit import limiter

router = APIRouter()


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)
    label: str | None = Field(default=None, max_length=120)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=200)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)


@router.post("/auth/login")
def post_login(body: LoginIn, request: Request, session: Session = Depends(get_session)) -> dict:
    return ok(auth.login(session, body.email, body.password, body.label, client_ip(request)))


@router.post("/auth/refresh")
def post_refresh(body: RefreshIn, session: Session = Depends(get_session)) -> dict:
    return ok(auth.refresh(session, body.refresh_token))


@router.post("/auth/logout")
def post_logout(
    caller: auth.Caller = Depends(auth.get_caller), session: Session = Depends(get_session)
) -> dict:
    auth.logout(session, caller.user.user_id, caller.session_id)
    return ok(None)


@router.post("/auth/change-password")
def post_change_password(
    body: ChangePasswordIn,
    caller: auth.Caller = Depends(auth.get_caller),
    session: Session = Depends(get_session),
) -> dict:
    auth.change_password(
        session, caller.user.user_id, caller.session_id, body.current_password, body.new_password
    )
    return ok(None, "Đã đổi mật khẩu.")


@router.get("/auth/me")
def get_me(
    user: UserContext = Depends(auth.get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(auth.serialize_user(session.get(User, user.user_id)))


@router.get("/auth/sessions")
def get_sessions(
    caller: auth.Caller = Depends(auth.get_caller), session: Session = Depends(get_session)
) -> dict:
    return ok({"items": auth.list_sessions(session, caller.user.user_id, caller.session_id)})


@router.delete("/auth/sessions/{session_id}")
def delete_session(
    session_id: int, caller: auth.Caller = Depends(auth.get_caller), session: Session = Depends(get_session)
) -> dict:
    auth.revoke_session(session, caller.user.user_id, session_id)
    return ok(None)


class ClientLogIn(BaseModel):
    level: Literal["error", "warn", "info"] = "error"
    kind: str = Field(max_length=40, description="ui_error, api_error, native_error...")
    screen: str | None = Field(default=None, max_length=100)
    message: str = Field(max_length=2000)
    detail: dict | None = None
    app_version: str | None = Field(default=None, max_length=40)
    occurred_at: AwareDatetime | None = None


class ClientLogsIn(BaseModel):
    items: list[ClientLogIn] = Field(min_length=1, max_length=50)


@router.post("/client-logs")
def post_client_logs(
    body: ClientLogsIn,
    request: Request,
    user: UserContext | None = Depends(auth.get_optional_user),
    session: Session = Depends(get_session),
) -> dict:
    """App gửi lỗi giao diện và lỗi gọi API (QĐ-30). Nhận cả khi chưa đăng nhập, giới hạn theo IP."""
    limiter.hit(f"client-logs:{client_ip(request)}", 60, 60, cost=len(body.items))
    now = clock.now()
    for item in body.items:
        session.add(
            ClientLog(
                user_id=user.user_id if user else None,
                level=item.level,
                kind=item.kind,
                screen=item.screen,
                message=item.message,
                detail=item.detail,
                app_version=item.app_version or request.headers.get("x-app-version"),
                occurred_at=item.occurred_at or now,
            )
        )
    return ok({"accepted": len(body.items)})


def serialize_job(job: JobQueue) -> dict:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


@router.get("/jobs/{job_id}")
def get_job(
    job_id: int, user: UserContext = Depends(auth.get_current_user), session: Session = Depends(get_session)
) -> dict:
    job = session.scalar(select(JobQueue).where(JobQueue.id == job_id, JobQueue.user_id == user.user_id))
    if job is None:
        raise NotFoundError()
    return ok(serialize_job(job))
