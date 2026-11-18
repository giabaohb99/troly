"""Thời gian dùng chung (10 mục 3.11). Mọi chỗ lấy giờ hiện tại đi qua now() để bài kiểm thay được."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

CHAT_DAY_START_HOUR = 4
CHAT_CONTINUE_HOURS = 3


def now() -> datetime:
    return datetime.now(UTC)


def to_local(at: datetime, tz: str) -> datetime:
    return at.astimezone(ZoneInfo(tz))


def chat_day(at: datetime, tz: str) -> date:
    """Ngày của phiên chat: tách lúc 04:00 giờ người dùng (QĐ-20)."""
    return (to_local(at, tz) - timedelta(hours=CHAT_DAY_START_HOUR)).date()


def should_continue_previous(last_message_at: datetime | None, at: datetime) -> bool:
    """Tin mới cách tin cuối dưới 3 giờ thì nối 10 tin của phiên trước (QĐ-27 mục 12)."""
    if last_message_at is None:
        return False
    return at - last_message_at < timedelta(hours=CHAT_CONTINUE_HOURS)


def local_day_start(day: date, tz: str) -> datetime:
    return datetime.combine(day, time.min, tzinfo=ZoneInfo(tz))


def period_range(period: str, day: date, tz: str, week_start: int = 1) -> tuple[datetime, datetime]:
    """Khoảng [from, to) theo giờ người dùng cho `day`, `week`, `month` (từ 00:00).

    week_start: 1 là thứ Hai (theo cài đặt calendar.week_start), 7 là chủ nhật.
    """
    if period == "day":
        start = day
        end = day + timedelta(days=1)
    elif period == "week":
        offset = (day.isoweekday() - week_start) % 7
        start = day - timedelta(days=offset)
        end = start + timedelta(days=7)
    elif period == "month":
        start = day.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
    else:
        raise ValueError(f"Kỳ không hợp lệ: {period}")
    return local_day_start(start, tz), local_day_start(end, tz)
