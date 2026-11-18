"""Báo cáo (12 mục 5.1 dòng /reports, 31 mục Báo cáo). Chỉ đọc, không có bảng riêng.

Đọc qua service công khai của expense, calendar, task, inbox, device, setting; tab_ai_run là bảng của
agent AI, đọc bằng SQL. Mỗi thẻ tính riêng trong một savepoint: thẻ lỗi không kéo thẻ khác.
"""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.context import UserContext
from app.core.errors import ValidationError
from app.modules.calendar import service as calendar
from app.modules.device import service as device
from app.modules.expense import service as expense
from app.modules.inbox import service as inbox
from app.modules.setting import service as setting
from app.modules.task import service as task

log = logging.getLogger(__name__)

TOP_CATEGORIES = 5
NEXT_EVENT_DAYS = 30
PAGE = 200
MAX_PAGES = 20
CARD_ERROR = "Chưa đọc được phần này, thử lại sau."
HEALTH_DISABLED = "Có ở bản V2."


def _card(session: Session, name: str, build) -> dict:
    try:
        with session.begin_nested():
            return {"status": "ok", "data": build(), "message": None}
    except Exception:  # thẻ lỗi riêng, các thẻ khác vẫn hiện (12 mục 5.1)
        log.exception("report card %s failed", name)
        return {"status": "error", "data": None, "message": CARD_ERROR}


def _today(user: UserContext) -> date:
    return clock.to_local(clock.now(), user.timezone).date()


def _week_start(session: Session, user: UserContext) -> int:
    return int(setting.get_value(session, user.user_id, "calendar.week_start"))


# ---------- Thẻ ----------


def expense_card(session: Session, user: UserContext, day: date) -> dict:
    cur = expense.summarize(session, user, "month", day, None, None, "category")
    prev_day = day.replace(day=1) - timedelta(days=1)
    prev = expense.summarize(session, user, "month", prev_day, None, None, None)
    return {
        "period": day.strftime("%Y-%m"),
        "total_vnd": cur["total_expense_vnd"],
        "previous_total_vnd": prev["total_expense_vnd"],
        "income_vnd": cur["total_income_vnd"],
        "top_categories": [
            {"name": g["label"], "total_vnd": g["total_vnd"]} for g in cur["groups"][:TOP_CATEGORIES]
        ],
    }


def _event_start(item: dict, tz: str) -> datetime:
    if item.get("start_at") is not None:
        return item["start_at"]
    return clock.local_day_start(item["start_date"], tz)


def calendar_card(session: Session, user: UserContext, day: date) -> dict:
    tz = user.timezone
    lo, hi = clock.period_range("week", day, tz, _week_start(session, user))
    week = [e for e in calendar.list_events(session, user, lo, hi) if e.get("status") != "cancelled"]
    now = clock.now()
    upcoming = calendar.list_events(session, user, now, now + timedelta(days=NEXT_EVENT_DAYS))
    ahead = sorted(
        (e for e in upcoming if e.get("status") != "cancelled" and _event_start(e, tz) >= now),
        key=lambda e: _event_start(e, tz),
    )
    nxt = ahead[0] if ahead else None
    return {
        "week_events": len(week),
        "next_event": (
            {"id": nxt["id"], "title": nxt["title"], "start_at": _event_start(nxt, tz)} if nxt else None
        ),
    }


