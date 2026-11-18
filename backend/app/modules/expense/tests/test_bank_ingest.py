"""Ghép cặp chuyển nội bộ, trùng, đường AI khi mẫu lạ (11 mục 3.9, 70 mục 3.3)."""

from datetime import date, datetime, timedelta

import pytest

from app.ai.bank_extract import BankExtract
from app.core import clock
from app.modules.expense import service
from app.modules.expense.models import Expense
from app.modules.expense.tests.samples import sample


@pytest.fixture(autouse=True)
def _late_clock(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: datetime.fromisoformat("2026-12-02T12:00:00+07:00"))


def ingest(db, user, sample_id, shift=timedelta(0), **kw):
    s = sample(sample_id)
    return service.ingest_bank_notification(
        db,
        user,
        bank=s["parser"],
        package=s["package"],
        title=s["title"],
        text=kw.pop("text", s["text"]),
        posted_at=s["posted_at"] + shift,
        **kw,
    )


def rows(db, user):
    return db.query(Expense).filter(Expense.user_id == user.user_id, Expense.deleted_at.is_(None)).all()


@pytest.mark.parametrize("order", [("vcb-momo-001", "momo-nap-001"), ("momo-nap-001", "vcb-momo-001")])
def test_bank_to_momo_becomes_one_transfer_either_order(db, user, order):
    first = ingest(db, user, order[0])
    second = ingest(db, user, order[1])

    assert first["result_kind"] == "expense"
    assert second["result_kind"] == "transfer_merged" and second["result_id"] == first["result_id"]
    [row] = rows(db, user)
    assert (row.kind, row.account, row.account_last4, row.to_account) == ("transfer", "vcb", "9876", "momo")
    assert row.transfer_peer_ref and row.category_id is None
    total = service.summarize(db, user, "day", date(2026, 11, 18), None, None, None)
    assert total["total_expense_vnd"] == 0 and total["total_transfer_vnd"] == 500_000


def test_momo_withdraw_to_bank_pairs(db, user):
    ingest(db, user, "tcb-momo-001")
    merged = ingest(db, user, "momo-rut-001")
    assert merged["result_kind"] == "transfer_merged"
    [row] = rows(db, user)
    assert (row.kind, row.account, row.to_account, row.to_account_last4) == (
        "transfer",
        "momo",
        "tcb",
        "4321",
    )


def test_thirty_minutes_apart_does_not_pair(db, user):
    ingest(db, user, "vcb-momo-001")
    ingest(db, user, "momo-nap-001", shift=timedelta(minutes=30))
    assert sorted(r.kind for r in rows(db, user)) == ["expense", "transfer"]


def test_different_amount_does_not_pair(db, user):
    ingest(db, user, "vcb-momo-001")
    ingest(db, user, "momo-nap-001", text="Nạp tiền thành công 400.000đ từ Vietcombank vào Ví MoMo.")
    assert len(rows(db, user)) == 2


def test_two_momo_transactions_same_amount_never_pair(db, user):
    ingest(db, user, "momo-chuyen-001")
    ingest(
        db,
        user,
        "momo-nhan-001",
        text="Bạn vừa nhận được 150.000đ từ LE VAN CUONG.",
        shift=timedelta(hours=1, minutes=47),  # 17:47, hai phút sau khoản chuyển 17:45
    )
    assert sorted(r.kind for r in rows(db, user)) == ["expense", "income"]


def test_duplicate_notification_gives_one_row(db, user):
    first = ingest(db, user, "vcb-chi-001")
    again = ingest(db, user, "vcb-chi-001", shift=timedelta(seconds=40))
    assert again["status"] == "ignored" and again["result_id"] == first["result_id"]
    assert len(rows(db, user)) == 1


def test_duplicate_of_merged_second_event_is_ignored(db, user):
    ingest(db, user, "vcb-momo-001")
    ingest(db, user, "momo-nap-001")
    again = ingest(db, user, "momo-nap-001")
    assert again["status"] == "ignored" and len(rows(db, user)) == 1


def test_ignored_notification_creates_nothing(db, user):
    assert ingest(db, user, "vcb-km-001")["status"] == "ignored"
    assert rows(db, user) == []


def _ai(result):
    calls = []

    def fake(user_id, bank, title, text, posted_at):
        calls.append(text)
        return result

    return fake, calls


UNKNOWN = "Giao dich the 9704xxxx1234 so tien 99,000 VND tai SHOP ABC. So du 3,210,000 VND"


def _extract(**kw):
    base = {
        "is_transaction": True,
        "direction": "out",
        "amount_vnd": 99_000,
        "account_last4": "1234",
        "txn_type": "purchase",
        "counterparty": "SHOP ABC",
        "description": None,
        "occurred_at": None,
        "confidence": 0.6,
    }
    return BankExtract(**{**base, **kw})


def test_unknown_format_goes_to_ai_masked_and_low_confidence_needs_review(db, user):
    fake, calls = _ai(_extract())
    out = ingest(db, user, "tcb-chi-001", text=UNKNOWN, ai_extract=fake)
    assert out["result_kind"] == "expense"
    assert "3,210,000" not in calls[0] and "xxxx1234" in calls[0]
    [row] = rows(db, user)
    assert (row.amount_vnd, row.parser, row.needs_review, row.merchant) == (99_000, "ai", True, "SHOP ABC")


def test_ai_says_not_transaction_or_fails_is_ignored(db, user):
    fake, _ = _ai(_extract(is_transaction=False, direction=None, amount_vnd=None))
    assert ingest(db, user, "tcb-chi-001", text=UNKNOWN, ai_extract=fake)["status"] == "ignored"
    fake_none, _ = _ai(None)
    assert ingest(db, user, "tcb-chi-001", text=UNKNOWN + ".", ai_extract=fake_none)["status"] == "ignored"
    assert rows(db, user) == []
