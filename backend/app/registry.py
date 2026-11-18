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
    "search",
    "system",
]
# Tích hợp ngoài ở app/integrations/<tên>/; không import modules, module cài store cho nó (10 mục 3.4).
ENABLED_INTEGRATIONS = ["google"]


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
    """Trả (tên module, đối tượng) của `router`, `tools`, `jobs` cho các module có tệp đó."""
    for module in ENABLED_MODULES:
        loaded = _import_if_exists(f"app.modules.{module}.{part}")
        if loaded is not None:
            yield module, loaded


def iter_integration_parts(part: str):
    for integration in ENABLED_INTEGRATIONS:
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


def approval_executor(tool_name: str):
    """Hàm `(session, user, input) -> dict` chạy việc đã duyệt, khai ở `modules/<tên>/approvals.py`
    (`EXECUTORS = {tool_name: hàm}`). Không có thì chat dùng `execute` của công cụ AI."""
    for _name, module in iter_module_parts("approvals"):
        executor = getattr(module, "EXECUTORS", {}).get(tool_name)
        if executor is not None:
            return executor
    return None
