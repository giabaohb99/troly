from datetime import UTC, date, datetime, timedelta

from app.core import clock
from app.modules.expense import service


def vn(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=UTC) - timedelta(hours=7)


def add(db, user, amount, at, kind="expense", **kw):
    data = {"amount_vnd": amount, "kind": kind, "spent_at": at, "note": kw.pop("note", "com trua"), **kw}
    return service.create_expense(db, user, data)


def test_month_total_uses_local_midnight_and_skips_transfer(db, user, monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: vn(2026, 11, 30, 12))
    add(db, user, 45_000, vn(2026, 11, 1, 0, 5))  # ngay sau nửa đêm 1/11 giờ VN: tính vào tháng 11
    add(db, user, 100_000, vn(2026, 10, 31, 23, 55))  # 31/10 giờ VN: không tính
    add(db, user, 2_000_000, vn(2026, 11, 5, 9), kind="transfer", account="vcb", to_account="momo")
    add(db, user, 15_000_000, vn(2026, 11, 10, 9), kind="income", note="luong")
    deleted = add(db, user, 70_000, vn(2026, 11, 12, 9))
    service.delete_expenses(db, user, [deleted["id"]])

    result = service.summarize(db, user, "month", date(2026, 11, 15), None, None, "category")

    assert result["total_expense_vnd"] == 45_000
    assert result["total_transfer_vnd"] == 2_000_000
    assert result["total_income_vnd"] == 15_000_000
    assert [g["label"] for g in result["groups"]] == ["Ăn uống"]


def test_week_starts_monday(db, user, monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: vn(2026, 11, 23, 12))
    add(db, user, 10_000, vn(2026, 11, 15, 23, 59))  # chủ nhật tuần trước
    add(db, user, 20_000, vn(2026, 11, 16, 0, 1))  # thứ Hai
    add(db, user, 30_000, vn(2026, 11, 22, 23, 0))  # chủ nhật cuối tuần

    result = service.summarize(db, user, "week", date(2026, 11, 18), None, None, None)

    assert result["total_expense_vnd"] == 50_000


def test_restore_after_delete(db, user):
    e = add(db, user, 35_000, clock.now() - timedelta(hours=1), note="ca phe")
    service.delete_expenses(db, user, [e["id"]])
    restored = service.restore_expense(db, user, e["id"])
    assert restored["id"] == e["id"]


def test_guess_category_from_keywords(db, user):
    e = add(db, user, 45_000, clock.now() - timedelta(minutes=5), note="Cơm trưa")
    assert e["category"]["name"] == "Ăn uống"
    other = add(db, user, 99_000, clock.now() - timedelta(minutes=5), note="linh tinh")
    assert other["category"]["name"] == "Khác"


def test_group_by_account_uses_display_labels(db, user, monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: vn(2026, 11, 30, 12))
    add(db, user, 45_000, vn(2026, 11, 5, 9), account="momo")
    add(db, user, 30_000, vn(2026, 11, 6, 9), account="cash")
    out = service.summarize(db, user, "month", date(2026, 11, 15), None, None, "account")
    assert [(g["key"], g["label"]) for g in out["groups"]] == [("momo", "MoMo"), ("cash", "Tiền mặt")]
    item = service.list_expenses(db, user, {}, None, 10)["items"][0]
    assert item["account_label"] in ("MoMo", "Tiền mặt")
