"""Danh sách job duy nhất của worker (10 mục 3.9). Số khóa tư vấn cố định, không đổi khi đã chạy thật."""

from datetime import timedelta

from app.core.config import get_settings
from app.core.scheduler import DailyAt, Every, Job


def build_jobs() -> list[Job]:
    from app.modules.chat import jobs as chat_jobs
    from app.modules.file import jobs as file_jobs
    from worker.jobs import backup, cleanup, disk, queue

    s = get_settings()

    def extract_unless_disk_full() -> int:
        return 0 if disk.heavy_jobs_paused() else file_jobs.extract_file_text()

    return [
        Job("run_queued_jobs", 7001, None, queue.run_queued_jobs),
        Job("extract_file_text", 7002, None, extract_unless_disk_full),
        Job("summarize_previous_day", 7101, DailyAt(4, 5), chat_jobs.summarize_previous_day),
        Job("expire_pending_actions", 7102, Every(timedelta(minutes=5)), chat_jobs.expire_pending_actions),
        Job(
            "backup_database",
            7201,
            DailyAt(s.backup_hour, s.backup_minute, weekday=s.backup_weekday),
            backup.backup_database,
        ),
        Job("cleanup_old_data", 7202, DailyAt(3, 30), cleanup.cleanup_old_data),
        Job("disk_check", 7203, Every(timedelta(minutes=15)), disk.disk_check, run_on_start=True),
        Job("recover_stuck_items", 7204, Every(timedelta(minutes=5)), queue.recover_stuck_items),
    ]
