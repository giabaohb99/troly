"""Phần AI của lịch trình (41 mục 3.2, 5.3; việc 4-02).

- `extract_trip`: Haiku bóc tách tệp hoặc chữ lịch trình theo lược đồ duy nhất của 41 mục 3.2.
- `summarize_options`: Sonnet viết tóm tắt 2 câu và lời khuyên cho mỗi phương án đã tính bằng mã;
  không đổi số, không thêm bớt rủi ro. Số trong chữ phải có trong số liệu đưa vào, lệch thì dùng câu dựng bằng mã.

Lược đồ không dùng null (API giới hạn 16 tham số union cho đầu ra có cấu trúc): chữ trống là "" , số không rõ là 0.
Module trip import từ đây; ai/ không import module trip.
"""

import json
import logging
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.ai.client import ClaudeClient
from app.ai.extract import extract_structured
from app.ai.schemas import AiError
from app.ai.settings import get_ai_settings

log = logging.getLogger(__name__)

Category = Literal["an_uong", "nghi", "tham_quan", "pha", "di_chuyen", "khach_san", "mua_sam", "khac"]
Role = Literal["main", "alternative", "backup", "generic", "via"]
FactKind = Literal["ferry_last", "ferry_first", "checkin", "checkout", "hotline", "opening_hours", "other"]


class TripPlace(BaseModel):
    label: str = Field(description="Tên địa điểm; nếu có link thì chép đúng chữ của link")
    url: str = Field(description="Luôn để chuỗi rỗng; máy tự gắn link theo label")
    role: Role


class TripStop(BaseModel):
    time_text: str = Field(description="Giờ nguyên văn: 2h30, ~7h00, 10h30–12h30; không có thì rỗng")
    title: str = Field(description="Một câu ngắn")
    category: Category
    places: list[TripPlace]
    cost_note: str
    phone: str
    note: str
    optional: bool = Field(description="true nếu tệp nói có thể bỏ: nếu còn đói, nếu còn giờ, có thể")


class TripDay(BaseModel):
    day_no: int
    weekday_text: str = Field(description="Nguyên văn: thứ 7, chủ nhật; không có thì rỗng")
    date: str = Field(description="YYYY-MM-DD nếu tệp ghi ngày; không thì rỗng")
    title: str
    route_text: str = Field(description="Dòng Đường đi: ... nếu có")
    stops: list[TripStop]


class TripHotel(BaseModel):
    night_no: int
    label: str
    url: str
    booked: bool
    backups: list[str]


class TripMapLink(BaseModel):
    day_no: int
    label: str
    url: str


class TripFact(BaseModel):
    kind: FactKind
    day_no: int = Field(description="Ngày áp dụng; 0 nếu không rõ")
    value_time: str = Field(description="HH:MM nếu có giờ; không thì rỗng")
    value_text: str = Field(description="Giá trị chữ, ví dụ số hotline; không thì rỗng")
    text: str = Field(description="Câu nguyên văn trong tệp")


class TripExtract(BaseModel):
    title: str
    travel_mode: Literal["motorbike", "car", "walk", "unknown"]
    origin_text: str
    end_text: str
    start_date: str = Field(description="YYYY-MM-DD nếu tệp ghi; không thì rỗng")
    nights: int
    days: list[TripDay]
    hotels: list[TripHotel]
    map_links: list[TripMapLink]
    notes: list[str] = Field(description="Nguyên văn mục Lưu ý")
    facts: list[TripFact]


