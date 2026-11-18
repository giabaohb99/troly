"""Job của file: trích chữ tệp vừa tải lên vào tab_file_text (11 mục 3.8)."""

import logging

from app.core.db import SessionLocal
from app.modules.file import service

log = logging.getLogger("troly.file.jobs")
BATCH = 5


def extract_file_text() -> int:
    done = 0
    with SessionLocal() as session:
        for f in service.claim_pending_extracts(session, BATCH):
            try:
                with session.begin_nested():
                    service.extract_one(session, f)
            except Exception:
                log.exception("Trích chữ lỗi", extra={"file_id": f.id})
                f.extract_status = "failed"
            done += 1
        session.commit()
    return done
