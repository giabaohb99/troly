"""Đường kết nối MCP chung (QĐ-56). Gắn dưới /api/v1; callback không cần JWT.

Cờ FEATURE_CONNECTORS mặc định tắt: tắt thì router rỗng, app chưa thấy tính năng (bản 1.1.0 vẫn deploy được).
"""

from fastapi import APIRouter, Body, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.integrations.connectors import service
from app.integrations.connectors.settings import get_connector_settings

router = APIRouter()
routes = APIRouter()


@routes.get("/connectors")
def list_connectors(
    user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok({"items": service.list_connectors(session, user.user_id)})


@routes.get("/connectors/presets")
def list_presets(user: UserContext = Depends(get_current_user)) -> dict:
    return ok({"items": service.presets()})


@routes.get("/connectors/oauth/callback", response_class=HTMLResponse)
def oauth_callback(
    code: str | None = None,
    state: str | None = None,
    iss: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    return HTMLResponse(service.callback_html(service.finish_connect(session, code, state, iss, error)))


@routes.post("/connectors", status_code=201)
def create_connector(
    name: str = Body(..., embed=True),
    url: str = Body(..., embed=True),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.create(session, user.user_id, name, url), "Đã thêm kết nối.")


@routes.post("/connectors/{connector_id}/connect")
def connect(
    connector_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.start_connect(session, user.user_id, connector_id))


@routes.post("/connectors/{connector_id}/reconnect")
def reconnect(
    connector_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.start_connect(session, user.user_id, connector_id))


@routes.put("/connectors/{connector_id}/key")
def set_key(
    connector_id: int,
    api_key: str = Body(..., embed=True),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.set_key(session, user.user_id, connector_id, api_key), "Đã lưu khóa.")


@routes.get("/connectors/{connector_id}/tools")
def list_tools(
    connector_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok({"items": service.list_tools(session, user.user_id, connector_id)})


@routes.patch("/connectors/{connector_id}")
def patch_connector(
    connector_id: int,
    changes: dict = Body(...),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    allowed = {k: v for k, v in changes.items() if k in ("name", "write_tools_enabled")}
    return ok(service.update_connector(session, user.user_id, connector_id, allowed))


@routes.delete("/connectors/{connector_id}")
def delete_connector(
    connector_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    service.delete_connector(session, user.user_id, connector_id)
    return ok(None, "Đã xóa kết nối.")


if get_connector_settings().feature_connectors:
    router.include_router(routes)
