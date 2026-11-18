"""export_document (QĐ-41): xuất PDF, Word, Excel qua file.service.save_generated_file; kết quả là thẻ tệp."""

from datetime import UTC, datetime

import pytest

from app.ai.schemas import AiError, ToolContext
from app.core.errors import ValidationError
from app.modules.file import service, tools

NOW = datetime(2026, 11, 18, 5, tzinfo=UTC)


@pytest.fixture
def ctx(db, user):
    return ToolContext(session=db, user=user, conversation_id=None, now=NOW)


def _run(ctx, **data):
    spec = next(t for t in tools.TOOLS if t.name == "export_document")
    return spec.run(ctx, spec.input_model.model_validate(data))


def test_export_pdf_returns_file_card(ctx, monkeypatch):
    calls = []

    def save(session, user, fmt, title, blocks, purpose="document"):
        calls.append((fmt, title, blocks))
        return {"file_id": 99, "name": "Chi-tieu-thang-11.pdf", "mime": "application/pdf", "size_bytes": 2048}

    monkeypatch.setattr(service, "save_generated_file", save)
    out = _run(
        ctx,
        title=" Chi tiêu tháng 11 ",
        blocks=[
            {"type": "heading", "text": "Tổng quan", "level": 1},
            {"type": "bullets", "items": ["Ăn uống 300.000đ"]},
            {
                "type": "table",
                "title": "Theo nhóm",
                "header": ["Nhóm", "Số tiền"],
                "rows": [["Ăn uống", 300000]],
            },
        ],
    )
    fmt, title, blocks = calls[0]
    assert fmt == "pdf" and title == "Chi tiêu tháng 11"
    assert blocks[0] == {"type": "heading", "text": "Tổng quan", "level": 1}
    assert blocks[2] == {
        "type": "table",
        "title": "Theo nhóm",
        "header": ["Nhóm", "Số tiền"],
        "rows": [["Ăn uống", 300000]],
    }
    card = out.actions[0]
    assert card["type"] == "file" and card["file_id"] == 99 and card["label"] == "Chi-tieu-thang-11.pdf"
    assert out.result == {
        "file_id": 99,
        "name": "Chi-tieu-thang-11.pdf",
        "mime": "application/pdf",
        "size_bytes": 2048,
    }


def test_render_validation_error_is_explained_to_model(ctx, monkeypatch):
    def save(*a, **k):
        raise ValidationError(fields={"blocks": "Mỗi dòng của bảng phải đủ số cột như dòng đầu."})

    monkeypatch.setattr(service, "save_generated_file", save)
    with pytest.raises(AiError) as err:
        _run(ctx, title="X", format="xlsx", blocks=[{"type": "table", "header": ["A", "B"], "rows": [["1"]]}])
    assert "đủ số cột" in err.value.message


def test_export_real_render_xlsx(ctx, monkeypatch):
    """Chạy render thật của agent kiến trúc; chỉ giả phần ghi R2."""
    stored = []

    def store(session, user_id, data, mime, filename, purpose):
        stored.append((len(data), mime, filename, purpose))
        return {"id": 5, "size_bytes": len(data)}

    monkeypatch.setattr(service, "store_generated_file", store)
    out = _run(
        ctx,
        title="Chi tiêu",
        format="xlsx",
        blocks=[
            {"type": "table", "header": ["Nhóm", "Số tiền"], "rows": [["Ăn uống", 300000], ["Xăng", 120000]]}
        ],
    )
    assert stored[0][0] > 0 and stored[0][2].endswith(".xlsx")
    assert out.actions[0]["mime"].endswith("spreadsheetml.sheet")


def test_empty_document_rejected(ctx):
    with pytest.raises(AiError):
        _run(ctx, title="Rỗng", blocks=[])
