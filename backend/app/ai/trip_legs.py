"""Ước tính chặng xe máy cho lịch trình (QĐ-36: V1 không dùng Google Routes, Places).

- `estimate_legs`: Sonnet ước tính km, phút cho từng chặng trip đưa vào; mã kẹp số về khoảng hợp lý
  (không âm, tốc độ phần chạy xe 15 tới 60 km/h, không dưới đường chim bay khi có tọa độ), gắn cờ `estimated`.
- Nghĩ kỹ (`think=True`): thêm một lượt Sonnet tìm web giờ mở cửa và giờ phà cuối, rồi bóc ra lược đồ.
  Hai bước tách nhau vì citations của tìm web không đi cùng đầu ra có cấu trúc (API trả 400).

Module trip gọi qua bridge; ai/ không import module trip.
"""

import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import time
from typing import Literal

from pydantic import BaseModel

from app.ai.client import ClaudeClient, get_client
from app.ai.extract import extract_structured
from app.ai.prompt import WEB_TOOLS
from app.ai.schemas import AiError
from app.ai.settings import get_ai_settings

log = logging.getLogger(__name__)

LEG_SYSTEM = """Bạn ước tính quãng đường và thời gian chạy xe máy ở Việt Nam giữa từng cặp điểm dừng.
- Đi xe máy, không đi cao tốc (xe máy không được vào cao tốc): đi quốc lộ, tỉnh lộ, đường ven biển; qua sông bằng cầu hoặc phà như người địa phương hay đi.
- Dựa vào tên, địa chỉ, tỉnh và tọa độ nếu có. Cùng một nơi hoặc sát nhau thì km gần 0, phút nhỏ.
- minutes là tổng thời gian chặng, đã gồm chờ và qua phà; ferry_minutes là phần chờ và qua phà (không qua phà thì 0).
- Tốc độ chạy thực tế: nội thành 20 tới 25 km/h, đường tỉnh 30 tới 40 km/h, quốc lộ thoáng 40 tới 50 km/h. Chặng dài trên 100 km chủ yếu quốc lộ thường trung bình 35 tới 45 km/h kể cả đoạn qua thị trấn; không cộng giờ nghỉ ăn uống (đã có điểm dừng riêng).
- roads: tên quốc lộ, tỉnh lộ chính đi qua (ví dụ QL1A, QL51, ĐT44A), không có thì rỗng.
- travel_mode car là ô tô (được đi cao tốc, tốc độ cao hơn); còn lại là xe máy.
- confidence: high khi biết rõ tuyến; low khi chỉ đoán theo tỉnh. note: một câu nói tuyến đi chính (ví dụ: đi QL55 qua Đất Đỏ), không xưng hô.
- Trả đủ mỗi chặng một dòng, đúng index đã cho.
- Có <ghi_chu_web> thì với mỗi điểm trong <diem_can_kiem>, điền checks theo đúng ghi chú, không bịa. opening_hours: open_weekdays (0 là Chủ nhật, 1 là thứ Hai, ..., 6 là thứ Bảy), open_time, close_time dạng HH:MM; có nghỉ trưa thì break_start, break_end, không thì để trống. ferry_last: last_time là giờ chuyến phà cuối của ngày ghé. Ghi chú không có thông tin thì found = false. source_url phải là link có trong ghi chú, không có thì để trống. Không có ghi chú thì checks rỗng."""

CHECK_SYSTEM = """Bạn tra cứu trên web cho một chuyến đi xe máy ở Việt Nam. Với từng điểm được hỏi:
- Điểm tham quan, ăn uống, mua sắm: giờ mở cửa vào đúng thứ trong tuần của ngày ghé, ngày nghỉ trong tuần.
- Bến phà: giờ chuyến phà cuối của ngày ghé (và chuyến đầu nếu có).
Ưu tiên trang chính thức, trang của tỉnh, báo địa phương. Mỗi điểm viết một dòng: số trong ngoặc vuông, tên điểm, giờ tìm được, link nguồn. Không tìm được thì ghi không rõ, không đoán."""

