"""Danh sách module bật và nạp model (gốc ghép, 10 mục 3.4)."""

import importlib
import importlib.util

ENABLED_MODULES = [
    "setting",
    "memory",
    "chat",
    "file",
    "device",
    "expense",
    "inbox",
    "calendar",
    "task",
    "trip",
    "booking",
    "gym",
    "zalo",
    "claude_job",
    "search",
    "report",
    "notice",
    "system",
]
# Tích hợp ngoài ở app/integrations/<tên>/; không import modules, module cài store cho nó (10 mục 3.4).
ENABLED_INTEGRATIONS = ["google", "connectors"]

# Tính năng dở sau cờ (luật điều phối 25/11): cờ tắt thì phần `router`, `tools`, `approvals`, `jobs` không nạp;
# `models` luôn nạp để khớp migration.
FEATURE_FLAGS = {
    "gym": "feature_gym",
    "connectors": "feature_connectors",
    "zalo": "feature_zalo_bridge",
    "claude_job": "feature_claude_worker",
}


def feature_enabled(name: str) -> bool:
    """Module hoặc tích hợp `name` có bật không (không có cờ thì luôn bật)."""
    from app.core.config import get_settings

    flag = FEATURE_FLAGS.get(name)
    return flag is None or bool(getattr(get_settings(), flag, False))


def features() -> dict[str, bool]:
    """Cờ cho app (`GET /system/status`): gym, connectors, zalo_bridge."""
    from app.core.config import get_settings

    s = get_settings()
    return {
        "gym": s.feature_gym,
        "connectors": s.feature_connectors,
        "zalo_bridge": s.feature_zalo_bridge,
        "claude_worker": s.feature_claude_worker,
    }


def _import_if_exists(name: str):
    try:
        if importlib.util.find_spec(name) is None:
            return None
    except ModuleNotFoundError:
        return None
    return importlib.import_module(name)


def import_all_models() -> None:
    importlib.import_module("app.core.models")
    _import_if_exists("app.ai.models")
    for module in ENABLED_MODULES:
        _import_if_exists(f"app.modules.{module}.models")
    for integration in ENABLED_INTEGRATIONS:
        _import_if_exists(f"app.integrations.{integration}.models")


def iter_module_parts(part: str):
    """Trả (tên module, đối tượng) của `router`, `tools`, `jobs` cho các module có tệp đó (bỏ module tắt cờ)."""
    for module in ENABLED_MODULES:
        if part != "models" and not feature_enabled(module):
            continue
        loaded = _import_if_exists(f"app.modules.{module}.{part}")
        if loaded is not None:
            yield module, loaded


def iter_integration_parts(part: str):
    for integration in ENABLED_INTEGRATIONS:
        if part != "models" and not feature_enabled(integration):
            continue
        loaded = _import_if_exists(f"app.integrations.{integration}.{part}")
        if loaded is not None:
            yield integration, loaded


def register_integrations() -> None:
    """Gọi một lần lúc api và worker khởi động: module calendar, task cài store cho đồng bộ Google.

    Module có `google_store.py` khai `STORE`; chưa có (trước 3-02) thì job Google bỏ qua và ghi log.
    """
    google_stores = _import_if_exists("app.integrations.google.stores")
    if google_stores is None:
        return
    calendar = _import_if_exists("app.modules.calendar.google_store")
    if calendar is not None:
        google_stores.register_calendar_store(calendar.STORE)
    task = _import_if_exists("app.modules.task.google_store")
    if task is not None:
        google_stores.register_task_store(task.STORE)
    files = _import_if_exists("app.modules.file.google_store")
    if files is not None and hasattr(google_stores, "register_file_store"):
        google_stores.register_file_store(files.STORE)
    mail = _import_if_exists("app.modules.inbox.google_store")
    if mail is not None and hasattr(google_stores, "register_mail_store"):
        google_stores.register_mail_store(mail.STORE)
    booking = _import_if_exists("app.modules.booking.google_store")
    if booking is not None and hasattr(google_stores, "register_booking_store"):
        google_stores.register_booking_store(booking.STORE)


def approval_executor(tool_name: str):
    """Hàm `(session, user, input) -> dict` chạy việc đã duyệt, khai ở `modules/<tên>/approvals.py`
    (`EXECUTORS = {tool_name: hàm}`). Không có thì chat dùng `execute` của công cụ AI."""
    for _name, module in iter_module_parts("approvals"):
        executor = getattr(module, "EXECUTORS", {}).get(tool_name)
        if executor is not None:
            return executor
    return None
