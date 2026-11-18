"""Vòng worker (10 mục 3.9): chờ NOTIFY troly_wake hoặc hết WORKER_POLL_SECONDS, chạy job hàng đợi,
chạy job theo lịch tới giờ; mỗi job dưới khóa tư vấn, lỗi một job không làm chết vòng."""

import logging
import signal
import threading

from app.core import clock
from app.core.config import get_settings
from app.core.db import SessionLocal, get_engine
from app.core.logging import setup_logging
from app.core.scheduler import due_jobs, ensure_schedule, run_job
from app.registry import import_all_models, register_integrations
from worker.jobs import build_jobs

log = logging.getLogger("troly.worker")
stop_event = threading.Event()


def handle_stop(signum, frame) -> None:
    log.info("Nhận tín hiệu dừng, làm nốt việc đang dở rồi thoát.")
    stop_event.set()


class Waker:
    """LISTEN troly_wake trên một kết nối riêng; mất kết nối thì chỉ còn vòng quét định kỳ."""

    def __init__(self) -> None:
        self.conn = None

    def _connect(self) -> None:
        raw = get_engine().raw_connection()
        self.conn = raw.driver_connection
        self.conn.autocommit = True
        self.conn.execute("LISTEN troly_wake")

    def wait(self, seconds: int) -> None:
        """Chờ theo từng nhịp 5 giây để SIGTERM thoát kịp trong 30 giây Docker cho."""
        try:
            if self.conn is None:
                self._connect()
            remaining = seconds
            while remaining > 0 and not stop_event.is_set():
                step = min(5, remaining)
                if list(self.conn.notifies(timeout=step, stop_after=1)):
                    return
                remaining -= step
        except Exception:
            log.warning("Mất kết nối LISTEN, dùng vòng quét")
            self.conn = None
            stop_event.wait(seconds)


def tick(jobs) -> None:
    for job in jobs:
        if stop_event.is_set():
            return
        if job.schedule is None:
            run_job(job)
    with SessionLocal() as session:
        ready = due_jobs(session, jobs, clock.now())
    for job in ready:
        if stop_event.is_set():
            return
        run_job(job)


def run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    import_all_models()
    register_integrations()
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    jobs = build_jobs()
    with SessionLocal() as session:
        for job in jobs:
            ensure_schedule(session, job, clock.now())
        session.commit()
    log.info("Worker chạy", extra={"jobs": len(jobs), "poll_seconds": settings.worker_poll_seconds})
    waker = Waker()
    while not stop_event.is_set():
        try:
            tick(jobs)
        except Exception:
            log.exception("Vòng worker lỗi")
        if stop_event.is_set():
            break
        waker.wait(settings.worker_poll_seconds)
    log.info("Worker đã dừng.")


if __name__ == "__main__":
    run()
