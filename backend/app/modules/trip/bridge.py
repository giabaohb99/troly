"""Chỗ trip gọi sang tầng AI (agent AI, 4-02) và module file (agent kiến trúc).

Gom một chỗ để module không import ruột nơi khác và để bài kiểm thay được. Hàm bên kia chưa có thì báo
lỗi tiếng Việt thay vì ngã cả việc nền.
"""

import importlib
import importlib.util

from sqlalchemy.orm import Session

from app.core.errors import AppError


class TripAiUnavailable(AppError):
    status = 503
    code = "AI_UNAVAILABLE"
    message = "Chưa có bộ đọc lịch trình, thử lại sau."


def _optional(name: str):
    try:
        if importlib.util.find_spec(name) is None:
            return None
    except ModuleNotFoundError:
        return None
    return importlib.import_module(name)


def _blank_to_none(value):
    if isinstance(value, dict):
        return {k: _blank_to_none(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_blank_to_none(v) for v in value]
    return None if value == "" else value


def from_ai_extract(result, output_model):
    """Đổi TripExtract của app.ai.trip_ai (chuỗi rỗng thay null, 0 là không rõ) sang lược đồ trip.

    Kiểm lại bằng model của trip (extra="forbid"), nên hai bên lệch trường là lỗi ngay ở đây.
    """
    data = _blank_to_none(result.model_dump())
    if data.get("travel_mode") in (None, "unknown"):
        data["travel_mode"] = "motorbike"
    for fact in data.get("facts", []):
        if not fact.get("day_no"):
            fact["day_no"] = None
    for hotel in data.get("hotels", []):
        hotel["backups"] = [
            b if isinstance(b, dict) else {"label": b, "url": None, "role": "backup"}
            for b in hotel.get("backups") or []
        ]
    return output_model.model_validate(data)


def extract_trip(user_id: int, content, output_model, hint: str | None = None):
    """Haiku bóc tách (app.ai.trip_ai.extract_trip, agent AI giữ). content là chữ hoặc khối PDF, ảnh."""
    mod = _optional("app.ai.trip_ai")
    if mod is None or not hasattr(mod, "extract_trip"):
        raise TripAiUnavailable()
    if isinstance(content, list):
        result = mod.extract_trip(user_id, files=content, hint=hint)
    else:
        result = mod.extract_trip(user_id, text=content, hint=hint)
    return from_ai_extract(result, output_model) if result is not None else None


def summarize_options(user_id: int, trip_title: str, options: list[dict]) -> dict[int, dict]:
    """Sonnet viết tóm tắt từng phương án (app.ai.trip_ai.summarize_options). Trả {option_id: {summary, tips}}."""
    mod = _optional("app.ai.trip_ai")
    if mod is None or not hasattr(mod, "summarize_options"):
        return {}
    try:
        items = mod.summarize_options(user_id, trip_title=trip_title, options=options) or []
    except Exception:
        return {}
    return {i.option_id: {"summary": i.summary, "tips": list(i.tips)} for i in items}


def _file_service():
    return importlib.import_module("app.modules.file.service")


def read_file_bytes(session: Session, user_id: int, file_id: int) -> tuple[bytes, str, str | None]:
    return _file_service().read_file_bytes(session, user_id, file_id)


def claude_blocks(session: Session, user_id: int, file_ids: list[int]) -> list[dict]:
    return _file_service().build_claude_blocks(session, user_id, file_ids)


def store_generated_file(
    session: Session, user_id: int, data: bytes, mime: str, filename: str, purpose: str
) -> dict:
    return _file_service().store_generated_file(session, user_id, data, mime, filename, purpose)


def setting_values(session: Session, user_id: int) -> dict:
    return importlib.import_module("app.modules.setting.service").get_all(session, user_id)


def create_calendar_event(session: Session, user, data: dict) -> dict:
    return importlib.import_module("app.modules.calendar.service").create_event(session, user, data)
