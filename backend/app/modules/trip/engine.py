"""Lõi đánh giá lịch trình, thuần, không DB (41 mục 5).

Mô phỏng giờ đến từng điểm theo thời gian chạy, chạy 9 luật R1 tới R9 bằng mã, sắp thứ tự trong khung
giữa các mốc cứng, dựng 3 phương án. Claude chỉ viết tóm tắt sau đó, không đổi số.
"""

import itertools
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.modules.trip.normalize import fold, weekday_of

WEEKDAY_VI = ["thứ Hai", "thứ Ba", "thứ Tư", "thứ Năm", "thứ Sáu", "thứ Bảy", "Chủ nhật"]
HEAVY_ROADS = ("ql1", "ql 1", "quoc lo 1", "ql51", "ql 51", "quoc lo 51")
MAX_PERMUTE = 8


@dataclass
class Settings:
    tz: str = "Asia/Ho_Chi_Minh"
    night_start: time = time(18, 0)
    night_end: time = time(5, 30)
    ride_break_minutes: int = 90
    speed_factor: float = 1.2
    ferries: list[dict] = field(default_factory=list)


@dataclass
class PStop:
    id: int
    day_no: int
    title: str
    category: str
    role: str = "main"
    fixed: bool = False
    optional: bool = False
    approx: bool = False
    planned_start: datetime | None = None
    stay_minutes: int = 30
    lat: float | None = None
    lng: float | None = None
    place_query: str | None = None
    place_id: str | None = None
    hours: dict | None = None  # kết quả maps.opening_hours; None là chưa tra
    hours_checked: bool = False

    @property
    def located(self) -> bool:
        return self.lat is not None and self.lng is not None

    @property
    def point(self) -> tuple[float, float]:
        return (float(self.lat), float(self.lng))


@dataclass
class PLeg:
    minutes: float
    km: float
    instructions: list[str] = field(default_factory=list)


@dataclass
class PDay:
    day_no: int
    date: date
    weekday_text: str | None
    stops: list[PStop]


@dataclass
class Fact:
    kind: str
    day_no: int | None
    value_time: time | None
    stop_id: int | None = None
    text: str = ""


@dataclass
class Timed:
    stop: PStop
    arrive: datetime
    begin: datetime
    depart: datetime
    leg_minutes: float | None
    leg_km: float | None


@dataclass
class Ride:
    start: datetime
    end: datetime
    km: float
    instructions: list[str]
    to_stop: int


@dataclass
class DayResult:
    day_no: int
    timed: list[Timed]
    rides: list[Ride]

    @property
    def ride_minutes(self) -> float:
        return sum((r.end - r.start).total_seconds() / 60 for r in self.rides)

    @property
    def km(self) -> float:
        return sum(r.km for r in self.rides)


LegKey = tuple[tuple[float, float], tuple[float, float]]


def leg_key(a: PStop, b: PStop) -> LegKey:
    return (round(a.point[0], 5), round(a.point[1], 5)), (round(b.point[0], 5), round(b.point[1], 5))


# ---------- Mô phỏng ----------


def simulate(day: PDay, legs: dict[LegKey, PLeg], cfg: Settings) -> DayResult:
    zone = ZoneInfo(cfg.tz)
    default_start = datetime.combine(day.date, time(8, 0), zone)
    clock = None
    prev_located: PStop | None = None
    timed: list[Timed] = []
    rides: list[Ride] = []
    for stop in day.stops:
        leg = None
        if clock is None:
            arrive = stop.planned_start or default_start
        else:
            arrive = clock
            if stop.located and prev_located is not None:
                leg = legs.get(leg_key(prev_located, stop))
                if leg is not None and leg.minutes > 0:
                    ride = timedelta(minutes=leg.minutes * cfg.speed_factor)
                    rides.append(Ride(clock, clock + ride, leg.km, leg.instructions, stop.id))
                    arrive = clock + ride
        begin = max(arrive, stop.planned_start) if stop.planned_start else arrive
        depart = begin + timedelta(minutes=stop.stay_minutes or 0)
        timed.append(
            Timed(
                stop,
                arrive,
                begin,
                depart,
                round(leg.minutes * cfg.speed_factor) if leg else None,
                round(leg.km, 1) if leg else None,
            )
        )
        clock = depart
        if stop.located:
            prev_located = stop
    return DayResult(day.day_no, timed, rides)


