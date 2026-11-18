"""Trạng thái hệ thống cho màn Máy chủ (12 mục 5.9) và chi phí AI (12 mục 5.2 /chat/status).

Chỉ đọc. tab_ai_run, tab_device_event là bảng của nơi khác: đọc bằng SQL, không import model.
"""

from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import clock, scheduler
from app.core.config import get_settings
from app.core.context import UserContext
from app.core.errors import NotFoundError


def ai_cost(session: Session, user: UserContext) -> dict:
    """Chi phí AI hôm nay, tháng này của người dùng; cảnh báo theo tổng tháng toàn hệ thống (QĐ-15)."""
    today = clock.to_local(clock.now(), user.timezone).date()
    day_start, _ = clock.period_range("day", today, user.timezone)
    month_start, _ = clock.period_range("month", today, user.timezone)
    week_ago = clock.now() - timedelta(days=7)
    row = session.execute(
        text(
            "SELECT "
            " coalesce(sum(cost_usd) FILTER (WHERE user_id = :u AND created_at >= :d), 0) AS today_user,"
            " coalesce(sum(cost_usd) FILTER (WHERE user_id = :u AND created_at >= :m), 0) AS month_user,"
            " coalesce(sum(cost_usd) FILTER (WHERE created_at >= :m), 0) AS month_all,"
            " coalesce(sum(cache_read_tokens) FILTER (WHERE user_id = :u AND created_at >= :w), 0) AS cache_read,"
            " coalesce(sum(input_tokens + cache_read_tokens + cache_write_5m_tokens + cache_write_1h_tokens)"
            "   FILTER (WHERE user_id = :u AND created_at >= :w), 0) AS prompt_all "
            "FROM tab_ai_run WHERE created_at >= least(CAST(:m AS timestamptz), CAST(:w AS timestamptz))"
        ),
        {"u": user.user_id, "d": day_start, "m": month_start, "w": week_ago},
    ).one()
    warn = get_settings().ai_monthly_usd
    return {
        "today_usd": round(float(row.today_user), 4),
        "month_usd": round(float(row.month_user), 4),
        "monthly_warn_usd": warn,
        "over_monthly_warning": float(row.month_all) > warn,
        "cache_read_ratio_7d": round(row.cache_read / row.prompt_all, 3) if row.prompt_all else None,
    }


def chat_status(session: Session, user: UserContext) -> dict:
    s = get_settings()
    return {
        "models": {"chat": s.ai_model_chat, "smart": s.ai_model_smart, "max": s.ai_model_max},
        "ai_configured": bool(s.anthropic_api_key),
        **ai_cost(session, user),
    }


def _last_detail(session: Session, job_name: str) -> dict | None:
    return session.execute(
        text(
            "SELECT detail, finished_at FROM tab_job_run WHERE job_name = :n AND status = 'ok' "
            "ORDER BY started_at DESC LIMIT 1"
        ),
        {"n": job_name},
    ).first()


def _count(session: Session, table: str, where: str) -> int | None:
    if session.execute(text("SELECT to_regclass(:t)"), {"t": table}).scalar() is None:
        return None
    return session.execute(text(f"SELECT count(*) FROM {table} WHERE {where}")).scalar()


def system_status(session: Session, user: UserContext) -> dict:
    jobs = [
        dict(r._mapping)
        for r in session.execute(
            text(
                "SELECT name, last_status, last_started_at, last_finished_at, next_run_at, last_error, last_duration_ms "
                "FROM tab_job_schedule ORDER BY name"
            )
        )
    ]
    backup = _last_detail(session, "backup_database")
    disk = _last_detail(session, "disk_check")
    silent = [
        dict(r._mapping)
        for r in session.execute(
            text(
                "SELECT id, name, last_event_at FROM tab_device WHERE user_id = :u AND revoked_at IS NULL "
                "AND listener_connected IS TRUE AND (last_event_at IS NULL OR last_event_at < now() - interval '24 hours')"
            ),
            {"u": user.user_id},
        )
    ]
    client_errors = session.execute(
        text(
            "SELECT count(*) FROM tab_client_log WHERE level = 'error' AND created_at >= now() - interval '24 hours'"
        )
    ).scalar()
    return {
        "jobs": jobs,
        "queues": {
            "device_event_pending": _count(session, "tab_device_event", "status = 'pending'"),
            "job_queue_pending": _count(session, "tab_job_queue", "status = 'pending'"),
            "file_extract_pending": _count(session, "tab_file", "extract_status = 'pending'"),
            "google_outbox_failed": _count(session, "tab_google_outbox", "status IN ('failed','conflict')"),
        },
        "backup": {
            "last_ok_at": backup.finished_at if backup else None,
            "size_bytes": (backup.detail or {}).get("size_bytes") if backup else None,
            "key": (backup.detail or {}).get("key") if backup else None,
            "kept": get_settings().backup_keep,
        },
        "disk": {
            "free_percent": (disk.detail or {}).get("free_percent") if disk else None,
            "state": (disk.detail or {}).get("state") if disk else None,
        },
        "ai": ai_cost(session, user),
        # OTP lọt qua điện thoại mà máy chủ chặn trong 24 giờ; phải bằng 0 (60 mục 3.5).
        "otp_blocked_server": _count(
            session,
            "tab_device_event",
            "error = 'OTP_DETECTED' AND received_at >= now() - interval '24 hours'",
        ),
        "silent_devices": silent,
        "client_errors_24h": client_errors,
    }


def request_job_run(session: Session, name: str) -> None:
    """Chỉ job theo lịch có dòng trong tab_job_schedule mới chạy ngay được (ví dụ backup_database)."""
    if not scheduler.request_run(session, name):
        raise NotFoundError("Không có việc nền này.")
