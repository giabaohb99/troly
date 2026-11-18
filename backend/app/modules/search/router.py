from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.search import service

router = APIRouter()


@router.get("/search")
def get_search(
    q: str = Query(..., min_length=1, max_length=200),
    types: str | None = None,
    from_: AwareDatetime | None = Query(None, alias="from"),
    to: AwareDatetime | None = None,
    limit: int = Query(20, ge=1, le=50),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    wanted = [t.strip() for t in types.split(",") if t.strip()] if types else None
    return ok(
        {"items": service.search(session, user.user_id, q, wanted, from_, to, limit, include_private=True)}
    )