# ---------- Luật rủi ro ----------


def _risk(code, level, day_no, stop_id, message, suggestion, checked_at) -> dict:
    return {
        "code": code,
        "level": level,
        "day_no": day_no,
        "stop_id": stop_id,
        "message": message,
        "suggestion": suggestion,
        "checked_at": checked_at,
    }


def _local(at: datetime, cfg: Settings) -> datetime:
    return at.astimezone(ZoneInfo(cfg.tz))


def _overlap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> float:
    return max(0.0, (min(a1, b1) - max(a0, b0)).total_seconds() / 60)


def _night_windows(ride: Ride, cfg: Settings) -> tuple[float, float]:
    """Trả (phút trong khung đêm, phút trong khung 03:00 tới 05:00)."""
    zone = ZoneInfo(cfg.tz)
    night = deep = 0.0
    start_day = _local(ride.start, cfg).date() - timedelta(days=1)
    for offset in range(3):
        d = start_day + timedelta(days=offset)
        n0 = datetime.combine(d, cfg.night_start, zone)
        n1 = datetime.combine(d + timedelta(days=1), cfg.night_end, zone)
        night += _overlap(ride.start, ride.end, n0, n1)
        deep += _overlap(
            ride.start,
            ride.end,
            datetime.combine(d, time(3, 0), zone),
            datetime.combine(d, time(5, 0), zone),
        )
    return night, deep


def _hours_status(hours: dict, begin: datetime, stay: int, cfg: Settings) -> tuple[str | None, str]:
    """('red'|'yellow'|None, câu). Google: day 0 là Chủ nhật; không giả định phần tử đầu là Chủ nhật."""
    if hours.get("business_status") == "CLOSED_PERMANENTLY":
        return "red", "đã đóng cửa hẳn"
    block = hours.get("current") or hours.get("regular")
    periods = (block or {}).get("periods") or []
    if not periods:
        return "yellow", "chưa rõ giờ mở cửa"
    local = _local(begin, cfg)
    gday = (local.weekday() + 1) % 7
    today = [p for p in periods if (p.get("open") or {}).get("day") == gday]
    if any("close" not in p for p in periods):
        return None, ""  # mở 24 giờ
    if not today:
        return "red", f"đóng cửa {WEEKDAY_VI[local.weekday()]}"
    minute = local.hour * 60 + local.minute
    for p in today:
        o, c = p["open"], p["close"]
        start = o.get("hour", 0) * 60 + o.get("minute", 0)
        end = c.get("hour", 0) * 60 + c.get("minute", 0) + (24 * 60 if c.get("day") != o.get("day") else 0)
        if start <= minute < end:
            if end - minute < 30 or minute + stay > end:
                return "yellow", "tới sát giờ đóng cửa"
            return None, ""
    return "red", "tới ngoài giờ mở cửa"


def _ferry_last(stop: PStop, day_no: int, facts: list[Fact], cfg: Settings) -> time | None:
    for f in facts:
        if (
            f.kind == "ferry_last"
            and f.value_time
            and (f.stop_id == stop.id or (f.stop_id is None and f.day_no == day_no))
        ):
            return f.value_time
    name = fold(stop.title + " " + (stop.place_query or ""))
    for ferry in cfg.ferries:
        key = fold(ferry.get("name"))
        if key and key in name and ferry.get("last_time"):
            hh, mm = str(ferry["last_time"]).split(":")[:2]
            return time(int(hh), int(mm))
    return None


