"""Tệp trên R2: tải lên bằng URL ký sẵn, tải về, xóa mềm, trích chữ để tìm (11 mục 3.8, 12 mục 5.10)."""

import base64
import hashlib
import io
import logging
import uuid
from datetime import timedelta

from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core import clock, storage
from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError, ValidationError
from app.modules.file.models import File, FileText

log = logging.getLogger("troly.file")

MAX_BYTES = 25 * 1024 * 1024
MAX_TEXT_CHARS = 200_000
MAX_OCR_PAGES = 20
UNDO_DAYS = 30
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic"}
CLAUDE_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_MIMES = IMAGE_MIMES | {
    "audio/mp4",
    "audio/ogg",
    "audio/webm",
    "audio/mpeg",
    "application/pdf",
    DOCX,
    "text/plain",
    "text/markdown",
}
EXTRACTABLE = CLAUDE_IMAGE_MIMES | {"application/pdf", DOCX, "text/plain", "text/markdown"}


class UnsupportedFileType(AppError):
    status = 415
    code = "UNSUPPORTED_FILE_TYPE"
    message = "Loại tệp này chưa hỗ trợ."


class PayloadTooLarge(AppError):
    status = 413
    code = "PAYLOAD_TOO_LARGE"
    message = "Tệp quá lớn (tối đa 25 MB)."


def _bucket() -> str:
    return get_settings().r2_bucket


def serialize(f: File, with_url: bool = False) -> dict:
    data = {
        "id": f.id,
        "original_name": f.original_name,
        "mime": f.mime,
        "size_bytes": f.size_bytes,
        "purpose": f.purpose,
        "status": f.status,
        "extract_status": f.extract_status,
        "created_at": f.created_at,
        "drive_file_id": f.drive_file_id,
        "drive_url": f.drive_web_view_link,
    }
    if with_url and f.status == "ready":
        data["download_url"] = storage.presign_get(_bucket(), f.r2_key, f.original_name)
    return data


