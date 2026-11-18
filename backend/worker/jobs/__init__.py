"""Danh sách job duy nhất của worker (10 mục 3.9). Số khóa tư vấn cố định, không đổi khi đã chạy thật."""

from datetime import timedelta

from app.core.config import get_settings
from app.core.scheduler import DailyAt, Every, Job


def build_jobs() -> list[Job]:
    from app.integrations.google import jobs as google_jobs
    from app.modules.chat import jobs as chat_jobs
    from app.modules.file import jobs as file_jobs
    from app.registry import _import_if_exists
    from worker.jobs import backup, cleanup, device_events, disk, queue

    s = get_settings()
    queue.HANDLERS["google_initial_sync"] = google_jobs.run_initial_sync
    # Module trip (4-01) có jobs.py thì nhận hai việc nền nhập và đánh giá lịch trình.
    trip_jobs = _import_if_exists("app.modules.trip.jobs")
    if trip_jobs is not None:
        queue.HANDLERS["trip_import"] = trip_jobs.run_import
        queue.HANDLERS["trip_evaluate"] = trip_jobs.run_evaluate

    def extract_unless_disk_full() -> int:
        return 0 if disk.heavy_jobs_paused() else file_jobs.extract_file_text()

    return [
        Job("run_queued_jobs", 7001, None, queue.run_queued_jobs),
        Job("extract_file_text", 7002, None, extract_unless_disk_full),
        Job("process_device_events", 7003, None, device_events.process_device_events),
        Job("push_google_outbox", 7004, None, google_jobs.push_outbox),
        # Hai job đồng bộ tự xét next_sync_at nên chạy mỗi vòng; nút Đồng bộ ngay đặt về bây giờ.
        Job("sync_google_calendar", 7005, None, google_jobs.sync_due_calendars),
        Job("pull_google_tasks_status", 7302, None, google_jobs.pull_due_tasks),
        Job("renew_google_watch", 7301, DailyAt(3, 0), google_jobs.renew_watches),
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