def check_day(day: PDay, result: DayResult, facts: list[Fact], cfg: Settings, now_iso: str) -> list[dict]:
    risks: list[dict] = []
    d = day.day_no

    def add(code, level, stop_id, message, suggestion):
        risks.append(_risk(code, level, d, stop_id, message, suggestion, now_iso))

    # R9 thứ lệch ngày
    wd = weekday_of(day.weekday_text)
    if wd is not None and wd != day.date.weekday():
        add(
            "R9",
            "red",
            None,
            f"Ngày {d} ghi {day.weekday_text} nhưng {day.date:%d/%m} là {WEEKDAY_VI[day.date.weekday()]}",
            "Sửa ngày đi hoặc thứ trong tệp",
        )

    for t in result.timed:
        s = t.stop
        # R1 trễ giờ
        if s.planned_start and t.arrive > s.planned_start:
            late = (t.arrive - s.planned_start).total_seconds() / 60
            if late > 30:
                add(
                    "R1",
                    "red",
                    s.id,
                    f"Tới {s.title} trễ khoảng {round(late)} phút",
                    "Rời điểm trước sớm hơn hoặc bỏ một điểm tùy chọn",
                )
            elif late > 10:
                add(
                    "R1",
                    "yellow",
                    s.id,
                    f"Tới {s.title} trễ khoảng {round(late)} phút",
                    "Rút ngắn điểm trước",
                )
        elif s.fixed and s.planned_start and (s.planned_start - t.arrive).total_seconds() < 600:
            add("R1", "yellow", s.id, f"Dư dưới 10 phút trước {s.title}", "Đi sớm hơn một chút")
        # R2 giờ mở cửa
        if s.hours is not None:
            level, text = _hours_status(s.hours, t.begin, s.stay_minutes or 0, cfg)
            if level:
                add("R2", level, s.id, f"{s.title}: {text}", "Đổi giờ ghé hoặc thay bằng điểm dự phòng")
        elif s.hours_checked:
            add("R2", "yellow", s.id, f"{s.title}: chưa rõ giờ mở cửa", "Gọi trước hoặc xem trên Google Maps")
        # R3 phà
        if s.category == "pha":
            last = _ferry_last(s, d, facts, cfg)
            if last is None:
                add(
                    "R3",
                    "yellow",
                    s.id,
                    f"{s.title}: chưa biết giờ chuyến cuối",
                    "Gọi hotline phà trước 1 ngày",
                )
            else:
                last_dt = datetime.combine(_local(t.arrive, cfg).date(), last, ZoneInfo(cfg.tz))
                slack = (last_dt - t.arrive).total_seconds() / 60
                if slack < 30:
                    add(
                        "R3",
                        "red",
                        s.id,
                        f"Tới {s.title} lúc {_local(t.arrive, cfg):%H:%M}, sát hoặc sau chuyến cuối {last:%H:%M}",
                        "Rời sớm hơn hoặc bỏ điểm tùy chọn trước phà",
                    )
                elif slack < 60:
                    add(
                        "R3",
                        "yellow",
                        s.id,
                        f"Tới {s.title} chỉ dư {round(slack)} phút trước chuyến cuối {last:%H:%M}",
                        "Gọi hotline xác nhận giờ",
                    )
        # R8 chưa định vị
        if s.role == "main" and s.place_query and not s.located:
            add("R8", "yellow", s.id, f"{s.title}: chưa định vị", "Chọn địa điểm ở mục Điểm cần xác nhận")

    # R4 chạy liên tục
    run, worst, worst_stop = 0.0, 0.0, None
    stays = {t.stop.id: t.stop.stay_minutes or 0 for t in result.timed}
    for r in result.rides:
        run += (r.end - r.start).total_seconds() / 60
        if run > worst:
            worst, worst_stop = run, r.to_stop
        if stays.get(r.to_stop, 0) >= 15:
            run = 0.0
    if worst > 120:
        add(
            "R4",
            "red",
            worst_stop,
            f"Chạy liền khoảng {_hm(worst)} không nghỉ",
            "Thêm điểm nghỉ ở khoảng giữa chặng",
        )
    elif worst > cfg.ride_break_minutes:
        add("R4", "yellow", worst_stop, f"Chạy liền khoảng {_hm(worst)}", "Nghỉ khoảng mỗi 1,5 tiếng")

    # R5 chạy đêm
    night = deep = 0.0
    heavy = False
    for r in result.rides:
        n, dp = _night_windows(r, cfg)
        night += n
        deep += dp
        if n > 0 and any(h in fold(" ".join(r.instructions)) for h in HEAVY_ROADS):
            heavy = True
    if deep > 0 or (night > 0 and heavy):
        why = "trong khung 03:00 tới 05:00" if deep > 0 else "trên quốc lộ nhiều xe tải"
        add(
            "R5",
            "red",
            None,
            f"Chạy đêm khoảng {_hm(night)}, {why}",
            "Đổi giờ xuất phát; chạy làn phải, mặc áo phản quang",
        )
    elif night > 0:
        add("R5", "yellow", None, f"Chạy đêm khoảng {_hm(night)}", "Bật đèn đủ sáng, nghỉ khi buồn ngủ")

    # R6 tổng giờ chạy
    total = result.ride_minutes
    if total > 480:
        add(
            "R6",
            "red",
            None,
            f"Tổng chạy khoảng {_hm(total)} trong ngày",
            "Chia bớt quãng đường sang ngày khác",
        )
    elif total > 360:
        add("R6", "yellow", None, f"Tổng chạy khoảng {_hm(total)} trong ngày", "Nghỉ đủ giữa các chặng")

    # R7 nhận, trả phòng
    for f in facts:
        if f.day_no != d or f.value_time is None or f.kind not in ("checkin", "checkout"):
            continue
        hotel = next((t for t in result.timed if t.stop.id == f.stop_id), None) or next(
            (t for t in result.timed if t.stop.category == "khach_san"), None
        )
        if hotel is None:
            continue
        at = datetime.combine(_local(hotel.arrive, cfg).date(), f.value_time, ZoneInfo(cfg.tz))
        if f.kind == "checkin" and hotel.arrive < at:
            add(
                "R7",
                "yellow",
                hotel.stop.id,
                f"Tới {hotel.stop.title} trước giờ nhận phòng {f.value_time:%H:%M}",
                "Gửi đồ ở lễ tân",
            )
        if f.kind == "checkout" and hotel.depart > at + timedelta(minutes=60):
            add(
                "R7",
                "red",
                hotel.stop.id,
                f"Rời {hotel.stop.title} trễ quá 60 phút so với giờ trả phòng",
                "Trả phòng đúng giờ, gửi đồ",
            )
    return risks