def _get(session: Session, user_id: int, file_id: int, include_deleted: bool = False) -> File:
    stmt = select(File).where(File.id == file_id, File.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(File.deleted_at.is_(None))
    f = session.scalar(stmt)
    if f is None:
        raise NotFoundError()
    return f


def create_upload(
    session: Session,
    user_id: int,
    original_name: str,
    mime: str,
    size_bytes: int,
    purpose: str,
    sha256: str | None,
) -> dict:
    if mime not in ALLOWED_MIMES:
        raise UnsupportedFileType()
    if size_bytes > MAX_BYTES:
        raise PayloadTooLarge()
    now = clock.now()
    key = f"files/u/{user_id}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}"
    f = File(
        user_id=user_id,
        r2_key=key,
        original_name=original_name[:200],
        mime=mime,
        size_bytes=size_bytes,
        sha256=sha256,
        purpose=purpose,
    )
    session.add(f)
    session.flush()
    return {
        "file_id": f.id,
        "upload_url": storage.presign_put(_bucket(), key, mime),
        "upload_headers": {"Content-Type": mime},
        "expires_at": now + timedelta(seconds=get_settings().r2_presign_seconds),
    }


READ_MAX_BYTES = 20 * 1024 * 1024


def read_file_bytes(session: Session, user_id: int, file_id: int) -> tuple[bytes, str, str | None]:
    """Cho module khác (trip đọc tệp lịch trình): `(dữ liệu, mime, tên gốc)`, tối đa 20 MB."""
    f = _get(session, user_id, file_id)
    if f.status != "ready":
        raise ValidationError("Tệp chưa tải lên xong.")
    if f.size_bytes > READ_MAX_BYTES:
        raise PayloadTooLarge("Tệp quá lớn để đọc (tối đa 20 MB).")
    return storage.get_bytes(_bucket(), f.r2_key, READ_MAX_BYTES + 1), f.mime, f.original_name


def store_generated_file(
    session: Session, user_id: int, data: bytes, mime: str, filename: str, purpose: str
) -> dict:
    """Cho module khác lưu tệp máy chủ tạo ra (trip_export, report_export): ghi R2, dòng `ready`."""
    from app.modules.file.models import PURPOSES

    if purpose not in PURPOSES:
        raise ValidationError(fields={"purpose": "Mục đích tệp không hợp lệ."})
    if not data:
        raise ValidationError("Tệp rỗng.")
    if len(data) > MAX_BYTES:
        raise PayloadTooLarge()
    now = clock.now()
    key = f"files/u/{user_id}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}"
    storage.put_bytes(_bucket(), key, data, mime)
    f = File(
        user_id=user_id,
        r2_key=key,
        original_name=(filename or "tep")[:200],
        mime=mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        purpose=purpose,
        status="ready",
    )
    session.add(f)
    session.flush()
    return serialize(f, with_url=True)


def complete_upload(session: Session, user_id: int, file_id: int) -> dict:
    f = _get(session, user_id, file_id)
    if f.status == "ready":
        return serialize(f)
    meta = storage.head(_bucket(), f.r2_key)
    if meta is None:
        raise ValidationError("Chưa thấy tệp trên kho, tải lên lại.")
    if int(meta.get("ContentLength", -1)) != f.size_bytes:
        raise ValidationError("Kích thước tệp không khớp, tải lên lại.")
    f.status = "ready"
    if f.mime in EXTRACTABLE and f.purpose not in ("voice",):
        f.extract_status = "pending"
        session.execute(text("NOTIFY troly_wake, 'file_extract'"))
    return serialize(f)


def get_file(session: Session, user_id: int, file_id: int) -> dict:
    return serialize(_get(session, user_id, file_id), with_url=True)


def list_files(session: Session, user_id: int, purpose: str | None, cursor: str | None, limit: int) -> dict:
    stmt = select(File).where(File.user_id == user_id, File.status == "ready", File.deleted_at.is_(None))
    if purpose:
        stmt = stmt.where(File.purpose == purpose)
    if cursor:
        stmt = stmt.where(File.id < int(cursor))
    rows = list(session.scalars(stmt.order_by(File.id.desc()).limit(limit + 1)))
    items = rows[:limit]
    return {
        "items": [serialize(f) for f in items],
        "next_cursor": str(items[-1].id) if len(rows) > limit else None,
    }


def delete_file(session: Session, user_id: int, file_id: int) -> None:
    _get(session, user_id, file_id).deleted_at = clock.now()


def restore_file(session: Session, user_id: int, file_id: int) -> dict:
    f = _get(session, user_id, file_id, include_deleted=True)
    if f.deleted_at is None or f.deleted_at < clock.now() - timedelta(days=UNDO_DAYS):
        raise NotFoundError()
    f.deleted_at = None
    return serialize(f)


def describe_files(session: Session, user_id: int, file_ids: list[int]) -> dict[int, dict]:
    rows = session.scalars(select(File).where(File.user_id == user_id, File.id.in_(file_ids)))
    return {
        f.id: {"file_id": f.id, "mime": f.mime, "name": f.original_name, "size_bytes": f.size_bytes}
        for f in rows
    }


# ---------- Khối nội dung cho Claude ----------
# Tin người dùng lưu khối giữ chỗ {"type": "troly_file", "file_id": N} để DB không chứa base64;
# chat gọi materialize_blocks khi dựng lịch sử gửi Claude.


def build_claude_blocks(session: Session, user_id: int, file_ids: list[int]) -> list[dict]:
    if not file_ids:
        return []
    rows = {
        f.id: f
        for f in session.scalars(
            select(File).where(
                File.user_id == user_id,
                File.id.in_(file_ids),
                File.status == "ready",
                File.deleted_at.is_(None),
            )
        )
    }
    missing = [fid for fid in file_ids if fid not in rows]
    if missing:
        raise ValidationError(
            "Có tệp chưa tải lên xong hoặc không tồn tại.", fields={"attachment_file_ids": str(missing)}
        )
    return [{"type": "troly_file", "file_id": fid} for fid in file_ids]


def _block_for(session: Session, f: File) -> dict:
    if f.mime in CLAUDE_IMAGE_MIMES:
        data = base64.b64encode(storage.get_bytes(_bucket(), f.r2_key)).decode()
        return {"type": "image", "source": {"type": "base64", "media_type": f.mime, "data": data}}
    if f.mime == "application/pdf":
        data = base64.b64encode(storage.get_bytes(_bucket(), f.r2_key)).decode()
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data},
            "title": f.original_name or "tep.pdf",
        }
    content = session.scalar(select(FileText.content).where(FileText.file_id == f.id))
    if content is None and f.mime in EXTRACTABLE:
        content = _extract_text_only(f)
    if content:
        return {"type": "text", "text": f'<tep ten="{f.original_name}">\n{content[:50_000]}\n</tep>'}
    return {"type": "text", "text": f"(Tệp {f.original_name}, loại {f.mime}, chưa đọc được nội dung.)"}


def materialize_blocks(session: Session, user_id: int, content):
    """Đổi khối giữ chỗ thành khối Claude thật; nội dung khác giữ nguyên."""
    if not isinstance(content, list) or not any(b.get("type") == "troly_file" for b in content):
        return content
    ids = [b["file_id"] for b in content if b.get("type") == "troly_file"]
    rows = {f.id: f for f in session.scalars(select(File).where(File.user_id == user_id, File.id.in_(ids)))}
    out = []
    for block in content:
        if block.get("type") != "troly_file":
            out.append(block)
            continue
        f = rows.get(block["file_id"])
        if f is None or f.deleted_at is not None:
            out.append({"type": "text", "text": "(Tệp đã bị xóa.)"})
        else:
            out.append(_block_for(session, f))
    return out


