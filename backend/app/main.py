"""Khung tối thiểu do agent hạ tầng dựng (việc 0-06): chỉ có GET /api/health.

Agent kiến trúc thay tệp này bằng gốc ghép thật (docs/10-backend/10-kien-truc-backend.md):
cấu hình ở core/config.py, kết nối DB ở core/db.py, phong bì lỗi ở core/errors.py.
"""

import os
from functools import lru_cache

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

app = FastAPI(title="troly", docs_url=None, redoc_url=None)


@lru_cache
def get_engine() -> Engine:
    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True, pool_size=2)


def check_database() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@app.get("/api/health")
def read_health() -> JSONResponse:
    db_ok = check_database()
    data = {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "worker_lag_seconds": None,
        "version": os.environ.get("APP_VERSION", "dev"),
        "git_sha": os.environ.get("GIT_SHA", "dev"),
    }
    message = "" if db_ok else "Không kết nối được cơ sở dữ liệu."
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={"success": db_ok, "message": message, "data": data},
    )