def _hm(minutes: float) -> str:
    h, m = divmod(round(minutes), 60)
    return f"{h} giờ {m} phút" if h else f"{m} phút"


# ---------- Sắp thứ tự ----------


def reorder_day(day: PDay, matrix_minutes) -> tuple[PDay, list[str]]:
    """Đổi chỗ điểm không cố định trong khung giữa các mốc cứng để giảm phút chạy (41 mục 5.3)."""
    changes: list[str] = []
    stops = list(day.stops)
    i = 0
    while i < len(stops):
        if stops[i].fixed or not stops[i].located or stops[i].role != "main":
            i += 1
            continue
        j = i
        while j < len(stops) and not stops[j].fixed and stops[j].located and stops[j].role == "main":
            j += 1
        window = stops[i:j]
        before = stops[i - 1] if i > 0 and stops[i - 1].located else None
        after = stops[j] if j < len(stops) and stops[j].located else None
        if 3 <= len(window) <= MAX_PERMUTE:
            best = min(
                itertools.permutations(window),
                key=lambda order: _path_cost([before, *order, after], matrix_minutes),
            )
            if [s.id for s in best] != [s.id for s in window]:
                stops[i:j] = list(best)
                changes.append(f"Ngày {day.day_no}: đổi thứ tự " + ", ".join(s.title for s in best))
        i = j
    return replace(day, stops=stops), changes


