from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core import scheduler
from app.core.models import JobRun, JobSchedule
from app.core.scheduler import DailyAt, Every, Job


def vn(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=UTC) - timedelta(hours=7)


def test_weekly_backup_runs_sunday_2am_vietnam():
    sched = DailyAt(2, 0, weekday=6)
    assert sched.next_after(vn(2026, 11, 18, 12)) == vn(2026, 11, 22, 2)  # thứ Tư -> chủ nhật
    assert sched.next_after(vn(2026, 11, 22, 2)) == vn(2026, 11, 29, 2)  # đúng giờ thì sang tuần sau
    assert sched.next_after(vn(2026, 11, 22, 1, 59)) == vn(2026, 11, 22, 2)


def test_daily_at_rolls_to_next_day():
    assert DailyAt(4, 5).next_after(vn(2026, 11, 18, 4, 6)) == vn(2026, 11, 19, 4, 5)


def test_run_job_records_schedule_and_run(db):
    calls = []
    job = Job("thu_job", 9901, Every(timedelta(minutes=5)), lambda: calls.append(1) or 3, run_on_start=True)
    scheduler.ensure_schedule(db, job, datetime.now(UTC))
    db.commit()

    assert [j.name for j in scheduler.due_jobs(db, [job], datetime.now(UTC) + timedelta(seconds=1))] == [
        "thu_job"
    ]
    scheduler.run_job(job)

    row = db.scalar(select(JobSchedule).where(JobSchedule.name == "thu_job"))
    db.refresh(row)
    assert calls == [1]
    assert row.last_status == "ok"
    assert row.next_run_at > datetime.now(UTC)
    run = db.scalar(select(JobRun).where(JobRun.job_name == "thu_job"))
    assert run.status == "ok" and run.items_processed == 3


def test_failing_job_is_recorded_not_raised(db):
    def boom():
        raise ValueError("hỏng")

    job = Job("thu_loi", 9902, Every(timedelta(minutes=5)), boom, run_on_start=True)
    scheduler.ensure_schedule(db, job, datetime.now(UTC))
    db.commit()
    scheduler.run_job(job)

    row = db.scalar(select(JobSchedule).where(JobSchedule.name == "thu_loi"))
    db.refresh(row)
    assert row.last_status == "error" and "hỏng" in row.last_error
