"""Cài đặt người dùng dạng khóa và giá trị (11 mục 3.4). Khóa lạ hoặc sai kiểu bị 400."""

from collections.abc import Callable
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.modules.setting.models import Setting


def _bool(v):
    if isinstance(v, bool):
        return v
    raise ValueError


def _int_range(lo: int, hi: int) -> Callable:
    def check(v):
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise ValueError
        return v

    return check


def _remind_list(v):
    if (
        not isinstance(v, list)
        or len(v) > 5
        or any(isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= 40320 for x in v)
    ):
        raise ValueError
    return sorted(set(v))


def _choice(*values) -> Callable:
    def check(v):
        if v not in values:
            raise ValueError
        return v

    return check


def _hhmm(v):
    time.fromisoformat(v)
    return v


def _quiet_hours(v):
    if v is None:
        return None
    if not isinstance(v, dict) or set(v) != {"start", "end"}:
        raise ValueError
    return {"start": _hhmm(v["start"]), "end": _hhmm(v["end"])}


def _speed(v):
    if isinstance(v, bool) or not isinstance(v, int | float) or not 0.5 <= v <= 3:
        raise ValueError
    return float(v)


FERRY_FIELDS = ("name", "place_query", "first_time", "last_time", "hotline", "note", "updated_at")


def _ferries(v):
    """Giờ phà quen (QĐ-26 câu 28, 41 mục 5.4): tối đa 10 bến."""
    if not isinstance(v, list) or len(v) > 10:
        raise ValueError
    out = []
    for item in v:
        if not isinstance(item, dict) or set(item) - set(FERRY_FIELDS):
            raise ValueError
        name = item.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError
        for key in ("place_query", "hotline", "note"):
            value = item.get(key)
            if value is not None and (not isinstance(value, str) or len(value) > 300):
                raise ValueError
        for key in ("first_time", "last_time"):
            if item.get(key) is not None:
                _hhmm(item[key])
        if item.get("updated_at") is not None:
            date.fromisoformat(item["updated_at"])
        out.append({key: item.get(key) for key in FERRY_FIELDS} | {"name": name.strip()})
    return out


# khóa: (mặc định, hàm kiểm, câu lỗi)
REGISTRY: dict[str, tuple[object, Callable, str]] = {
    "ui.voice_reply": (False, _bool, "Phải là true hoặc false."),
    "calendar.default_remind_minutes": ([15], _remind_list, "Danh sách tối đa 5 số phút, từ 0 tới 40320."),
    "calendar.week_start": (1, _int_range(1, 7), "Từ 1 (thứ Hai) tới 7 (chủ nhật)."),
    "expense.default_account": (
        "cash",
        _choice("vcb", "tcb", "momo", "cash", "card", "other"),
        "Tài khoản không hợp lệ.",
    ),
    "inbox.ai_enabled": (True, _bool, "Phải là true hoặc false."),
    # QĐ-38: báo trên máy khi ghi giao dịch mới (mặc định tắt), khi có tin quan trọng (mặc định bật);
    # app nhắc cả sự kiện tạo trên Google (mặc định tắt, Google tự nhắc).
    "notify.new_transaction": (False, _bool, "Phải là true hoặc false."),
    "notify.important_message": (True, _bool, "Phải là true hoặc false."),
    # QĐ-41: lượt chat xong khi app không ở màn hình thì máy báo (mặc định bật).
    "notify.chat_done": (True, _bool, "Phải là true hoặc false."),
    # QĐ-49: đặt chỗ tự thêm vào Lịch từ thư xác nhận thì máy báo, có nút Hoàn tác (mặc định bật).
    "notify.booking_added": (True, _bool, "Phải là true hoặc false."),
    "calendar.app_reminds_google": (False, _bool, "Phải là true hoặc false."),
    "inbox.quiet_hours": (None, _quiet_hours, 'Dạng {start: "22:00", end: "07:00"} hoặc null.'),
    "trip.default_travel_mode": (
        "motorbike",
        _choice("motorbike", "car", "walk"),
        "Chỉ nhận motorbike, car, walk.",
    ),
    "trip.night_start": ("18:00", _hhmm, "Giờ dạng HH:MM."),
    "trip.night_end": ("05:30", _hhmm, "Giờ dạng HH:MM."),
    "trip.ride_break_minutes": (90, _int_range(15, 600), "Từ 15 tới 600 phút."),
    "trip.speed_factor": (1.2, _speed, "Từ 0,5 tới 3."),
    "trip.ferries": (
        [],
        _ferries,
        "Tối đa 10 bến: {name, place_query, first_time HH:MM, last_time HH:MM, hotline, note, updated_at YYYY-MM-DD}.",
    ),
}


def defaults() -> dict:
    return {k: v[0] for k, v in REGISTRY.items()}


def get_all(session: Session, user_id: int) -> dict:
    rows = dict(session.execute(select(Setting.key, Setting.value).where(Setting.user_id == user_id)).all())
    values = {k: rows.get(k, d) for k, d in defaults().items()}
    return {"values": values, "defaults": defaults()}


def get_value(session: Session, user_id: int, key: str):
    if key not in REGISTRY:
        raise KeyError(key)
    value = session.scalar(select(Setting.value).where(Setting.user_id == user_id, Setting.key == key))
    return REGISTRY[key][0] if value is None else value


def update(session: Session, user_id: int, changes: dict) -> dict:
    errors: dict[str, str] = {}
    clean: dict = {}
    for key, value in changes.items():
        spec = REGISTRY.get(key)
        if spec is None:
            errors[key] = "Khóa cài đặt không tồn tại."
            continue
        try:
            clean[key] = spec[1](value)
        except (ValueError, TypeError, KeyError):
            errors[key] = spec[2]
    if errors:
        raise ValidationError("Cài đặt chưa hợp lệ.", fields=errors)
    for key, value in clean.items():
        stmt = insert(Setting).values(user_id=user_id, key=key, value=value)
        session.execute(stmt.on_conflict_do_update(index_elements=["user_id", "key"], set_={"value": value}))
    return get_all(session, user_id)["values"]