EXTRACT_SYSTEM = """Bạn bóc tách một lịch trình du lịch tiếng Việt (tệp Word đã đổi thành chữ, PDF, ảnh hoặc lời mô tả) thành dữ liệu có cấu trúc.

Luật:
- Không bịa: không thêm điểm, giờ, link mà tệp không có. Chữ không có thì để chuỗi rỗng, số không rõ để 0.
- Ngày: mỗi tiêu đề Ngày N là một phần tử days. weekday_text chép nguyên văn (thứ 7, chủ nhật). date chỉ điền khi tệp ghi rõ ngày tháng.
- Giờ: time_text chép nguyên văn (2h30, ~7h00, 10h30–12h30). Không đổi giờ.
- Mỗi hàng của bảng giờ là một stop. title là một câu ngắn nói làm gì ở đó.
- category: an_uong (ăn, uống, cafe), nghi (nghỉ chân, đổ xăng), tham_quan, pha (bến phà, qua phà), di_chuyen (chạy xe, đi qua cầu), khach_san (nhận, trả phòng), mua_sam, khac.
- places: mọi địa điểm có tên trong hàng. label chép đúng chữ nằm trong [chữ](link) nếu điểm có link.
  - Nối bằng "hoặc": điểm đầu role main, các điểm sau alternative.
  - Sau chữ "Dự phòng": backup.
  - Tên món kèm tên vùng mà không có tên quán (bún nước lèo Trà Vinh, bánh giá Gò Công): generic.
  - Điểm chỉ đi qua (cầu, ngã ba): via.
  - url: luôn để chuỗi rỗng, kể cả hotels và map_links; máy tự gắn link theo label. Không chép link.
- optional = true khi tệp nói có thể bỏ (nếu còn đói, nếu còn giờ, có thể, tùy).
- facts (mốc cứng): chuyến phà cuối hoặc đầu (ferry_last, ferry_first), nhận phòng (checkin), trả phòng (checkout), hotline, giờ mở cửa (opening_hours), mốc khác (other). value_time dạng HH:MM. text chép nguyên câu.
- hotels: khách sạn theo đêm, booked = true nếu tệp nói đã đặt; backups là tên khách sạn dự phòng.
- map_links: mỗi link tuyến đường (google.com/maps/dir) là một phần tử: day_no và label chép đúng chữ của link.
- notes: chép nguyên văn từng ý của mục Lưu ý.
- travel_mode: motorbike nếu đi xe máy, car nếu ô tô, walk nếu đi bộ, unknown nếu không rõ."""  # noqa: E501

SUMMARY_SYSTEM = """Bạn viết tóm tắt các phương án lịch trình đi xe máy cho người dùng, tiếng Việt, giọng gọn.
- Số liệu, rủi ro đã được máy tính sẵn. Không đổi số, không làm tròn khác, không thêm hay bỏ rủi ro. Mọi con số bạn viết phải có trong dữ liệu.
- Mỗi phương án: summary đúng 2 câu (câu 1 nói phương án làm gì và số liệu chính; câu 2 nói rủi ro còn lại hoặc vì sao nên chọn).
- tips: tối đa 3 lời khuyên ngắn, thực tế (mang áo mưa, đổ xăng trước đoạn dài, gọi hotline bến phà trước giờ chuyến cuối). Không có thì để rỗng.
- Không xưng hô (không dùng bạn, anh, em); không dùng emoji; không bọc tên phương án trong ngoặc kép."""


class OptionSummary(BaseModel):
    option_id: int
    summary: str
    tips: list[str]


class OptionSummaries(BaseModel):
    items: list[OptionSummary]


# ---------- Bóc tách ----------


