"""Gốc ghép FastAPI (10 mục 3.13): cấu hình, log, lớp giữa, lỗi, router mọi module, công cụ AI."""

import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core import clock
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.errors import error_body, install_error_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.router import router as core_router
from app.registry import import_all_models, iter_integration_parts, iter_module_parts, register_integrations

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger("troly")
import_all_models()

app = FastAPI(
    title="troly",
    docs_url=None if settings.is_prod else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_prod else "/api/openapi.json",
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Retry-After"],
)
install_error_handlers(app)

_VERSION_EXEMPT = ("/api/v1/device/release", "/api/v1/auth/", "/api/v1/client-logs")


@app.middleware("http")
async def check_app_version(request: Request, call_next):
    """Bản APK thấp hơn min_supported_version_code của releases/latest.json thì 426 (12 mục 3.6)."""
    raw = request.headers.get("x-app-version", "")
    path = request.url.path
    if raw.isdigit() and path.startswith("/api/v1/") and not path.startswith(_VERSION_EXEMPT):
        from app.modules.device import service as device_service

        min_code = await run_in_threadpool(device_service.min_supported_version_code)
        if min_code and int(raw) < min_code:
            return JSONResponse(
                status_code=426,
                content=error_body("APP_VERSION_UNSUPPORTED", "Bản app đã cũ, cập nhật để dùng tiếp."),
            )
    return await call_next(request)


api = APIRouter(prefix="/api/v1")
api.include_router(core_router)
for _name, module in iter_module_parts("router"):
    api.include_router(module.router)
    if hasattr(module, "public_router"):
        app.include_router(module.public_router)
for _name, integration in iter_integration_parts("router"):
    api.include_router(integration.router)
app.include_router(api)
register_integrations()


def _register_tools() -> None:
    """Gom công cụ AI của các module có tools.py (agent AI viết)."""
    try:
        from app.ai.registry import register_tools
    except ModuleNotFoundError:
        return
    for name, module in iter_module_parts("tools"):
        tools = getattr(module, "TOOLS", None)
        if tools:
            register_tools(tools)
            log.info("Đã đăng ký công cụ AI", extra={"tool_module": name, "count": len(tools)})


_register_tools()


def check_database() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def worker_lag_seconds() -> int | None:
    try:
        with get_engine().connect() as conn:
            last = conn.execute(text("SELECT max(last_finished_at) FROM tab_job_schedule")).scalar()
    except Exception:
        return None
    if last is None:
        return None
    return int((clock.now() - last).total_seconds())


@app.get("/api/health")
def read_health() -> JSONResponse:
    db_ok = check_database()
    lag = worker_lag_seconds() if db_ok else None
    healthy = db_ok and (lag is None or lag < 300)
    data = {
        "status": "ok" if healthy else "degraded",
        "db": db_ok,
        "worker_lag_seconds": lag,
        "version": settings.app_version,
        "git_sha": settings.git_sha,
    }
    message = "" if db_ok else "Không kết nối được cơ sở dữ liệu."
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={"success": db_ok, "message": message, "data": data},
    )
