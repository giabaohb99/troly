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


def from_ai_extract(result, output_model, default_title: str | None = None):
    """Đổi TripExtract của app.ai.trip_ai (chuỗi rỗng thay null, 0 là không rõ) sang lược đồ trip.

    Kiểm lại bằng model của trip (extra="forbid"), nên hai bên lệch trường là lỗi ngay ở đây.
    """
    data = _blank_to_none(result.model_dump())
    if not data.get("title"):
        data["title"] = default_title or "Chuyến đi"
    if data.get("travel_mode") in (None, "unknown"):
        data["travel_mode"] = "motorbike"
    for fact in data.get("facts", []):
        if not fact.get("day_no"):
            fact["day_no"] = None
    _drop_unnamed(data)
    return output_model.model_validate(data)


def _drop_unnamed(data: dict) -> None:
    """Model đôi khi để trống trường tên bắt buộc (gặp thật: khách sạn đêm 1 không tên khi đọc ảnh).
    Thiếu một mục không được làm hỏng cả chuyến: lấy tên thay thế nếu có, không thì bỏ mục đó."""
    hotels = []
    for hotel in data.get("hotels") or []:
        backups = [
            b if isinstance(b, dict) else {"label": b, "url": None, "role": "backup"}
            for b in hotel.get("backups") or []
        ]
        backups = [b for b in backups if b.get("label")]
        if not hotel.get("label") and backups:
            hotel["label"], hotel["url"] = backups[0]["label"], backups[0].get("url") or hotel.get("url")
            backups = backups[1:]
        hotel["backups"] = backups
        if hotel.get("label"):
            hotels.append(hotel)
    data["hotels"] = hotels
    for day in data.get("days") or []:
        stops = []
        for stop in day.get("stops") or []:
            stop["places"] = [p for p in stop.get("places") or [] if p.get("label")]
            if not stop.get("title") and stop["places"]:
                stop["title"] = stop["places"][0]["label"]
            if stop.get("title"):
                stops.append(stop)
        day["stops"] = stops
    data["map_links"] = [m for m in data.get("map_links") or [] if m.get("url")]
    for link in data["map_links"]:
        link["label"] = link.get("label") or "Bản đồ"
    data["facts"] = [f for f in data.get("facts") or [] if f.get("text")]
    data["notes"] = [n for n in data.get("notes") or [] if n]


def extract_trip(user_id: int, content, output_model, hint: str | None = None, default_title: str | None = None):
    """Haiku bóc tách (app.ai.trip_ai.extract_trip, agent AI giữ). content là chữ hoặc khối PDF, ảnh."""
    mod = _optional("app.ai.trip_ai")
    if mod is None or not hasattr(mod, "extract_trip"):
        raise TripAiUnavailable()
    if isinstance(content, list):
        result = mod.extract_trip(user_id, files=content, hint=hint)
    else:
        result = mod.extract_trip(user_id, text=content, hint=hint)
    return from_ai_extract(result, output_model, default_title) if result is not None else None


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


def _plain(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        return asdict(value)
    return dict(value)


def estimate_legs(
    user_id: int,
    trip_title: str,
    region: str | None,
    stops: list[dict],
    legs: list[dict],
    think: bool,
    travel_mode: str = "motorbike",
) -> dict | None:
    """AI ước tính chặng thay Routes (QĐ-36; app.ai.trip_legs.estimate_legs). think: tìm web giờ mở cửa, phà cuối.

    Trả {legs: [{from_stop_id, to_stop_id, km, minutes, ferry_minutes, note}], checks: [...], sources: [...]}.
    """
    mod = _optional("app.ai.trip_legs")
    if mod is None or not hasattr(mod, "estimate_legs"):
        return None
    try:
        result = mod.estimate_legs(
            user_id,
            trip_title=trip_title,
            region=region,
            stops=stops,
            legs=legs,
            think=think,
            travel_mode=travel_mode,
        )
    except Exception:
        return None
    if result is None:
        return None
    data = _plain(result)
    data["legs"] = [_plain(x) for x in data.get("legs") or []]
    data["checks"] = [_plain(x) for x in data.get("checks") or []]
    return data


def _file_service():
    return importlib.import_module("app.modules.file.service")


def read_file_bytes(session: Session, user_id: int, file_id: int) -> tuple[bytes, str, str | None]:
    return _file_service().read_file_bytes(session, user_id, file_id)


def claude_blocks(session: Session, user_id: int, file_ids: list[int]) -> list[dict]:
    """Khối image, document thật cho Claude. build_claude_blocks chỉ trả khối giữ chỗ troly_file (để lưu
    tin chat); gửi thẳng khối giữ chỗ thì Claude trả 400, nên phải materialize ở đây."""
    files = _file_service()
    return files.materialize_blocks(session, user_id, files.build_claude_blocks(session, user_id, file_ids))


def store_generated_file(
    session: Session, user_id: int, data: bytes, mime: str, filename: str, purpose: str
) -> dict:
    return _file_service().store_generated_file(session, user_id, data, mime, filename, purpose)


def setting_values(session: Session, user_id: int) -> dict:
    return importlib.import_module("app.modules.setting.service").get_all(session, user_id)


def create_calendar_event(session: Session, user, data: dict) -> dict:
    return importlib.import_module("app.modules.calendar.service").create_event(session, user, data)


def request_drive_upload(session: Session, user_id: int, file_id: int) -> bool:
    """Đặt lệnh lưu tệp lên thư mục Trợ lý trên Drive; chưa nối gói drive thì trả False (40 mục 8)."""
    from app.integrations.google import drive
    from app.integrations.google.errors import GoogleNotConnected

    try:
        drive.request_upload(session, user_id, file_id)
    except GoogleNotConnected:
        return False
    return True
