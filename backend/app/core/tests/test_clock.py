from datetime import UTC, date, datetime, timedelta

from app.core import clock

TZ = "Asia/Ho_Chi_Minh"


def vn(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=UTC) - timedelta(hours=7)


def test_chat_day_splits_at_4am():
    assert clock.chat_day(vn(2026, 11, 19, 1, 0), TZ) == date(2026, 11, 18)
    assert clock.chat_day(vn(2026, 11, 19, 3, 59), TZ) == date(2026, 11, 18)
    assert clock.chat_day(vn(2026, 11, 19, 4, 0), TZ) == date(2026, 11, 19)
    assert clock.chat_day(vn(2026, 11, 19, 23, 59), TZ) == date(2026, 11, 19)


def test_continue_previous_under_three_hours():
    last = vn(2026, 11, 19, 2, 30)
    assert clock.should_continue_previous(last, vn(2026, 11, 19, 5, 29)) is True
    assert clock.should_continue_previous(last, vn(2026, 11, 19, 5, 30)) is False
    assert clock.should_continue_previous(None, vn(2026, 11, 19, 5, 0)) is False


def test_period_day_starts_at_midnight_local():
    start, end = clock.period_range("day", date(2026, 11, 18), TZ)
    assert start == vn(2026, 11, 18, 0)
    assert end == vn(2026, 11, 19, 0)


def test_period_week_starts_monday():
    start, end = clock.period_range("week", date(2026, 11, 18), TZ)  # thứ Tư
    assert start == vn(2026, 11, 16, 0)
    assert end == vn(2026, 11, 23, 0)
    start, _ = clock.period_range("week", date(2026, 11, 16), TZ)  # chính thứ Hai
    assert start == vn(2026, 11, 16, 0)
    start, _ = clock.period_range("week", date(2026, 11, 22), TZ)  # chủ nhật
    assert start == vn(2026, 11, 16, 0)


def test_period_month_and_year_end():
    start, end = clock.period_range("month", date(2026, 12, 31), TZ)
    assert start == vn(2026, 12, 1, 0)
    assert end == vn(2027, 1, 1, 0)
    start, end = clock.period_range("month", date(2027, 2, 10), TZ)
    assert end == vn(2027, 3, 1, 0)
