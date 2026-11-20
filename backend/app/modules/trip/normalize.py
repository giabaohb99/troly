"""Chuẩn hóa kết quả bóc tách thành điểm dừng (41 mục 3.2 tới 3.4)."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.modules.trip.reader import links_in, parse_latlng, parse_maps_url
from app.modules.trip.schemas import TripExtract

DEFAULT_STAY = {"an_uong": 45, "tham_quan": 60, "mua_sam": 20, "nghi": 15, "via": 0, "pha": 30}
TIME_RE = re.compile(r"(~)?\s*(\d{1,2})\s*h\s*(\d{2})?")
WEEKDAYS = {"thu 2": 0, "thu hai": 0, "thu 3": 1, "thu ba": 1, "thu 4": 2, "thu tu": 2, "thu 5": 3, "thu nam": 3,
            "thu 6": 4, "thu sau": 4, "thu 7": 5, "thu bay": 5, "chu nhat": 6, "cn": 6}  # fmt: skip
FIXED_WORDS = ("binh minh", "hoang hon")


def fold(text: str | None) -> str:
    """Chữ thường, bỏ dấu, gộp khoảng trắng (khóa lưu đệm, so khớp tên)."""
    if not text:
        return ""
    value = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    value = "".join(c for c in value if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s,./-]", " ", value)).strip()


@dataclass
class ParsedTime:
    start: time | None
    end: time | None
    approx: bool


def parse_time_text(text: str | None) -> ParsedTime:
    """`2h30` là 02:30; `~7h00` kèm approx; `10h30–12h30` là khoảng (41 mục 3.2)."""
    if not text:
        return ParsedTime(None, None, False)
    found = TIME_RE.findall(text)
    if not found:
        return ParsedTime(None, None, "~" in text)

    def to_time(item) -> time | None:
        h, m = int(item[1]), int(item[2] or 0)
        return time(h % 24, m) if h <= 24 and m < 60 else None

    start = to_time(found[0])
    end = to_time(found[1]) if len(found) > 1 else None
    return ParsedTime(start, end, "~" in text)


def weekday_of(text: str | None) -> int | None:
    key = fold(text)
    for name, value in WEEKDAYS.items():
        if key.startswith(name) or key == name:
            return value
    return None


def suggest_start_date(first_weekday: int | None, today: date) -> date:
    """Thứ Bảy gần nhất khớp thứ của ngày 1; người dùng bấm xác nhận (QĐ-26)."""
    target = 5 if first_weekday is None else first_weekday
    delta = (target - today.weekday()) % 7
    return today + timedelta(days=delta or 7)


@dataclass
class StopDraft:
    day_no: int
    title: str
    category: str
    role: str = "main"
    parent: int | None = None  # chỉ số StopDraft của điểm chính
    time_text: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    approx: bool = False
    fixed: bool = False
    optional: bool = False
    stay_minutes: int | None = None
    place_query: str | None = None
    area: str | None = None
    source_url: str | None = None
    place_id: str | None = None
    lat: float | None = None
    lng: float | None = None
    coord_source: str | None = None
    phone: str | None = None
    cost_note: str | None = None
    note: str | None = None
    short_link: str | None = None


@dataclass
class Normalized:
    start_date: date
    date_suggested: bool
    stops: list[StopDraft]
    facts: list[dict]
    errors: list[str] = field(default_factory=list)


def check_extract(extract: TripExtract, source_text: str | None) -> list[str]:
    """Kiểm đầu ra bóc tách: link phải có trong văn bản gốc, giờ tăng dần, số ngày (41 mục 3.2)."""
    errors: list[str] = []
    allowed = links_in(source_text) if source_text else None
    for day in extract.days:
        last: time | None = None
        for stop in day.stops:
            for place in stop.places:
                if allowed is not None and place.url and place.url not in allowed:
                    errors.append(f"Link không có trong tệp: {place.url[:80]}")
            parsed = parse_time_text(stop.time_text)
            if parsed.start and not parsed.approx and last and parsed.start < last and parsed.start.hour >= 4:
                errors.append(f"Ngày {day.day_no}: giờ {stop.time_text} lùi so với điểm trước")
            if parsed.start and not parsed.approx:
                last = parsed.start
    if source_text:
        heads = len(re.findall(r"^#{1,3}\s*Ngày\s+\d+", source_text, flags=re.M | re.I))
        if heads and heads != len(extract.days):
            errors.append(f"Tệp có {heads} ngày nhưng bóc ra {len(extract.days)} ngày")
    return errors


def normalize(extract: TripExtract, tz: str, today: date) -> Normalized:
    zone = ZoneInfo(tz)
    first_weekday = weekday_of(extract.days[0].weekday_text) if extract.days else None
    if extract.start_date:
        start = date.fromisoformat(extract.start_date)
        suggested = False
    elif extract.days and extract.days[0].date:
        start = date.fromisoformat(extract.days[0].date)
        suggested = False
    else:
        start = suggest_start_date(first_weekday, today)
        suggested = True

    drafts: list[StopDraft] = []
    for day in extract.days:
        day_date = start + timedelta(days=day.day_no - 1)
        for stop in day.stops:
            parsed = parse_time_text(stop.time_text)
            mains = [p for p in stop.places if p.role in ("main", "via", "generic")]
            others = [p for p in stop.places if p.role in ("alternative", "backup")]
            entries = mains or [None]
            first_index = None
            for i, place in enumerate(entries):
                role = place.role if place else "main"
                category = "di_chuyen" if role == "via" else stop.category
                d = StopDraft(
                    day_no=day.day_no,
                    title=(place.label if place and len(entries) > 1 else stop.title)[:500],
                    category=category,
                    role=role,
                    optional=stop.optional,
                    phone=stop.phone,
                    cost_note=stop.cost_note,
                    note=stop.note,
                    area=(stop.area or None) and stop.area.strip()[:200],
                )
                if i == 0:
                    d.time_text = stop.time_text
                    d.approx = parsed.approx
                    if parsed.start:
                        d.planned_start = datetime.combine(day_date, parsed.start, zone)
                    if parsed.end and d.planned_start:
                        d.planned_end = datetime.combine(day_date, parsed.end, zone)
                        if d.planned_end <= d.planned_start:
                            d.planned_end += timedelta(days=1)
                        d.stay_minutes = int((d.planned_end - d.planned_start).total_seconds() // 60)
                if d.stay_minutes is None:
                    d.stay_minutes = DEFAULT_STAY.get("via" if role == "via" else category, 30)
                if place is not None:
                    _apply_link(d, place.label, place.url)
                titled = fold(d.title)
                d.fixed = bool(
                    d.planned_start
                    and not d.approx
                    and (category in ("pha", "khach_san") or any(w in titled for w in FIXED_WORDS))
                )
                drafts.append(d)
                if i == 0:
                    first_index = len(drafts) - 1
            for place in others:
                child = StopDraft(
                    day_no=day.day_no,
                    title=place.label[:500],
                    category=stop.category,
                    role=place.role,
                    parent=first_index,
                    stay_minutes=DEFAULT_STAY.get(stop.category, 30),
                )
                _apply_link(child, place.label, place.url)
                drafts.append(child)
    _apply_route_coordinates(extract, drafts)
    facts = [
        {
            "kind": f.kind,
            "day_no": f.day_no,
            "value_time": _hhmm(f.value_time),
            "value_text": f.value_text,
            "text": f.text,
        }
        for f in extract.facts
    ]
    return Normalized(start, suggested, drafts, facts)


def _hhmm(value: str | None) -> time | None:
    if not value:
        return None
    parsed = parse_time_text(value.replace(":", "h"))
    return parsed.start


def _apply_link(d: StopDraft, label: str, url: str | None) -> None:
    d.place_query = label
    if not url:
        return
    d.source_url = url
    link = parse_maps_url(url)
    if link.kind == "search":
        d.place_query = link.query or label
        d.place_id = link.place_id
    elif link.kind == "short":
        d.short_link = url
    elif link.kind == "dir" and link.destination:
        point = parse_latlng(link.destination)
        if point:
            d.lat, d.lng, d.coord_source = point[0], point[1], "user"
        else:
            d.place_query = link.destination


def _apply_route_coordinates(extract: TripExtract, drafts: list[StopDraft]) -> None:
    """Điểm đầu, cuối của link tuyến là tọa độ mà chữ mô tả gọi tên một điểm đã biết (41 mục 3.3)."""
    for link in extract.map_links:
        parsed = parse_maps_url(link.url)
        if parsed.kind != "dir":
            continue
        names = [n.strip() for n in re.split(r"→|->", link.label)]
        ends = [(names[0] if names else "", parsed.origin), (names[-1] if names else "", parsed.destination)]
        for name, value in ends:
            point = parse_latlng(value)
            if not point or not name:
                continue
            target = _match_stop(drafts, link.day_no, name)
            if target is not None and target.lat is None:
                target.lat, target.lng, target.coord_source = point[0], point[1], "user"


def _match_stop(drafts: list[StopDraft], day_no: int, name: str) -> StopDraft | None:
    key = fold(name)
    if key in ("khach san", "hotel"):
        for wanted in (day_no, day_no - 1):
            hit = next(
                (d for d in drafts if d.day_no == wanted and d.category == "khach_san" and d.role == "main"),
                None,
            )
            if hit:
                return hit
        return None
    return next((d for d in drafts if d.day_no == day_no and key and key in fold(d.title)), None)