def _path_cost(path: list[PStop | None], matrix_minutes) -> float:
    total = 0.0
    nodes = [p for p in path if p is not None]
    for a, b in zip(nodes, nodes[1:], strict=False):
        value = matrix_minutes(a, b)
        total += value if value is not None else 1e6
    return total


# ---------- Phương án ----------


@dataclass
class Option:
    name: str
    days: list[PDay]
    changes: list[str]


def _drop(days: list[PDay], ids: set[int]) -> list[PDay]:
    return [replace(d, stops=[s for s in d.stops if s.id not in ids]) for d in days]


def build_options(base: list[PDay], risks: list[dict], extra_changes: list[str]) -> list[Option]:
    """Nhiều điểm (giữ đủ), Đúng giờ ít rủi ro (sửa rủi ro đỏ), Nhàn (bỏ tùy chọn, ở lâu gấp 1,5)."""
    by_id = {s.id: s for d in base for s in d.stops}
    red = [r for r in risks if r["level"] == "red"]
    drop: set[int] = set()
    changes: list[str] = []
    for r in red:
        stop = by_id.get(r["stop_id"]) if r["stop_id"] else None
        if r["code"] == "R2" and stop is not None:
            drop.add(stop.id)
            changes.append(f"Bỏ {stop.title} ({r['message'].split(': ', 1)[-1]})")
        if r["code"] in ("R1", "R3") and stop is not None:
            day = next(d for d in base if d.day_no == r["day_no"])
            earlier = [s for s in day.stops[: day.stops.index(stop)] if s.optional and s.id not in drop]
            for s in earlier:
                drop.add(s.id)
                changes.append(f"Bỏ {s.title} (tùy chọn) để kịp {stop.title}")
        if r["code"] == "R4":
            changes.append(f"Ngày {r['day_no']}: thêm điểm nghỉ ở khoảng giữa chặng dài")
    safe = _drop(base, drop)
    relaxed_drop = {s.id for d in safe for s in d.stops if s.optional}
    relaxed = [
        replace(d, stops=[replace(s, stay_minutes=round((s.stay_minutes or 0) * 1.5)) for s in d.stops])
        for d in _drop(safe, relaxed_drop)
    ]
    relaxed_changes = changes + [f"Bỏ {by_id[i].title} (tùy chọn)" for i in sorted(relaxed_drop)]
    relaxed_changes.append("Thời gian ở lại mỗi điểm dài gấp 1,5")
    options = [
        Option("Nhiều điểm", base, list(extra_changes)),
        Option("Đúng giờ, ít rủi ro", safe, extra_changes + changes),
        Option("Nhàn", relaxed, extra_changes + relaxed_changes),
    ]
    unique: list[Option] = []
    seen: set = set()
    for opt in options:
        sig = tuple((s.id, s.stay_minutes) for d in opt.days for s in d.stops)
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(opt)
    return unique


def bridge_legs(days: list[PDay], legs: dict[LegKey, PLeg], full: list[PDay]) -> dict[LegKey, PLeg]:
    """Bỏ điểm thì chặng mới xấp xỉ bằng tổng các chặng đi qua điểm bị bỏ (không gọi Routes thêm)."""
    out = dict(legs)
    for day in days:
        whole = [s for s in next(d for d in full if d.day_no == day.day_no).stops if s.located]
        kept = [s for s in day.stops if s.located]
        for a, b in zip(kept, kept[1:], strict=False):
            key = leg_key(a, b)
            if key in out:
                continue
            try:
                i, j = whole.index(a), whole.index(b)
            except ValueError:
                continue
            parts = [legs.get(leg_key(x, y)) for x, y in zip(whole[i:j], whole[i + 1 : j + 1], strict=False)]
            if all(parts) and i < j:
                out[key] = PLeg(
                    sum(p.minutes for p in parts),
                    sum(p.km for p in parts),
                    [x for p in parts for x in p.instructions],
                )
    return out
