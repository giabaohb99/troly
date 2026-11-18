"""Job Google cho worker (10 mục 3.9). worker/jobs/__init__.py khai lịch và số khóa.

push_outbox           hàng đợi, mỗi vòng              push_google_outbox
sync_due_calendars    hàng đợi, mỗi vòng xét hạn       sync_google_calendar (webhook gộp 10 giây, 15 phút ±25%)
pull_due_tasks        hàng đợi, mỗi vòng xét hạn       pull_google_tasks_status (15 phút ±25%)
renew_watches         03:00 hằng ngày                 renew_google_watch
run_initial_sync      tab_job_queue kind google_initial_sync
"""

from app.core.db import SessionLocal
from app.integrations.google import outbox, service
from app.integrations.google.settings import get_google_settings


def push_outbox() -> int:
    with SessionLocal() as session:
        return outbox.push_due(session)


def sync_due_calendars() -> int:
    with SessionLocal() as session:
        count = service.sync_due(session, "calendar", get_google_settings().google_sync_min_seconds)
        session.commit()
        return count


def pull_due_tasks() -> int:
    with SessionLocal() as session:
        count = service.sync_due(session, "tasks", get_google_settings().google_sync_min_seconds)
        session.commit()
        return count


def renew_watches() -> int:
    with SessionLocal() as session:
        count = service.renew_watches(session)
        session.commit()
        return count


def run_initial_sync(session, job) -> dict:
    return service.run_initial_sync(session, job)
