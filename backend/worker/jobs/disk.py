"""Kiểm ổ đĩa (10 mục 3.9): dưới DISK_WARN_PERCENT cảnh báo, dưới DISK_STOP_PERCENT tạm dừng việc ghi nhiều."""

import shutil

from app.core.config import get_settings

STATE = {"state": "ok", "free_percent": None}


def disk_check() -> tuple[int, dict]:
    usage = shutil.disk_usage("/")
    free = round(usage.free * 100 / usage.total, 1)
    s = get_settings()
    state = "stop" if free < s.disk_stop_percent else "warn" if free < s.disk_warn_percent else "ok"
    STATE.update(state=state, free_percent=free)
    return 1, {"free_percent": free, "state": state, "free_bytes": usage.free, "total_bytes": usage.total}


def heavy_jobs_paused() -> bool:
    return STATE["state"] == "stop"
