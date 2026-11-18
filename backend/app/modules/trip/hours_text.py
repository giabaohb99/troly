"""Giờ mở cửa đọc từ chữ (QĐ-36): câu trong tệp, ghi chú người dùng, hoặc kết quả tìm web của AI.

Đổi thành cấu trúc giống `regularOpeningHours` của Google để luật R2 dùng chung. Câu có *có thể* thì
đánh dấu `maybe`, luật hạ từ đỏ xuống vàng. Không đọc được gì thì trả None và R2 không báo.
"""

import re

from app.modules.trip.normalize import fold

DAY_WORDS = {
    "thu 2": 0, "thu hai": 0, "thu 3": 1, "thu ba": 1, "thu 4": 2, "thu tu": 2, "thu 5": 3, "thu nam": 3,
    "thu 6": 4, "thu sau": 4, "thu 7": 5, "thu bay": 5, "chu nhat": 6, "cn": 6,
}  # fmt: skip
CLOSED_RE = re.compile(
    r"(co the\s+)?(?:dong cua|nghi)\s+(?:vao\s+|ngay\s+)?((?:thu\s*(?:2|3|4|5|6|7|hai|ba|tu|nam|sau|bay)|chu nhat)"
    r"(?:\s*(?:,|va|hoac)\s*(?:thu\s*(?:2|3|4|5|6|7|hai|ba|tu|nam|sau|bay)|chu nhat))*)"
)
OPEN_RE = re.compile(
    r"(?:mo cua|gio mo cua|mo)\D{0,12}(\d{1,2})\s*[h:]\s*(\d{2})?\s*(?:-|–|den|toi)\s*(\d{1,2})\s*[h:]\s*(\d{2})?"
)


def _days(text: str) -> list[int]:
    found = []
    for part in re.split(r"\s*(?:,|va|hoac)\s*", text):
        key = re.sub(r"\s+", " ", part.strip())
        if key in DAY_WORDS:
            found.append(DAY_WORDS[key])
    return found


def build_hours(
    closed: list[int], open_min: int = 0, close_min: int = 23 * 60 + 59, maybe: bool = False
) -> dict:
    """closed theo Python (0 là thứ Hai); periods theo Google (0 là Chủ nhật)."""
    periods = []
    for wd in range(7):
        if wd in closed:
            continue
        gday = (wd + 1) % 7
        periods.append(
            {
                "open": {"day": gday, "hour": open_min // 60, "minute": open_min % 60},
                "close": {"day": gday, "hour": close_min // 60, "minute": close_min % 60},
            }
        )
    return {"regular": {"periods": periods}, "maybe": maybe, "source": "text"}


def hours_from_text(*texts: str | None) -> dict | None:
    joined = fold(" . ".join(t for t in texts if t))
    if not joined:
        return None
    closed: list[int] = []
    maybe = False
    for m in CLOSED_RE.finditer(joined):
        closed += _days(m.group(2))
        maybe = maybe or bool(m.group(1))
    opening = OPEN_RE.search(joined)
    if not closed and not opening:
        return None
    open_min, close_min = 0, 23 * 60 + 59
    if opening:
        open_min = int(opening.group(1)) * 60 + int(opening.group(2) or 0)
        close_min = int(opening.group(3)) * 60 + int(opening.group(4) or 0)
    return build_hours(sorted(set(closed)), open_min, close_min, maybe)


def hours_from_ai(item: dict) -> dict | None:
    """Kết quả tìm web của AI: {closed_weekdays, open, close, text, source}."""
    closed = [int(d) for d in item.get("closed_weekdays") or [] if 0 <= int(d) <= 6]

    def minutes(value: str | None, default: int) -> int:
        if not value or ":" not in value:
            return default
        h, m = value.split(":")[:2]
        return int(h) * 60 + int(m)

    if not closed and not item.get("open"):
        return hours_from_text(item.get("text"))
    out = build_hours(closed, minutes(item.get("open"), 0), minutes(item.get("close"), 23 * 60 + 59))
    out["source"] = item.get("source") or "web"
    return out
