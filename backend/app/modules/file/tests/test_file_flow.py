import io

import pytest
from moto import mock_aws

from app.core import storage
from app.core.config import get_settings
from app.modules.file import jobs, service
from app.modules.file.models import File
from app.modules.search import service as search


@pytest.fixture
def s3(monkeypatch):
    import boto3

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=get_settings().r2_bucket)
        monkeypatch.setattr(storage, "_client", lambda: client)
        yield client


def _docx_bytes(text: str) -> bytes:
    from docx import Document

    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_complete_extract_and_search(db, user, s3):
    data = _docx_bytes("Lịch trình Trà Vinh: ngày 2 ghé chùa Âng, ăn bún nước lèo.")
    up = service.create_upload(db, user.user_id, "lich trinh.docx", service.DOCX, len(data), "document", None)
    assert up["upload_url"].startswith("http")
    f = db.get(File, up["file_id"])
    storage.put_bytes(get_settings().r2_bucket, f.r2_key, data, service.DOCX)

    done = service.complete_upload(db, user.user_id, f.id)
    assert done["status"] == "ready" and done["extract_status"] == "pending"
    db.commit()

    assert jobs.extract_file_text() == 1
    db.refresh(f)
    assert f.extract_status == "done"
    hits = search.search(db, user.user_id, "chua ang", ["file"])
    assert [h["id"] for h in hits] == [f.id]


def test_complete_rejects_size_mismatch(db, user, s3):
    up = service.create_upload(db, user.user_id, "a.txt", "text/plain", 100, "document", None)
    f = db.get(File, up["file_id"])
    storage.put_bytes(get_settings().r2_bucket, f.r2_key, b"ngan", "text/plain")
    with pytest.raises(service.ValidationError):
        service.complete_upload(db, user.user_id, f.id)


def test_unsupported_and_too_large(db, user):
    with pytest.raises(service.UnsupportedFileType):
        service.create_upload(db, user.user_id, "x.exe", "application/x-msdownload", 10, "other", None)
    with pytest.raises(service.PayloadTooLarge):
        service.create_upload(
            db, user.user_id, "big.pdf", "application/pdf", 26 * 1024 * 1024, "document", None
        )