_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def _fold(text: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFD", (text or "").replace("đ", "d").replace("Đ", "D"))
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").lower().split())


def _link_index(source_text: str | None) -> dict[str, str]:
    """Chữ của link (đã bỏ dấu) sang link, lấy từ dạng [chữ](url) trong văn bản gốc."""
    index: dict[str, str] = {}
    for label, url in _LINK.findall(source_text or ""):
        index.setdefault(_fold(label), url)
    return index


def _clean_extract(result: TripExtract, source_text: str | None) -> TripExtract:
    """Gắn link theo chữ của link trong văn bản gốc (Claude không chép link: ngắn đầu ra, không bịa link);
    ngày sai dạng thì để rỗng."""
    index = _link_index(source_text)
    date_ok = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def link(label: str) -> str:
        return index.get(_fold(label), "")

    for day in result.days:
        if day.date and not date_ok.match(day.date):
            day.date = ""
        for stop in day.stops:
            for place in stop.places:
                place.url = link(place.label)
    for hotel in result.hotels:
        hotel.url = link(hotel.label)
    for m in result.map_links:
        m.url = link(m.label)
    result.map_links = [m for m in result.map_links if m.url]
    if result.start_date and not date_ok.match(result.start_date):
        result.start_date = ""
    return result


def extract_trip(
    user_id: int,
    *,
    text: str | None = None,
    files: list[dict] | None = None,
    hint: str | None = None,
    client: ClaudeClient | None = None,
) -> TripExtract | None:
    """`text`: chữ đọc từ Word hoặc lời mô tả (link dạng [chữ](url)); `files`: khối document, image cho Claude."""
    if not text and not files:
        raise ValueError("Cần text hoặc files")
    content: list[dict] = list(files or [])
    if text:
        content.append({"type": "text", "text": f"<lich_trinh>\n{text}\n</lich_trinh>"})
    ask = "Bóc tách lịch trình trên theo đúng lược đồ."
    if hint:
        ask += f" Lần trước bóc tách bị sai: {hint}. Sửa đúng chỗ đó, giữ nguyên phần đúng."
    content.append({"type": "text", "text": ask})
    try:
        result = extract_structured(
            user_id=user_id,
            purpose="trip_extract",
            output_model=TripExtract,
            content=content,
            system=EXTRACT_SYSTEM,
            model=get_ai_settings().ai_model_extract,
            effort="medium",
            max_tokens=32000,
            timeout=300,
            stream=True,
            client=client,
        )
    except AiError as exc:
        log.warning("Bóc tách lịch trình lỗi: %s", exc.code)
        return None
    return _clean_extract(result, text) if result is not None else None


# ---------- Tóm tắt phương án ----------


_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _numbers(text: str) -> set[str]:
    """Số trong chữ, bỏ dấu ngăn nghìn: 1.200 và 1,200 đều thành 1200; 3,5 giữ 3.5."""
    out = set()
    for raw in _NUMBER.findall(text):
        groups = re.split(r"[.,]", raw)
        if len(groups) > 1 and all(len(g) == 3 for g in groups[1:]):
            out.add("".join(groups))
        else:
            out.add(raw.replace(",", "."))
            out.update(groups)
    return out


def _hours_text(minutes: int) -> str:
    h, m = divmod(int(minutes or 0), 60)
    if h and m:
        return f"{h} giờ {m} phút"
    return f"{h} giờ" if h else f"{m} phút"


def _payload(trip_title: str, options: list[dict]) -> list[dict]:
    """Thêm chữ giờ dựng sẵn để model không phải tự đổi phút ra giờ."""
    out = []
    for o in options:
        item = {
            k: o.get(k)
            for k in ("option_id", "name", "total_km", "red_count", "yellow_count", "changes", "risks")
        }
        item["ride_time_text"] = _hours_text(o.get("total_ride_minutes") or 0)
        item["night_ride_text"] = _hours_text(o.get("night_ride_minutes") or 0)
        item["total_km"] = round(float(o.get("total_km") or 0))
        out.append(item)
    return out


def fallback_summary(option: dict) -> OptionSummary:
    km = round(float(option.get("total_km") or 0))
    first = (
        f"{option.get('name') or 'Phương án'}: khoảng {km} km, "
        f"{_hours_text(option.get('total_ride_minutes') or 0)} chạy xe."
    )
    red, yellow = int(option.get("red_count") or 0), int(option.get("yellow_count") or 0)
    second = f"Còn {red} rủi ro đỏ và {yellow} rủi ro vàng." if red or yellow else "Không còn rủi ro đáng kể."
    return OptionSummary(option_id=int(option["option_id"]), summary=f"{first} {second}", tips=[])


def _bad_numbers(summary: OptionSummary, allowed: set[str]) -> set[str]:
    return {n for n in _numbers(summary.summary + " " + " ".join(summary.tips)) if n not in allowed}


def summarize_options(
    user_id: int,
    *,
    trip_title: str,
    options: list[dict],
    client: ClaudeClient | None = None,
) -> list[OptionSummary]:
    """Luôn trả đủ mỗi phương án một tóm tắt: của Sonnet nếu đúng số, không thì câu dựng bằng mã."""
    payload = _payload(trip_title, options)
    data = json.dumps({"trip": trip_title, "options": payload}, ensure_ascii=False, default=str)
    allowed = _numbers(data)
    by_id = {int(o["option_id"]): o for o in options}
    result: dict[int, OptionSummary] = {}
    hint = ""
    for _ in range(2):
        try:
            parsed = extract_structured(
                user_id=user_id,
                purpose="trip_evaluate",
                output_model=OptionSummaries,
                content=f"<du_lieu>\n{data}\n</du_lieu>\nViết tóm tắt cho từng phương án.{hint}",
                system=SUMMARY_SYSTEM,
                model=get_ai_settings().ai_model_smart,
                effort="low",
                max_tokens=4000,
                client=client,
            )
        except AiError as exc:
            log.warning("Tóm tắt phương án lỗi: %s", exc.code)
            break
        if parsed is None:
            break
        wrong: set[str] = set()
        for item in parsed.items:
            if item.option_id not in by_id or item.option_id in result:
                continue
            bad = _bad_numbers(item, allowed)
            if bad:
                wrong |= bad
            else:
                result[item.option_id] = OptionSummary(
                    option_id=item.option_id,
                    summary=item.summary.strip(),
                    tips=[t.strip() for t in item.tips[:3]],
                )
        if len(result) == len(by_id):
            break
        hint = f" Lần trước có số không có trong dữ liệu: {', '.join(sorted(wrong))}. Chỉ dùng số có trong dữ liệu."
    return [result.get(oid) or fallback_summary(o) for oid, o in by_id.items()]
