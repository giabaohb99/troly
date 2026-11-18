"""Danh sách module bật và nạp model (gốc ghép, 10 mục 3.4)."""

import importlib
import importlib.util

ENABLED_MODULES = ["setting", "memory", "chat", "file", "device", "expense", "inbox", "search", "system"]


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


def iter_module_parts(part: str):
    """Trả (tên module, đối tượng) của `router`, `tools`, `jobs` cho các module có tệp đó."""
    for module in ENABLED_MODULES:
        loaded = _import_if_exists(f"app.modules.{module}.{part}")
        if loaded is not None:
            yield module, loaded
