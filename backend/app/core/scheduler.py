"""Khung job của worker (10 mục 3.9): lịch chạy, khóa tư vấn, ghi tab_job_schedule và tab_job_run."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.models import JobRun, JobSchedule

log = logging.getLogger("troly.worker")

VN = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass(frozen=True)
class Every:
    """Chạy lại sau một khoảng cố định."""

    interval: timedelta

    def next_after(self, at: datetime) -> datetime:
        return at + self.interval


@dataclass(frozen=True)
class DailyAt:
    hour: int
    minute: int = 0
    weekday: int | None = None  # 0 là thứ Hai ... 6 là chủ nhật; None là mỗi ngày

    def next_after(self, at: datetime) -> datetime:
        local = at.astimezone(VN)
        candidate = local.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        while candidate <= local or (self.weekday is not None and candidate.weekday() != self.weekday):
            candidate += timedelta(days=1)
        return candidate.astimezone(ZoneInfo("UTC"))


@dataclass(frozen=True)
class Job:
    name: str
    lock_id: int
    schedule: Every | DailyAt | None  # None: job hàng đợi, chạy mỗi vòng
    run: Callable[[], int]  # trả số mục đã xử lý
    run_on_start: bool = (
        False  # chạy ngay lần đầu tạo lịch; lỡ giờ khi worker tắt thì tự bù vì next_run_at đã qua
    )


def ensure_schedule(session: Session, job: Job, now: datetime) -> None:
    if job.schedule is None:
        return
    first = now if job.run_on_start else job.schedule.next_after(now)
    session.execute(
        insert(JobSchedule)
        .values(name=job.name, next_run_at=first)
        .on_conflict_do_nothing(index_elements=["name"])
    )


def due_jobs(session: Session, jobs: list[Job], now: datetime) -> list[Job]:
    rows = dict(session.execute(select(JobSchedule.name, JobSchedule.next_run_at)).all())
    return [j for j in jobs if j.schedule is not None and rows.get(j.name) and rows[j.name] <= now]


def request_run(session: Session, name: str) -> bool:
    """Đặt job chạy ngay ở vòng worker kế tiếp (nút *Sao lưu ngay*)."""
    result = session.execute(
        text("UPDATE tab_job_schedule SET next_run_at = now() WHERE name = :n"), {"n": name}
    )
    session.execute(text("NOTIFY troly_wake, 'job'"))
    return bool(result.rowcount)


def run_job(job: Job) -> None:
    """Chạy một job dưới khóa tư vấn; lỗi ghi lại, không làm chết vòng worker."""
    with SessionLocal() as lock_session:
        conn = lock_session.connection()
        if not conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": job.lock_id}).scalar():
            return
        try:
            _run_locked(job)
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": job.lock_id})
            lock_session.commit()


def _run_locked(job: Job) -> None:
    started = clock.now()
    run_id = None
    if job.schedule is not None:
        with SessionLocal() as s:
            run = JobRun(job_name=job.name, started_at=started, status="running")
            s.add(run)
            s.execute(
                text("UPDATE tab_job_schedule SET last_started_at = :t WHERE name = :n"),
                {"t": started, "n": job.name},
            )
            s.commit()
            run_id = run.id
    t0 = time.perf_counter()
    status, error, count, detail = "ok", None, 0, None
    try:
        result = job.run()
        if isinstance(result, tuple):
            count, detail = result
        else:
            count = int(result or 0)
    except Exception as exc:
        status, error = "error", f"{type(exc).__name__}: {str(exc)[:500]}"
        log.exception("Job lỗi", extra={"job": job.name})
    duration = int((time.perf_counter() - t0) * 1000)
    if job.schedule is None:
        if status == "error":
            log.warning("Job hàng đợi lỗi", extra={"job": job.name})
        return
    finished = clock.now()
    with SessionLocal() as s:
        s.execute(
            text(
                "UPDATE tab_job_run SET finished_at = :f, status = :st, items_processed = :c, detail = "
                "CAST(:d AS jsonb), error = :e WHERE id = :i"
            ),
            {"f": finished, "st": status, "c": count, "d": _json(detail), "e": error, "i": run_id},
        )
        s.execute(
            text(
                "UPDATE tab_job_schedule SET last_finished_at = :f, last_status = :st, last_error = :e, "
                "last_duration_ms = :ms, next_run_at = :nx, updated_at = now() WHERE name = :n"
            ),
            {
                "f": finished,
                "st": status,
                "e": error,
                "ms": duration,
                "nx": job.schedule.next_after(finished),
                "n": job.name,
            },
        )
        s.commit()
    log.info("Job xong", extra={"job": job.name, "status": status, "items": count, "duration_ms": duration})


def _json(value) -> str | None:
    if value is None:
        return None
    import json

    from fastapi.encoders import jsonable_encoder

    return json.dumps(jsonable_encoder(value), ensure_ascii=False)


def batch_size() -> int:
    return get_settings().worker_batch_size