HOURS_CATEGORIES = ("tham_quan", "an_uong", "mua_sam")
MIN_SPEED_KMH = 15
MAX_SPEED_KMH = 60
MAX_SPEED_CAR_KMH = 90
MAX_LEG_KM = 600
NEAR_KM = 0.3
FALLBACK_ROAD_FACTOR = 1.4
FALLBACK_SPEED_KMH = 30
MAX_WEB_ROUNDS = 3
MAX_SEARCHES = 6
_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class LegGuess(BaseModel):
    index: int
    km: float
    minutes: int
    ferry_minutes: int
    confidence: Literal["high", "medium", "low"]
    roads: list[str]
    note: str


class CheckGuess(BaseModel):
    stop_index: int
    kind: Literal["opening_hours", "ferry_last"]
    found: bool
    open_weekdays: list[int]
    open_time: str
    close_time: str
    break_start: str
    break_end: str
    last_time: str
    source_url: str
    text: str


class LegPlan(BaseModel):
    legs: list[LegGuess]
    checks: list[CheckGuess]


@dataclass
class LegEstimate:
    from_stop_id: int
    to_stop_id: int
    km: float
    minutes: int
    ferry_minutes: int
    estimated: bool = True
    adjusted: bool = False
    confidence: str = "low"
    roads: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class StopCheck:
    stop_id: int
    kind: str  # opening_hours | ferry_last
    hours: dict | None = None  # dạng maps.opening_hours: {"regular": {"periods": [...]}}, day 0 là Chủ nhật
    last_time: time | None = None
    text: str = ""
    source_url: str | None = None


@dataclass
class LegEstimates:
    legs: list[LegEstimate]
    checks: list[StopCheck] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)


# ---------- Kiểm số bằng mã ----------


