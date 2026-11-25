"""Đường cho trình chạy Claude Code trên VPS (QĐ-60), khóa `CLAUDE_WORKER_TOKEN`; và danh sách việc cho app."""

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.claude_job import service

router = APIRouter()


class FinishIn(BaseModel):
    ok: bool
    result: str | None = Field(default=None, max_length=200_000)
    session_id: str | None = Field(default=None, max_length=200)
    cost_usd: float | None = None
    turns: int | None = None
    error: str | None = Field(default=None, max_length=5000)


@router.post("/internal/claude/jobs/claim")
def claim_job(authorization: str | None = Header(default=None), session: Session = Depends(get_session)) -> dict:
    service.check_runner_token(authorization)
    job = service.claim(session)
    return ok({"job": job})


@router.post("/internal/claude/jobs/reset")
def reset_jobs(authorization: str | None = Header(default=None), session: Session = Depends(get_session)) -> dict:
    service.check_runner_token(authorization)
    count = service.reset_running(session)
    return ok({"reset": count})


@router.post("/internal/claude/jobs/{job_id}/finish")
def finish_job(
    job_id: int,
    body: FinishIn,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    service.check_runner_token(authorization)
    data = service.finish(session, job_id, body.model_dump())
    return ok({"job": data})


class FileIn(BaseModel):
    name: str = Field(max_length=300)
    mime: str | None = Field(default=None, max_length=100)
    data_b64: str


@router.post("/internal/claude/jobs/{job_id}/files")
def add_file(
    job_id: int,
    body: FileIn,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    service.check_runner_token(authorization)
    return ok({"file": service.add_file(session, job_id, body.name, body.mime or "", body.data_b64)})


@router.get("/claude/jobs")
def list_jobs(user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    return ok({"items": service.list_jobs(session, user.user_id, 20)})


@router.post("/claude/jobs/{job_id}/cancel")
def cancel_job(
    job_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    data = service.cancel_job(session, user.user_id, job_id)
    return ok({"job": data})
