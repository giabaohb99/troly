"""Bot xuất PDF, Word, Excel (QĐ-41): tiếng Việt có dấu đọc lại đúng, cột số là số."""

import io

import pytest

from app.core.errors import ValidationError
from app.modules.file import render

TITLE = "Báo cáo chi tiêu tháng 11"
BLOCKS = [
    {"type": "heading", "level": 1, "text": "Tổng quan"},
    {
        "type": "paragraph",
        "text": "Tháng này chi nhiều cho ăn uống và đi lại; tiết kiệm được ít hơn dự kiến.",
    },
    {"type": "bullets", "items": ["Ăn uống chiếm 40%", "Đổ xăng, gửi xe", "Quà sinh nhật mẹ"]},
    {"type": "heading", "level": 2, "text": "Chi tiết theo danh mục"},
    {
        "type": "table",
        "title": "Danh mục",
        "header": ["Danh mục", "Số khoản", "Tổng (đ)"],
        "rows": [["Ăn uống", 31, 2450000], ["Đi lại", 12, 830000.5], ["Phở bò, cà phê", 4, 185000]],
    },
    {"type": "table", "header": ["Ngày", "Ghi chú"], "rows": [["01/11", "Lương về"]]},
]


def test_pdf_keeps_vietnamese_text():
    from pypdf import PdfReader

    data, mime, ext = render.render_document("pdf", TITLE, BLOCKS)
    assert (mime, ext) == ("application/pdf", "pdf") and data.startswith(b"%PDF")
    text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(data)).pages)
    for expected in (
        TITLE,
        "Tổng quan",
        "tiết kiệm được ít hơn dự kiến",
        "Quà sinh nhật mẹ",
        "Phở bò, cà phê",
        "Đi lại",
    ):
        assert expected in text, expected


def test_docx_has_headings_bullets_and_table():
    from docx import Document

    data, mime, ext = render.render_document("docx", TITLE, BLOCKS)
    assert ext == "docx" and mime.endswith("wordprocessingml.document")
    doc = Document(io.BytesIO(data))
    texts = [p.text for p in doc.paragraphs]
    assert TITLE in texts and "Chi tiết theo danh mục" in texts and "Đổ xăng, gửi xe" in texts
    table = doc.tables[0]
    assert table.cell(0, 0).text == "Danh mục" and table.cell(1, 2).text == "2.450.000"
    assert any(r.bold for r in table.cell(0, 1).paragraphs[0].runs)


def test_xlsx_one_sheet_per_table_numbers_are_numbers():
    from openpyxl import load_workbook

    data, mime, ext = render.render_document("xlsx", TITLE, BLOCKS)
    assert ext == "xlsx" and mime.endswith("spreadsheetml.sheet")
    wb = load_workbook(io.BytesIO(data))
    assert wb.sheetnames == ["Nội dung", "Danh mục", "Bảng 2"]
    ws = wb["Danh mục"]
    assert [c.value for c in ws[1]] == ["Danh mục", "Số khoản", "Tổng (đ)"] and ws["A1"].font.bold
    assert ws["C2"].value == 2450000 and isinstance(ws["C2"].value, int) and ws["C3"].value == 830000.5
    assert wb["Nội dung"]["A1"].value == TITLE


def test_no_tables_still_gives_sheet_and_bad_input_is_refused():
    from openpyxl import load_workbook

    data, _, _ = render.render_document("xlsx", "Ghi chú", [{"type": "paragraph", "text": "Một dòng"}])
    assert load_workbook(io.BytesIO(data)).sheetnames == ["Nội dung"]
    for fmt, blocks in (
        ("csv", []),
        ("pdf", [{"type": "lạ"}]),
        ("pdf", [{"type": "table", "header": ["a"], "rows": [[1, 2]]}]),
    ):
        with pytest.raises(ValidationError):
            render.render_document(fmt, "x", blocks)


def test_file_name_is_ascii_slug():
    assert render.file_name("Báo cáo chi tiêu tháng 11/2026!", "pdf") == "bao-cao-chi-tieu-thang-11-2026.pdf"


def test_title_printed_once_with_accents_and_set_as_metadata():
    from docx import Document
    from openpyxl import load_workbook
    from pypdf import PdfReader

    blocks = [
        {"type": "heading", "level": 1, "text": "Báo cáo chi tiêu tháng 11/2026 (1/11 - 18/11)"},
        {"type": "paragraph", "text": "Tổng chi 3.465.000 đ."},
    ]
    data, _, _ = render.render_document("pdf", "Bao cao chi tieu thang 11-2026", blocks)
    reader = PdfReader(io.BytesIO(data))
    text = reader.pages[0].extract_text()
    assert "Bao cao chi tieu" not in text and text.count("Báo cáo chi tiêu tháng 11/2026") == 1
    assert reader.metadata.title == "Báo cáo chi tiêu tháng 11/2026 (1/11 - 18/11)"

    doc = Document(io.BytesIO(render.render_document("docx", "Bao cao", blocks)[0]))
    assert [p.text for p in doc.paragraphs].count("Báo cáo chi tiêu tháng 11/2026 (1/11 - 18/11)") == 1
    assert doc.core_properties.title == "Báo cáo chi tiêu tháng 11/2026 (1/11 - 18/11)"
    wb = load_workbook(io.BytesIO(render.render_document("xlsx", "Bao cao", blocks)[0]))
    assert wb["Nội dung"]["A1"].value == "Báo cáo chi tiêu tháng 11/2026 (1/11 - 18/11)"

    # Không mở bài bằng heading thì in title như cũ.
    plain = render.render_document("pdf", "Ghi chú họp", [{"type": "paragraph", "text": "Nội dung"}])[0]
    assert "Ghi chú họp" in PdfReader(io.BytesIO(plain)).pages[0].extract_text()


def test_same_meaning_rule():
    assert render.same_meaning(
        "Bao cao chi tieu thang 11-2026", "Báo cáo chi tiêu tháng 11/2026 (1/11 - 18/11)"
    )
    assert render.same_meaning("Báo cáo chi tiêu", "Báo cáo chi tiêu tháng 11")
    assert not render.same_meaning("Báo cáo chi tiêu tháng 11", "Tổng quan")
