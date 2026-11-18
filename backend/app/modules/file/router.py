from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.file import service
from app.modules.file.models import PURPOSES

router = APIRouter()


class UploadIn(BaseModel):
    original_name: str = Field(min_length=1, max_length=200)
    mime: str = Field(max_length=120)
    size_bytes: int = Field(gt=0)
    purpose: Literal[PURPOSES] = "chat_attachment"  # type: ignore[valid-type]
    sha256: str | None = Field(default=None, max_length=64)


@router.post("/files/upload-url")
def post_upload_url(
    body: UploadIn, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(
        service.create_upload(
            session, user.user_id, body.original_name, body.mime, body.size_bytes, body.purpose, body.sha256
        )
    )


@router.post("/files/{file_id}/complete")
def post_complete(
    file_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.complete_upload(session, user.user_id, file_id))


@router.get("/files")
def get_files(
    purpose: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.list_files(session, user.user_id, purpose, cursor, limit))


@router.get("/files/{file_id}")
def get_file(
    file_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.get_file(session, user.user_id, file_id))


@router.delete("/files/{file_id}")
def delete_file(
    file_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    service.delete_file(session, user.user_id, file_id)
    return ok(None)


@router.post("/files/{file_id}/restore")
def restore_file(
    file_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.restore_file(session, user.user_id, file_id))
