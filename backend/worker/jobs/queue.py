"""Hàng đợi việc dài tab_job_queue và trả dòng kẹt (10 mục 3.9)."""

import logging
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import select, text

from app.core import clock
from app.core.db import SessionLocal
from app.core.models import JobQueue

log = logging.getLogger("troly.queue")
BATCH = 5
STUCK_MINUTES = 10

# kind -> hàm(session, job) trả dict kết quả. Module của phase sau đăng ký ở đây (trip_import, ...).
HANDLERS: dict[str, Callable] = {}


def run_queued_jobs() -> int:
    done = 0
    with SessionLocal() as session:
        jobs = list(
            session.scalars(
                select(JobQueue)
                .where(JobQueue.status == "pending", JobQueue.next_attempt_at <= clock.now())
                .order_by(JobQueue.id)
                .limit(BATCH)
                .with_for_update(skip_locked=True)
            )
        )
        now = clock.now()
        for job in jobs:
            job.status, job.locked_at, job.started_at = "processing", now, now
            job.attempts += 1
        session.commit()
        for job in jobs:
            handler = HANDLERS.get(job.kind)
            try:
                if handler is None:
                    raise RuntimeError(f"Chưa có xử lý cho việc {job.kind}")
                with session.begin_nested():
                    job.result = handler(session, job)
                job.status = "done"
            except Exception:
                log.exception("Việc nền lỗi", extra={"job_id": job.id, "kind": job.kind})
                job.error = "Việc nền gặp lỗi, đã ghi lại."
                if job.attempts >= job.max_attempts:
                    job.status = "failed"
                else:
                    job.status = "pending"
                    job.next_attempt_at = clock.now() + timedelta(seconds=30 * 2 ** (job.attempts - 1))
            job.finished_at = clock.now()
            session.commit()
            done += 1
    return done


def recover_stuck_items() -> int:
    """Dòng kẹt ở processing quá 10 phút (worker chết giữa chừng) trả về pending."""
    total = 0
    with SessionLocal() as session:
        for table in ("tab_job_queue", "tab_device_event", "tab_google_outbox"):
            if session.execute(text("SELECT to_regclass(:t)"), {"t": table}).scalar() is None:
                continue
            result = session.execute(
                text(
                    f"UPDATE {table} SET status = 'pending', locked_at = NULL "
                    f"WHERE status = 'processing' AND locked_at < now() - make_interval(mins => :m)"
                ),
                {"m": STUCK_MINUTES},
            )
            total += result.rowcount or 0
        session.commit()
    return total