# ---------- Trích chữ (job extract_file_text) ----------


class OcrText(BaseModel):
    text: str = Field(description="Toàn bộ chữ đọc được, giữ xuống dòng; không thêm lời bình")
    page_count: int = Field(description="Số trang hoặc số ảnh đã đọc")


def _read_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def _read_pdf(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages), len(reader.pages)


def _extract_text_only(f: File) -> str | None:
    data = storage.get_bytes(_bucket(), f.r2_key)
    if f.mime == DOCX:
        return _read_docx(data)
    if f.mime in ("text/plain", "text/markdown"):
        return data.decode("utf-8", errors="replace")
    return None


def extract_one(session: Session, f: File) -> None:
    """Trích chữ một tệp, ghi tab_file_text. Ảnh và PDF quét nhờ Haiku chép chữ."""
    data = storage.get_bytes(_bucket(), f.r2_key)
    method, pages, content = "plain", None, ""
    if f.mime == DOCX:
        method, content = "docx", _read_docx(data)
    elif f.mime in ("text/plain", "text/markdown"):
        content = data.decode("utf-8", errors="replace")
    elif f.mime == "application/pdf":
        content, pages = _read_pdf(data)
        method = "pdf_text"
        if len(content.strip()) < 20 * max(pages, 1) and pages <= MAX_OCR_PAGES:
            ocr = _ocr(f, data, "document")
            if ocr is not None:
                method, content, pages = "ai_ocr", ocr.text, ocr.page_count
    elif f.mime in CLAUDE_IMAGE_MIMES:
        ocr = _ocr(f, data, "image")
        if ocr is None:
            f.extract_status = "failed"
            return
        method, content, pages = "ai_ocr", ocr.text, ocr.page_count
    else:
        f.extract_status = "skipped"
        return
    content = content.strip()[:MAX_TEXT_CHARS]
    existing = session.get(FileText, f.id)
    if existing is None:
        session.add(
            FileText(
                file_id=f.id,
                user_id=f.user_id,
                content=content,
                method=method,
                page_count=pages,
                extracted_at=clock.now(),
            )
        )
    else:
        existing.content, existing.method, existing.page_count = content, method, pages
        existing.extracted_at = clock.now()
    f.extract_status = "done"


def _ocr(f: File, data: bytes, kind: str) -> OcrText | None:
    from app.ai.extract import extract_structured

    b64 = base64.b64encode(data).decode()
    if kind == "image":
        block = {"type": "image", "source": {"type": "base64", "media_type": f.mime, "data": b64}}
    else:
        block = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
        }
    return extract_structured(
        user_id=f.user_id,
        purpose="file_extract",
        output_model=OcrText,
        content=[block, {"type": "text", "text": "Chép lại toàn bộ chữ trong tệp này."}],
        max_tokens=16000,
    )


def claim_pending_extracts(session: Session, limit: int) -> list[File]:
    """Việc hệ thống: lấy tệp chờ trích chữ, khóa dòng để hai worker không trùng."""
    return list(
        session.scalars(
            select(File)
            .where(File.extract_status == "pending", File.status == "ready", File.deleted_at.is_(None))
            .order_by(File.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )


def request_drive_upload(session: Session, user_id: int, file_id: int) -> dict:
    """Đưa tệp lên thư mục Trợ lý trên Drive (chạy nền qua push_google_outbox, 5-01)."""
    f = _get(session, user_id, file_id)
    if f.status != "ready":
        raise ValidationError("Tệp chưa tải lên xong.")
    try:
        from app.integrations.google import drive
    except ModuleNotFoundError as exc:
        raise AppError("Chưa nối Google Drive.", code="GOOGLE_NOT_CONNECTED", status=409) from exc
    return drive.request_upload(session, user_id, file_id)


def save_generated_file(
    session: Session, user, fmt: str, title: str, blocks: list, purpose: str = "document"
) -> dict:
    """Dựng tệp PDF, Word, Excel cho công cụ `export_document` (QĐ-41), lưu R2 `files/` như tệp tải lên.

    Trả `{file_id, name, mime, size_bytes}`; app mở bằng `GET /files/{id}` (link ký sẵn).
    """
    from app.modules.file import render

    data, mime, ext = render.render_document(fmt, title, blocks)
    name = render.file_name(title, ext)
    f = store_generated_file(session, user.user_id, data, mime, name, purpose)
    return {"file_id": f["id"], "name": name, "mime": mime, "size_bytes": f["size_bytes"]}
