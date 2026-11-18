"""Kết quả bóc tách dựng sẵn cho tệp mẫu Phước Hải – Trà Vinh, thay cho Claude trong bài kiểm.

Dựng tất định từ chữ của tệp (reader.read_docx) theo đúng luật bóc tách ở 41 mục 3.2, để bài kiểm
không gọi Claude mà vẫn đi qua đủ các bước sau bóc tách.
"""

import os
import re
from pathlib import Path

from app.modules.trip.normalize import fold
from app.modules.trip.reader import LINK_RE, read_docx
from app.modules.trip.schemas import TripExtract

GENERIC = {
    "bun nuoc leo",
    "banh canh ben co",
    "banh gia",
    "hu tieu go cong",
    "mam tom cha",
    "banh tet tra cuon",
}
VIA = {1: ["Cầu Mỹ Thuận"], 3: ["Cầu Rạch Miễu"]}


def sample_path() -> Path:
    base = os.environ.get("TESTDATA_DIR") or str(Path(__file__).resolve().parents[5] / "testdata")
    return Path(base) / "trips" / "Lich-trinh-Phuoc-Hai-Tra-Vinh.docx"


def sample_bytes() -> bytes:
    return sample_path().read_bytes()


def _category(text: str) -> str:
    t = fold(text)
    if re.search(r"\bpha\b", t):
        return "pha"
    if any(w in t for w in ("nhan phong", "tra phong", "khach san")):
        return "khach_san"
    if re.match(r"an (sang|trua|toi|xe|nhe)", t) or t.startswith("an "):
        return "an_uong"
    if any(w in t for w in ("ngu vong", "nghi ")):
        return "nghi"
    if t.startswith("mua "):
        return "mua_sam"
    if any(w in t for w in ("xuat phat", "di tra vinh", "ve can tho", "di vung tau")):
        return "di_chuyen"
    return "tham_quan"


def _places(cell: str, category: str) -> list[dict]:
    out = []
    last_end = 0
    for m in LINK_RE.finditer(cell):
        before = fold(cell[last_end : m.start()])
        role = (
            "backup" if "du phong" in before else "alternative" if "hoac" in before.split()[-3:] else "main"
        )
        if role == "main" and category == "an_uong" and out:
            role = "alternative"  # bữa ăn kê nhiều quán là các lựa chọn
        label = m.group(1)
        if fold(label) in GENERIC:
            role = "generic" if role == "main" else role
        out.append({"label": label, "url": m.group(2), "role": role})
        last_end = m.end()
    return out


def build_sample_extract(text: str | None = None) -> TripExtract:
    text = text or read_docx(sample_bytes()).text
    lines = text.splitlines()
    title = lines[0].lstrip("# ").strip()
    days: list[dict] = []
    map_links: list[dict] = []
    hotels: list[dict] = []
    notes: list[str] = []
    section = None
    for line in lines[1:]:
        heading = re.match(r"^## Ngày (\d+) \(([^)]+)\): (.+)$", line)
        if heading:
            ends = [x.strip() for x in heading.group(3).split("→")]
            days.append(
                {
                    "day_no": int(heading.group(1)),
                    "weekday_text": heading.group(2),
                    "title": heading.group(3),
                    "stops": [],
                    "_ends": ends,
                }
            )
            section = "day"
            continue
        if line.startswith("### Bản đồ ngày"):
            section = "map"
            continue
        if line.startswith("## Khách sạn"):
            section = "hotel"
            continue
        if line.startswith("## Lưu ý"):
            section = "notes"
            continue
        if section == "day" and line.startswith("Đường đi"):
            days[-1]["route_text"] = line
        elif section == "day" and line.startswith("| ") and not line.startswith("| Giờ"):
            time_cell, cell = [c.strip() for c in line.strip("|").split("|", 1)]
            cell = cell.strip(" |")
            plain = LINK_RE.sub(lambda m: m.group(1), cell)
            category = _category(plain)
            places = _places(cell, category)
            day = days[-1]
            if not places and category == "pha":
                places = [{"label": re.search(r"phà [^.]+", plain).group(0), "url": None, "role": "main"}]
            if not places and not day["stops"]:
                places = [{"label": day["_ends"][0], "url": None, "role": "main"}]
            if not places and fold(plain).startswith("ve ") and "khach san" not in fold(plain):
                places = [{"label": day["_ends"][-1], "url": None, "role": "main"}]
            day["stops"].append(
                {
                    "time_text": time_cell,
                    "title": plain.split(". ")[0][:200],
                    "category": category,
                    "places": places,
                    "optional": "nếu còn" in plain or "có thể" in plain,
                    "phone": (re.search(r"SĐT ([\d ]+)", plain) or [None, None])[1],
                }
            )
            if len(day["stops"]) == 1:
                for name in VIA.get(day["day_no"], []):
                    day["stops"].append(
                        {
                            "title": f"Qua {name}",
                            "category": "di_chuyen",
                            "places": [{"label": name, "url": None, "role": "via"}],
                        }
                    )
        elif section == "map":
            for m in LINK_RE.finditer(line):
                map_links.append({"day_no": days[-1]["day_no"], "label": m.group(1), "url": m.group(2)})
        elif section == "hotel" and line.strip():
            found = list(LINK_RE.finditer(line))
            if found:
                hotels.append(
                    {
                        "night_no": len(hotels) + 1,
                        "label": found[0].group(1),
                        "url": found[0].group(2),
                        "booked": "chưa đặt" not in line,
                        "backups": [
                            {"label": m.group(1), "url": m.group(2), "role": "backup"} for m in found[1:]
                        ],
                    }
                )
        elif section == "notes" and line.strip():
            notes.append(line)
    facts = [
        {"kind": "checkin", "day_no": 1, "value_time": "13:00", "text": "Nhận phòng Hotel Quốc Hương 13h00"},
        {"kind": "checkout", "day_no": 2, "value_time": "10:45", "text": "Trả phòng 10h45"},
        {"kind": "ferry_last", "day_no": 2, "value_time": "17:00", "text": "chuyến cuối từ Vũng Tàu lúc 17h"},
        {
            "kind": "hotline",
            "day_no": 2,
            "value_text": "0254 6525 656",
            "text": "Gọi hotline phà Vũng Tàu – Cần Giờ 0254 6525 656",
        },
    ]
    for day in days:
        day.pop("_ends")
    return TripExtract.model_validate(
        {
            "title": title,
            "travel_mode": "motorbike",
            "origin_text": "Cần Thơ",
            "end_text": "Cần Thơ",
            "nights": 2,
            "days": days,
            "hotels": hotels,
            "map_links": map_links,
            "notes": notes,
            "facts": facts,
        }
    )
