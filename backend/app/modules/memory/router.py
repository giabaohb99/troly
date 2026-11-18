from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.memory import service

router = APIRouter()


class ProfileIn(BaseModel):
    content: str = Field(max_length=8000)
    version: int


class RestoreIn(BaseModel):
    version: int | None = None


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=20000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class NotePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=20000)
    tags: list[str] | None = Field(default=None, max_length=20)


@router.get("/memory/profile")
def get_profile(
    user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.get_profile(session, user.user_id))


@router.put("/memory/profile")
def put_profile(
    body: ProfileIn, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.update_profile(session, user.user_id, body.content, body.version), "Đã lưu hồ sơ.")


@router.get("/memory/profile/revisions")
def get_revisions(
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.list_revisions(session, user.user_id, int(cursor) if cursor else None, limit))


@router.get("/memory/profile/revisions/{version}")
def get_revision(
    version: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.get_revision(session, user.user_id, version))


@router.post("/memory/profile/revisions/{version}/restore")
def restore_revision(
    version: int,
    body: RestoreIn | None = None,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    current = body.version if body else None
    return ok(service.restore_revision(session, user.user_id, version, current), "Đã hoàn tác hồ sơ.")


@router.get("/memory/notes")
def list_notes(
    q: str | None = None,
    tag: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.list_notes(session, user.user_id, q, tag, cursor, limit))


@router.post("/memory/notes", status_code=201)
def create_note(
    body: NoteIn, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.create_note(session, user.user_id, body.title, body.body, body.tags))


@router.get("/memory/notes/{note_id}")
def get_note(
    note_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.get_note(session, user.user_id, note_id))


@router.patch("/memory/notes/{note_id}")
def patch_note(
    note_id: int,
    body: NotePatch,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.update_note(session, user.user_id, note_id, body.model_dump(exclude_unset=True)))


@router.delete("/memory/notes/{note_id}")
def delete_note(
    note_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    service.delete_note(session, user.user_id, note_id)
    return ok(None)


@router.post("/memory/notes/{note_id}/restore")
def restore_note(
    note_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.restore_note(session, user.user_id, note_id))
