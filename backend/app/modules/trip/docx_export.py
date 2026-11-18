"""Xuất Word theo kiểu tệp mẫu Phước Hải – Trà Vinh (41 mục 8).

A4 dọc, lề 1200/1440 twip, Arial 11; Title 18 đậm màu 1F3864; Heading 1 14 đậm 1F3864; Heading 2 12 đậm;
bảng giờ 2 cột 1500/7526 twip, hàng đầu nền DCE6F1, viền BFBFBF; link màu 0563C1 gạch chân.
python-docx không có hàm thêm link nên tự tạo quan hệ RT.HYPERLINK và chèn w:hyperlink.
"""

import io
from dataclasses import dataclass, field

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Twips

NAVY = RGBColor(0x1F, 0x38, 0x64)
LINK = "0563C1"
HEADER_FILL = "DCE6F1"
BORDER = "BFBFBF"

Run = tuple[str, str | None]  # (chữ, link hoặc None)


@dataclass
class DocDay:
    day_no: int
    heading: str
    route_line: str | None
    rows: list[tuple[str, list[Run]]]
    map_links: list[tuple[str, str]]


@dataclass
class DocTrip:
    title: str
    summary: str
    days: list[DocDay]
    hotels: list[list[Run]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _font(run, size: float | None = None, bold: bool = False, color: RGBColor | None = None) -> None:
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    if size:
        run.font.size = Pt(size)
    run.font.bold = bold or None
    if color is not None:
        run.font.color.rgb = color


def _style(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width, section.page_height = Twips(11906), Twips(16838)
    section.top_margin = section.bottom_margin = Twips(1200)
    section.left_margin = section.right_margin = Twips(1440)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Arial", Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    for name, size, color, before, after in (
        ("Title", 18, NAVY, 0, 10),
        ("Heading 1", 14, NAVY, 16, 6),
        ("Heading 2", 12, None, 10, 4),
    ):
        st = doc.styles[name]
        st.font.name, st.font.size, st.font.bold = "Arial", Pt(size), True
        st.font.color.rgb = color if color is not None else RGBColor(0, 0, 0)
        st.font.italic = False
        st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(before), Pt(after)
        rfonts = st.element.rPr.rFonts
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rfonts.set(qn(attr), "Arial")
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            rfonts.attrib.pop(qn(attr), None)


def add_hyperlink(paragraph, text: str, url: str) -> None:
    rel_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rel_id)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(attr), "Arial")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), LINK)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    props.extend([fonts, color, underline])
    run.append(props)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def _runs(paragraph, runs: list[Run]) -> None:
    for text, url in runs:
        if url:
            add_hyperlink(paragraph, text, url)
        else:
            _font(paragraph.add_run(text))


def _cell(cell, fill: str | None) -> None:
    props = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), BORDER)
        borders.append(el)
    props.append(borders)
    if fill:
        shading = OxmlElement("w:shd")
        shading.set(qn("w:val"), "clear")
        shading.set(qn("w:fill"), fill)
        props.append(shading)
    margins = OxmlElement("w:tcMar")
    for side, width in (("top", 60), ("left", 100), ("bottom", 60), ("right", 100)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(width))
        el.set(qn("w:type"), "dxa")
        margins.append(el)
    props.append(margins)


def _table(doc: Document, rows: list[tuple[str, list[Run]]]) -> None:
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)
    widths = (Twips(1500), Twips(7526))
    header = table.rows[0].cells
    for cell, text, width in zip(header, ("Giờ", "Làm gì"), widths, strict=True):
        cell.width = width
        _cell(cell, HEADER_FILL)
        _font(cell.paragraphs[0].add_run(text), bold=True)
    for time_text, runs in rows:
        cells = table.add_row().cells
        for cell, width in zip(cells, widths, strict=True):
            cell.width = width
            _cell(cell, None)
        _font(cells[0].paragraphs[0].add_run(time_text or ""))
        _runs(cells[1].paragraphs[0], runs)


def build_docx(trip: DocTrip) -> bytes:
    doc = Document()
    _style(doc)
    doc.add_paragraph(trip.title, style="Title")
    _font(doc.add_paragraph().add_run(trip.summary))
    _font(
        doc.add_paragraph().add_run(
            "Link chỉ đường đã đặt sẵn chế độ xe máy và tránh cao tốc. Các chữ màu xanh đều bấm được."
        )
    )
    for day in trip.days:
        doc.add_paragraph(day.heading, style="Heading 1")
        if day.route_line:
            _font(doc.add_paragraph().add_run(day.route_line))
        _table(doc, day.rows)
        if day.map_links:
            doc.add_paragraph(f"Bản đồ ngày {day.day_no}", style="Heading 2")
            for label, url in day.map_links:
                add_hyperlink(doc.add_paragraph(), label, url)
    if trip.hotels:
        doc.add_paragraph("Khách sạn", style="Heading 1")
        for runs in trip.hotels:
            _runs(doc.add_paragraph(), runs)
    doc.add_paragraph("Lưu ý", style="Heading 1")
    for line in [*trip.notes, "Thời gian xe máy do Google ước tính (bản thử nghiệm), có thể lệch."]:
        _font(doc.add_paragraph().add_run(line))
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