def _count_tasks(session: Session, user: UserContext, due: str | None) -> int:
    total, cursor = 0, None
    for _ in range(MAX_PAGES):
        page = task.list_tasks(session, user, status="todo", due=due, cursor=cursor, limit=PAGE)
        total += len(page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    return total


def tasks_card(session: Session, user: UserContext) -> dict:
    return {
        "overdue": _count_tasks(session, user, "overdue"),
        "today": _count_tasks(session, user, "today"),
        "open": _count_tasks(session, user, None),
    }


def _count_unread(session: Session, user: UserContext, importance: str | None) -> int:
    total, cursor = 0, None
    filters = {"status": "new", "importance": importance}
    for _ in range(MAX_PAGES):
        page = inbox.list_conversations(session, user.user_id, filters, cursor, PAGE)
        total += sum(c["unread_count"] for c in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    return total


def inbox_card(session: Session, user: UserContext) -> dict:
    return {
        "important_unseen": _count_unread(session, user, "important"),
        "new_count": _count_unread(session, user, None),
    }


def ai_card(session: Session, user: UserContext) -> dict:
    today = _today(user)
    day_start, _ = clock.period_range("day", today, user.timezone)
    month_start, _ = clock.period_range("month", today, user.timezone)
    row = session.execute(
        text(
            "SELECT coalesce(sum(cost_usd) FILTER (WHERE created_at >= :d), 0) AS today_usd,"
            " coalesce(sum(cost_usd), 0) AS month_usd "
            "FROM tab_ai_run WHERE user_id = :u AND created_at >= :m"
        ),
        {"u": user.user_id, "d": day_start, "m": month_start},
    ).one()
    return {
        "month_usd": round(float(row.month_usd), 4),
        "today_usd": round(float(row.today_usd), 4),
        "monthly_warn_usd": get_settings().ai_monthly_usd,
    }


def devices_card(session: Session, user: UserContext) -> dict:
    items = [d for d in device.list_devices(session, user.user_id) if d["revoked_at"] is None]
    return {
        "items": [
            {
                "id": d["id"],
                "name": d["name"],
                "listener_connected": d["listener_connected"],
                "last_event_at": d["last_event_at"],
                "otp_blocked_today": d["otp_blocked_today"] or 0,
                "last_seen_at": d["last_seen_at"],
            }
            for d in items
        ]
    }


def dashboard(session: Session, user: UserContext, day: date | None = None) -> dict:
    day = day or _today(user)
    return {
        "date": day,
        "cards": {
            "expense": _card(session, "expense", lambda: expense_card(session, user, day)),
            "calendar": _card(session, "calendar", lambda: calendar_card(session, user, day)),
            "tasks": _card(session, "tasks", lambda: tasks_card(session, user)),
            "inbox": _card(session, "inbox", lambda: inbox_card(session, user)),
            "ai": _card(session, "ai", lambda: ai_card(session, user)),
            "devices": _card(session, "devices", lambda: devices_card(session, user)),
            "health": {"status": "disabled", "data": None, "message": HEALTH_DISABLED},
        },
    }


# ---------- Chi phí AI theo tháng (màn Cài đặt, Chi phí AI) ----------


def parse_month(value: str | None, user: UserContext) -> date:
    if not value:
        return _today(user).replace(day=1)
    try:
        return datetime.strptime(value, "%Y-%m").date()
    except ValueError as exc:
        raise ValidationError(fields={"month": "Tháng dạng YYYY-MM."}) from exc


def ai_cost(session: Session, user: UserContext, month: date) -> dict:
    tz = user.timezone
    lo, hi = clock.period_range("month", month, tz)
    params = {"u": user.user_id, "lo": lo, "hi": hi, "tz": tz}
    where = "FROM tab_ai_run WHERE user_id = :u AND created_at >= :lo AND created_at < :hi"
    total = session.execute(
        text(
            "SELECT coalesce(sum(cost_usd), 0) AS usd, coalesce(sum(cache_read_tokens), 0) AS cache_read,"
            " coalesce(sum(input_tokens + cache_read_tokens + cache_write_5m_tokens"
            " + cache_write_1h_tokens), 0) AS prompt_all " + where
        ),
        params,
    ).one()
    per_day = {
        r.day: float(r.usd)
        for r in session.execute(
            text(
                "SELECT date(timezone(:tz, created_at)) AS day, sum(cost_usd) AS usd " + where + " GROUP BY 1"
            ),
            params,
        )
    }

    def grouped(col: str) -> list[dict]:
        rows = session.execute(
            text(f"SELECT {col} AS k, sum(cost_usd) AS usd {where} GROUP BY 1 ORDER BY 2 DESC"), params
        )
        return [{col: r.k, "usd": round(float(r.usd), 4)} for r in rows]

    today = _today(user)
    last = min((hi - timedelta(days=1)).date(), today)
    days = []
    d = month.replace(day=1)
    while d <= last:
        days.append({"date": d, "usd": round(per_day.get(d, 0.0), 4)})
        d += timedelta(days=1)
    day_start, day_end = clock.period_range("day", today, tz)
    today_usd = session.scalar(
        text(
            "SELECT coalesce(sum(cost_usd), 0) FROM tab_ai_run "
            "WHERE user_id = :u AND created_at >= :lo AND created_at < :hi"
        ),
        {"u": user.user_id, "lo": day_start, "hi": day_end},
    )
    return {
        "month": month.strftime("%Y-%m"),
        "total_usd": round(float(total.usd), 4),
        "today_usd": round(float(today_usd), 4),
        "monthly_warn_usd": get_settings().ai_monthly_usd,
        "by_day": days,
        "by_model": grouped("model"),
        "by_purpose": grouped("purpose"),
        "cache_read_ratio": round(total.cache_read / total.prompt_all, 3) if total.prompt_all else None,
    }
