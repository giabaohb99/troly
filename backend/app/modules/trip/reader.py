"""Lấy chữ và link từ tệp lịch trình (41 mục 3.1, 3.3).

Word: đoạn văn kèm kiểu, bảng theo hàng; link đọc từ thẻ w:hyperlink rồi tra rels (python-docx không có
API đọc link), đổi thành [chữ](url). Link Google Maps: tìm kiếm, chỉ đường, rút gọn.
"""

import io
import re
import zipfile
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlparse
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
LATLNG_RE = re.compile(r"^\s*(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s*$")


@dataclass
class DocxText:
    text: str
    links: list[str] = field(default_factory=list)
    tables: int = 0
    table_rows: int = 0


def _para(p: ET.Element, rels: dict[str, str]) -> str:
    out = []
    for child in p:
        if child.tag == W + "hyperlink":
            label = "".join(t.text or "" for t in child.iter(W + "t"))
            target = rels.get(child.get(R + "id", ""))
            out.append(f"[{label}]({target})" if target else label)
        else:
            out.append("".join(t.text or "" for t in child.iter(W + "t")))
    return "".join(out).strip()


def _style(p: ET.Element) -> str:
    style = p.find(f"{W}pPr/{W}pStyle")
    return style.get(W + "val", "") if style is not None else ""


def read_docx(data: bytes) -> DocxText:
    """Đổi .docx thành chữ dạng Markdown gọn để đưa Claude; giữ thứ tự đoạn và bảng."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        rels: dict[str, str] = {}
        if "word/_rels/document.xml.rels" in z.namelist():
            for rel in ET.fromstring(z.read("word/_rels/document.xml.rels")):
                rels[rel.get("Id", "")] = rel.get("Target", "")
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
    lines: list[str] = []
    tables = rows = 0
    prefixes = {"Title": "# ", "Heading1": "## ", "Heading2": "### "}
    for el in body if body is not None else []:
        if el.tag == W + "p":
            text = _para(el, rels)
            if text:
                lines.append(prefixes.get(_style(el), "") + text)
        elif el.tag == W + "tbl":
            tables += 1
            for i, tr in enumerate(el.iter(W + "tr")):
                cells = [
                    " / ".join(filter(None, (_para(p, rels) for p in tc.findall(W + "p"))))
                    for tc in tr.findall(W + "tc")
                ]
                lines.append("| " + " | ".join(cells) + " |")
                if i > 0:
                    rows += 1
            lines.append("")
    text = "\n".join(lines)
    return DocxText(
        text=text, links=[m.group(2) for m in LINK_RE.finditer(text)], tables=tables, table_rows=rows
    )


# ---------- Link Google Maps ----------


@dataclass
class MapsLink:
    kind: str  # search, dir, short, other
    query: str | None = None
    place_id: str | None = None
    origin: str | None = None
    destination: str | None = None
    waypoints: list[str] = field(default_factory=list)


def parse_latlng(value: str | None) -> tuple[float, float] | None:
    if not value:
        return None
    m = LATLNG_RE.match(value)
    if not m:
        return None
    lat, lng = float(m.group(1)), float(m.group(2))
    return (lat, lng) if -90 <= lat <= 90 and -180 <= lng <= 180 else None


def parse_maps_url(url: str) -> MapsLink:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host in ("maps.app.goo.gl", "goo.gl"):
        return MapsLink("short")
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    if "google." in host and parsed.path.startswith("/maps/search"):
        return MapsLink("search", query=params.get("query"), place_id=params.get("query_place_id"))
    if "google." in host and parsed.path.startswith("/maps/dir"):
        waypoints = [w for w in unquote(params.get("waypoints", "")).split("|") if w]
        return MapsLink(
            "dir", origin=params.get("origin"), destination=params.get("destination"), waypoints=waypoints
        )
    return MapsLink("other")


def links_in(text: str) -> set[str]:
    return {m.group(2) for m in LINK_RE.finditer(text)} | set(re.findall(r"https?://[^\s)\]]+", text))
