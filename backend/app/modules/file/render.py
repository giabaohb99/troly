"""Dựng tệp PDF, Word, Excel từ khối nội dung gọn cho công cụ `export_document` (QĐ-41).

Khối: `{"type": "heading", "level": 1-3, "text"}`, `{"type": "paragraph", "text"}`,
`{"type": "bullets", "items": [...]}`, `{"type": "table", "title"?, "header": [...], "rows": [[...]]}`.
Ô bảng là chuỗi hoặc số; số giữ kiểu số trong Excel, hiện dạng 1.234.567 trong PDF, Word.
PDF dùng font DejaVu Sans (gói `fonts-dejavu-core` trong image) để đủ dấu tiếng Việt.
"""

import io
import os
import re
import unicodedata

from app.core.errors import ValidationError

FORMATS = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
FONT_DIR = os.environ.get("TROLY_FONT_DIR", "/usr/share/fonts/truetype/dejavu")
MAX_BLOCKS = 500
MAX_ROWS = 5000
MAX_COLS = 30
MAX_TEXT = 20_000


# ---------- Kiểm khối ----------


def _text(value, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise ValidationError(fields={"blocks": "Nội dung khối phải là chữ."})
    return value[:limit]


def _cell(value):
    if isinstance(value, bool) or value is None:
        return "" if value is None else ("Có" if value else "Không")
    if isinstance(value, int | float):
        return value
    return _text(str(value), 2000)


def validate(fmt: str, title: str, blocks: list) -> list[dict]:
    if fmt not in FORMATS:
        raise ValidationError(fields={"format": "Chỉ xuất pdf, docx hoặc xlsx."})
    if not isinstance(blocks, list) or len(blocks) > MAX_BLOCKS:
        raise ValidationError(fields={"blocks": f"Tối đa {MAX_BLOCKS} khối."})
    _text(title, 300)
    clean = []
    for b in blocks:
        kind = b.get("type") if isinstance(b, dict) else None
        if kind == "heading":
            clean.append(
                {
                    "type": kind,
                    "level": min(max(int(b.get("level") or 1), 1), 3),
                    "text": _text(b.get("text"), 300),
                }
            )
        elif kind == "paragraph":
            clean.append({"type": kind, "text": _text(b.get("text"))})
        elif kind == "bullets":
            items = b.get("items") or []
            clean.append({"type": kind, "items": [_text(i, 2000) for i in items[:200]]})
        elif kind == "table":
            header = [_text(str(h), 200) for h in (b.get("header") or [])][:MAX_COLS]
            rows = b.get("rows") or []
            if not header or len(rows) > MAX_ROWS:
                raise ValidationError(fields={"blocks": f"Bảng cần dòng đầu và tối đa {MAX_ROWS} dòng."})
            if any(not isinstance(r, list) or len(r) != len(header) for r in rows):
                raise ValidationError(fields={"blocks": "Mỗi dòng của bảng phải đủ số cột như dòng đầu."})
            clean.append(
                {
                    "type": kind,
                    "title": _text(b["title"], 100) if b.get("title") else None,
                    "header": header,
                    "rows": [[_cell(v) for v in r] for r in rows],
                }
            )
        else:
            raise ValidationError(fields={"blocks": "Khối là heading, paragraph, bullets hoặc table."})
    return clean


def show_number(value) -> str:
    """2450000 -> 2.450.000; 830000.5 -> 830.000,5 (cách viết Việt Nam)."""
    if isinstance(value, float) and not value.is_integer():
        whole, frac = f"{value:,.2f}".rstrip("0").split(".")
        return whole.replace(",", ".") + "," + frac
    return f"{int(value):,}".replace(",", ".")


def _show(value) -> str:
    return show_number(value) if isinstance(value, int | float) else str(value)


def _numeric_columns(table: dict) -> set[int]:
    cols = set()
    for i in range(len(table["header"])):
        values = [r[i] for r in table["rows"] if r[i] != ""]
        if values and all(isinstance(v, int | float) for v in values):
            cols.add(i)
    return cols


def file_name(title: str, ext: str) -> str:
    folded = unicodedata.normalize("NFD", title.replace("đ", "d").replace("Đ", "D"))
    folded = "".join(c for c in folded if unicodedata.category(c) != "Mn").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")[:80] or "tep"
    return f"{slug}.{ext}"


# ---------- PDF ----------


def _pdf(title: str, blocks: list[dict]) -> bytes:
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", "", os.path.join(FONT_DIR, "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf"))
    pdf.set_title(title)
    pdf.add_page()
    width = pdf.epw
    pdf.set_font("DejaVu", "B", 18)
    pdf.multi_cell(width, 9, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    for b in blocks:
        if b["type"] == "heading":
            pdf.ln(2)
            pdf.set_font("DejaVu", "B", {1: 15, 2: 13, 3: 11.5}[b["level"]])
            pdf.multi_cell(width, 7, b["text"], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif b["type"] == "paragraph":
            pdf.set_font("DejaVu", "", 11)
            pdf.multi_cell(width, 6, b["text"], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif b["type"] == "bullets":
            pdf.set_font("DejaVu", "", 11)
            for item in b["items"]:
                pdf.set_x(pdf.l_margin + 4)
                pdf.multi_cell(width - 4, 6, f"• {item}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif b["type"] == "table":
            if b["title"]:
                pdf.set_font("DejaVu", "B", 11)
                pdf.multi_cell(width, 6, b["title"], new_x="LMARGIN", new_y="NEXT")
            numeric = _numeric_columns(b)
            pdf.set_font("DejaVu", "", 10)
            aligns = tuple("RIGHT" if i in numeric else "LEFT" for i in range(len(b["header"])))
            with pdf.table(
                text_align=aligns,
                headings_style=FontFace(emphasis="BOLD", fill_color=(235, 235, 235)),
                line_height=6,
            ) as table:
                head = table.row()
                for h in b["header"]:
                    head.cell(h)
                for r in b["rows"]:
                    row = table.row()
                    for v in r:
                        row.cell(_show(v))
            pdf.ln(3)
    return bytes(pdf.output())


# ---------- Word ----------


def _docx(title: str, blocks: list[dict]) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    doc.core_properties.title = title
    doc.add_heading(title, level=0)
    for b in blocks:
        if b["type"] == "heading":
            doc.add_heading(b["text"], level=b["level"])
        elif b["type"] == "paragraph":
            doc.add_paragraph(b["text"])
        elif b["type"] == "bullets":
            for item in b["items"]:
                doc.add_paragraph(item, style="List Bullet")
        elif b["type"] == "table":
            if b["title"]:
                doc.add_paragraph().add_run(b["title"]).bold = True
            numeric = _numeric_columns(b)
            table = doc.add_table(rows=1, cols=len(b["header"]))
            table.style = "Table Grid"
            for i, h in enumerate(b["header"]):
                cell = table.rows[0].cells[i]
                cell.paragraphs[0].add_run(h).bold = True
            for r in b["rows"]:
                cells = table.add_row().cells
                for i, v in enumerate(r):
                    cells[i].text = _show(v)
                    if i in numeric:
                        cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------- Excel ----------


def _sheet_name(name: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", " ", name).strip()[:31] or "Bảng"
    candidate, n = base, 2
    while candidate in used:
        suffix = f" ({n})"
        candidate, n = base[: 31 - len(suffix)] + suffix, n + 1
    used.add(candidate)
    return candidate


def _xlsx(title: str, blocks: list[dict]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.properties.title = title
    used: set[str] = set()
    text_sheet = wb.active
    text_sheet.title = _sheet_name("Nội dung", used)
    text_sheet.append([title])
    text_sheet["A1"].font = Font(bold=True, size=14)
    text_sheet.column_dimensions["A"].width = 100
    tables = 0
    for b in blocks:
        if b["type"] == "heading":
            text_sheet.append([b["text"]])
            text_sheet.cell(row=text_sheet.max_row, column=1).font = Font(
                bold=True, size={1: 13, 2: 12, 3: 11}[b["level"]]
            )
        elif b["type"] == "paragraph":
            text_sheet.append([b["text"]])
            text_sheet.cell(row=text_sheet.max_row, column=1).alignment = Alignment(wrap_text=True)
        elif b["type"] == "bullets":
            for item in b["items"]:
                text_sheet.append([f"- {item}"])
        elif b["type"] == "table":
            tables += 1
            ws = wb.create_sheet(_sheet_name(b["title"] or f"Bảng {tables}", used))
            ws.append(b["header"])
            for cell in ws[1]:
                cell.font = Font(bold=True)
            numeric = _numeric_columns(b)
            for r in b["rows"]:
                ws.append([int(v) if isinstance(v, float) and v.is_integer() else v for v in r])
            for i, h in enumerate(b["header"]):
                letter = get_column_letter(i + 1)
                longest = max([len(str(h))] + [len(_show(r[i])) for r in b["rows"][:500]])
                ws.column_dimensions[letter].width = min(max(longest + 2, 8), 60)
                if i in numeric:
                    for cell in ws[letter][1:]:
                        cell.number_format = "#,##0.##"
            ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _words(value: str) -> list[str]:
    folded = unicodedata.normalize("NFD", value.replace("đ", "d").replace("Đ", "D"))
    folded = "".join(c for c in folded if unicodedata.category(c) != "Mn").lower()
    return re.findall(r"[a-z0-9]+", folded)


def same_meaning(title: str, heading: str) -> bool:
    """Heading đầu nói lại tiêu đề (bỏ dấu, một bên là phần đầu của bên kia, hoặc trùng từ 3/4 trở lên)."""
    a, b = _words(title), _words(heading)
    if not a or not b:
        return False
    if a == b[: len(a)] or b == a[: len(b)]:
        return True
    shared = len(set(a) & set(b))
    return shared / min(len(set(a)), len(set(b))) >= 0.75


def document_title(title: str, blocks: list[dict]) -> tuple[str, list[dict]]:
    """Tiêu đề in ra và metadata. Khối đầu là heading nói lại `title` (model hay đặt title không dấu cho
    tên tệp rồi mở bài bằng heading có dấu) thì dùng heading đó, in một lần; không thì in `title`."""
    if blocks and blocks[0]["type"] == "heading" and same_meaning(title, blocks[0]["text"]):
        return blocks[0]["text"], blocks[1:]
    return title, blocks


def render_document(fmt: str, title: str, blocks: list) -> tuple[bytes, str, str]:
    """Trả `(dữ liệu, mime, phần mở rộng)`."""
    clean = validate(fmt, title, blocks)
    shown, body = document_title(title, clean)
    data = {"pdf": _pdf, "docx": _docx, "xlsx": _xlsx}[fmt](shown, body)
    return data, FORMATS[fmt], fmt