def straight_km(a: dict, b: dict) -> float | None:
    """Đường chim bay (haversine) khi hai đầu có tọa độ."""
    if None in (a.get("lat"), a.get("lng"), b.get("lat"), b.get("lng")):
        return None
    lat1, lng1, lat2, lng2 = (math.radians(float(v)) for v in (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def check_leg(
    km: float, minutes: int, ferry: int, line_km: float | None, max_speed: float = MAX_SPEED_KMH
) -> tuple[float, int, int, bool]:
    """Kẹp số của model về khoảng hợp lý. Trả (km, minutes, ferry_minutes, adjusted)."""
    adjusted = km < 0 or minutes < 0 or ferry < 0
    km, minutes, ferry = max(0.0, float(km)), max(0, int(minutes)), max(0, int(ferry))
    if ferry > minutes:
        ferry, adjusted = minutes, True
    if line_km is not None:
        if km < line_km:
            km, adjusted = line_km * 1.3, True
        elif km > line_km * 3 + 5:
            km, adjusted = line_km * 1.6, True
    if km > MAX_LEG_KM:
        km, adjusted = MAX_LEG_KM, True
    ride = minutes - ferry
    if km >= NEAR_KM:
        if ride <= 0 or km / (ride / 60) > max_speed:
            ride, adjusted = math.ceil(km / max_speed * 60), True
        elif km / (ride / 60) < MIN_SPEED_KMH:
            ride, adjusted = round(km / MIN_SPEED_KMH * 60), True
    return round(km, 1), ride + ferry, ferry, adjusted


def _note_with_roads(note: str, roads: list[str]) -> str:
    """Trip đọc tên quốc lộ trong `note` cho luật chạy đêm (R5): thiếu thì ghép thêm."""
    note = note.strip()[:200]
    missing = [r for r in roads if r.replace(" ", "").lower() not in note.replace(" ", "").lower()]
    if missing:
        note = f"{note} Đường chính: {', '.join(missing)}.".strip()
    return note


def _hhmm(value: str) -> time | None:
    m = _HHMM.match((value or "").strip())
    return time(int(m.group(1)), int(m.group(2))) if m else None


def _periods(days: list[int], spans: list[tuple[time, time]]) -> dict:
    periods = []
    for d in sorted({d for d in days if 0 <= d <= 6}):
        for start, end in spans:
            close_day = d if end > start else (d + 1) % 7
            periods.append(
                {
                    "open": {"day": d, "hour": start.hour, "minute": start.minute},
                    "close": {"day": close_day, "hour": end.hour, "minute": end.minute},
                }
            )
    return {"regular": {"periods": periods}, "source": "web"}


def _to_check(guess: CheckGuess, stop_id: int, urls: set[str]) -> StopCheck:
    url = guess.source_url.strip()
    out = StopCheck(
        stop_id=stop_id,
        kind=guess.kind,
        text=guess.text.strip()[:300],
        source_url=url if url in urls else None,
    )
    if not guess.found:
        return out
    if guess.kind == "ferry_last":
        out.last_time = _hhmm(guess.last_time)
    else:
        start, end = _hhmm(guess.open_time), _hhmm(guess.close_time)
        pause, resume = _hhmm(guess.break_start), _hhmm(guess.break_end)
        if start and end and guess.open_weekdays:
            spans = [(start, end)]
            if pause and resume and start < pause < resume < end:
                spans = [(start, pause), (resume, end)]  # nghỉ trưa
            out.hours = _periods(guess.open_weekdays, spans)
    return out


# ---------- Gọi Claude ----------


def _stop_brief(s: dict) -> dict:
    keys = ("title", "category", "address", "place_query", "lat", "lng", "planned_time")
    return {k: s.get(k) for k in keys if s.get(k) not in (None, "")}


def _collect(content: list[dict], texts: list[str], hits: list[dict]) -> None:
    for block in content:
        if block.get("type") == "text":
            texts.append(block.get("text") or "")
            for cit in block.get("citations") or []:
                if cit.get("url"):
                    hits.append({"title": cit.get("title") or cit["url"], "url": cit["url"]})
        elif block.get("type") == "web_search_tool_result" and isinstance(block.get("content"), list):
            hits.extend(
                {"title": r.get("title") or r["url"], "url": r["url"]}
                for r in block["content"]
                if r.get("type") == "web_search_result" and r.get("url")
            )


def _web_notes(
    user_id: int, trip_title: str, region: str | None, asks: list[dict], client: ClaudeClient
) -> tuple[str, list[dict]]:
    search = next(t for t in WEB_TOOLS if t["name"] == "web_search")
    lines = "\n".join(
        f"- [{a['stop_index']}] {a['title']} ({a.get('address') or a.get('place_query') or region or ''}), "
        f"ngày ghé {a.get('visit') or 'chưa rõ'}: {'giờ phà cuối' if a['kind'] == 'ferry_last' else 'giờ mở cửa'}"
        for a in asks
    )
    messages = [{"role": "user", "content": f"Chuyến: {trip_title} ({region or ''}).\nCần tra:\n{lines}"}]
    params = {
        "model": get_ai_settings().ai_model_smart,
        "max_tokens": 8000,
        "system": CHECK_SYSTEM,
        # Chỉ tìm, không đọc cả trang: đọc trang làm lượt nghĩ kỹ tốn gấp mấy lần (thử thật 18/11/2026).
        "tools": [{**search, "max_uses": min(MAX_SEARCHES, 2 * len(asks))}],
        "output_config": {"effort": "low"},
        "messages": messages,
    }
    texts: list[str] = []
    hits: list[dict] = []
    for _ in range(MAX_WEB_ROUNDS):
        res = client.create(params, purpose="trip_evaluate", user_id=user_id)
        _collect(res.content, texts, hits)
        if res.stop_reason != "pause_turn":
            break  # pause_turn: gửi lại nguyên lượt để server chạy tiếp
        params = {**params, "messages": [*messages, {"role": "assistant", "content": res.content}]}
    sources: list[dict] = []
    for h in hits:
        if h["url"] not in (s["url"] for s in sources):
            sources.append(h)
    notes = "".join(texts).strip()
    links = "\n".join(f"- {s['title']}: {s['url']}" for s in sources[:20])
    return (f"{notes}\nNguồn đã xem:\n{links}" if links else notes), sources


def _asks(stops: list[dict]) -> list[dict]:
    out = []
    for i, s in enumerate(stops):
        cat = s.get("category")
        kind = "ferry_last" if cat == "pha" else "opening_hours" if cat in HOURS_CATEGORIES else None
        if kind:
            visit = s.get("visit_date")
            out.append({**s, "stop_index": i, "kind": kind, "visit": str(visit) if visit else None})
    return out


def estimate_legs(
    user_id: int,
    *,
    trip_title: str,
    region: str | None,
    stops: list[dict],
    legs: list[dict],
    think: bool = False,
    travel_mode: str = "motorbike",
    client: ClaudeClient | None = None,
) -> LegEstimates | None:
    """`stops`: {stop_id, day_no, title, category, address, place_query, lat, lng, planned_time, visit_date};
    `legs`: {from_stop_id, to_stop_id} do trip chọn. Trả None khi model lỗi hoặc từ chối."""
    client = client or get_client()
    by_id = {int(s["stop_id"]): s for s in stops}
    pairs = [
        (int(g["from_stop_id"]), int(g["to_stop_id"]))
        for g in legs
        if int(g["from_stop_id"]) in by_id and int(g["to_stop_id"]) in by_id
    ]
    asks = _asks(list(by_id.values())) if think else []
    notes, sources = "", []
    if asks:
        try:
            notes, sources = _web_notes(user_id, trip_title, region, asks, client)
        except AiError as exc:
            log.warning("Tìm web cho lịch trình lỗi: %s", exc.code)
    data = {
        "trip": trip_title,
        "region": region,
        "travel_mode": travel_mode,
        "legs": [
            {
                "index": i,
                "day_no": by_id[a].get("day_no"),
                "from": _stop_brief(by_id[a]),
                "to": _stop_brief(by_id[b]),
            }
            for i, (a, b) in enumerate(pairs)
        ],
    }
    content = f"<du_lieu>\n{json.dumps(data, ensure_ascii=False, default=str)}\n</du_lieu>"
    if notes:
        asked = [{"stop_index": a["stop_index"], "title": a["title"], "kind": a["kind"]} for a in asks]
        content += (
            f"\n<diem_can_kiem>\n{json.dumps(asked, ensure_ascii=False)}\n</diem_can_kiem>"
            f"\n<ghi_chu_web>\n{notes}\n</ghi_chu_web>"
        )
    content += "\nƯớc tính từng chặng."
    try:
        plan = extract_structured(
            user_id=user_id,
            purpose="trip_evaluate",
            output_model=LegPlan,
            content=content,
            system=LEG_SYSTEM,
            model=get_ai_settings().ai_model_smart,
            effort="low",
            max_tokens=8000,
            client=client,
        )
    except AiError as exc:
        log.warning("Ước tính chặng lỗi: %s", exc.code)
        return None
    if plan is None:
        return None
    guesses = {g.index: g for g in plan.legs if 0 <= g.index < len(pairs)}
    top = MAX_SPEED_CAR_KMH if travel_mode == "car" else MAX_SPEED_KMH
    out: list[LegEstimate] = []
    for i, (a, b) in enumerate(pairs):
        line = straight_km(by_id[a], by_id[b])
        g = guesses.get(i)
        if g is None:
            if line is None:
                continue  # model bỏ sót, không có tọa độ: trip coi là chưa rõ
            road = line * FALLBACK_ROAD_FACTOR
            km, minutes, ferry, _ = check_leg(road, round(road / FALLBACK_SPEED_KMH * 60), 0, line, top)
            out.append(
                LegEstimate(a, b, km, minutes, ferry, adjusted=True, note="Ước tính theo đường chim bay.")
            )
            continue
        km, minutes, ferry, adjusted = check_leg(g.km, g.minutes, g.ferry_minutes, line, top)
        roads = [r.strip()[:40] for r in g.roads[:6] if r.strip()]
        out.append(
            LegEstimate(
                a,
                b,
                km,
                minutes,
                ferry,
                adjusted=adjusted,
                confidence=g.confidence,
                roads=roads,
                note=_note_with_roads(g.note, roads),
            )
        )
    checks: list[StopCheck] = []
    if asks:
        urls = {s["url"] for s in sources}
        target = {a["stop_index"]: (int(a["stop_id"]), a["kind"]) for a in asks}
        seen: set[tuple[int, str]] = set()
        for c in plan.checks:
            t = target.get(c.stop_index)
            if t is None or t[1] != c.kind or t in seen:
                continue
            seen.add(t)
            checks.append(_to_check(c, t[0], urls))
    return LegEstimates(legs=out, checks=checks, sources=sources[:10])
