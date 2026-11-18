from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.task import service

router = APIRouter()

Priority = Literal["low", "normal", "high"]


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=1024)
    note: str | None = Field(default=None, max_length=8000)
    priority: Priority = "normal"
    due_date: date | None = None
    due_at: AwareDatetime | None = None
    remind_minutes: list[int] | None = Field(default=None, max_length=5)


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=1024)
    note: str | None = Field(default=None, max_length=8000)
    priority: Priority | None = None
    due_date: date | None = None
    due_at: AwareDatetime | None = None
    remind_minutes: list[int] | None = Field(default=None, max_length=5)


class ResolveIn(BaseModel):
    keep: bool


@router.get("/tasks")
def list_tasks(
    status: Literal["todo", "done", "cancelled"] | None = None,
    due: Literal["overdue", "today", "week", "none"] | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.list_tasks(session, user, status=status, due=due, cursor=cursor, limit=limit))


@router.post("/tasks", status_code=201)
def create_task(
    body: TaskIn, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.create_task(session, user, body.model_dump()))


@router.get("/tasks/{task_id}")
def get_task(
    task_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.get_task(session, user, task_id))


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: int,
    body: TaskPatch,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.update_task(session, user, task_id, body.model_dump(exclude_unset=True)))


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    service.delete_task(session, user, task_id)
    return ok(None)


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.complete_task(session, user, task_id))


@router.post("/tasks/{task_id}/reopen")
def reopen_task(
    task_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.reopen_task(session, user, task_id))


@router.post("/tasks/{task_id}/restore")
def restore_task(
    task_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.restore_task(session, user, task_id))


@router.post("/tasks/{task_id}/resolve-remote-delete")
def resolve_remote_delete(
    task_id: int,
    body: ResolveIn,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.resolve_remote_delete(session, user, task_id, body.keep))
