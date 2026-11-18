import re
from datetime import datetime

import pytest

from app.modules.expense import bank
from app.modules.expense.tests.samples import PARSERS, fixtures_dir, load_samples

TZ = "Asia/Ho_Chi_Minh"
SAMPLES = load_samples()


@pytest.mark.parametrize("s", SAMPLES, ids=lambda s: s["id"])
def test_sample_parses_as_expected(s):
    parser = PARSERS[s["package"]]
    posted = datetime.fromisoformat(s["posted_at"])
    result = bank.parse_notification(parser, s.get("title", ""), s["text"], posted, TZ)
    expect = s["expect"]
    if expect["kind"] == "ignore":
        assert result is bank.IGNORE
        return
    assert isinstance(result, bank.BankTxn), result
    fields = bank.to_expense_fields(result, parser, posted)
    for key, value in expect.items():
        actual = fields[key]
        if key == "spent_at":
            value = datetime.fromisoformat(value)
        assert actual == value, f"{key}: {actual!r} khác {value!r}"
    # Không bao giờ giữ số dư (QĐ-22).
    for raw in re.findall(r"(?:So du(?: kha dung)?|SD)\s*:?\s*([\d.,]+)", s["text"]):
        balance = int(re.sub(r"[.,]", "", raw))
        assert balance not in fields.values()
        assert raw not in str(fields.get("note") or "")


def test_fixtures_have_no_real_looking_numbers():
    for path in (fixtures_dir() / "bank-notifications").glob("*.yaml"):
        assert not re.search(r"\d{9,}", path.read_text(encoding="utf-8")), path.name


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1,000,000", 1_000_000),
        ("1.000.000", 1_000_000),
        ("1tr", 1_000_000),
        ("45,000", 45_000),
        ("500", 500),
    ],
)
def test_read_amount(raw, expected):
    assert bank.read_amount(raw) == expected


def test_signed_amount_without_space_before_currency():
    posted = datetime.fromisoformat("2026-11-18T12:00:30+07:00")
    txn = bank.parse_notification("vcb", "", "TK 0011xxxx9876 -45,000VND luc 18-11-2026 12:00", posted, TZ)
    assert txn.amount_vnd == 45_000 and txn.direction == "out" and txn.account_last4 == "9876"


def test_unknown_format_returns_none_for_ai():
    posted = datetime.fromisoformat("2026-11-18T12:00:30+07:00")
    text = "Giao dich the 4321 tai SHOP ABC da duoc chap nhan"
    assert bank.parse_notification("tcb", "", text, posted, TZ) is None


def test_time_far_from_posted_falls_back_to_posted():
    posted = datetime.fromisoformat("2026-11-18T12:00:30+07:00")
    txn = bank.parse_notification("vcb", "", "TK 0011xxxx9876 -45,000 VND luc 01-01-2025 12:00", posted, TZ)
    assert bank.to_expense_fields(txn, "vcb", posted)["spent_at"] == posted


def test_mask_names_hides_upper_case_names_only():
    text = "Ref 9KD21.88776655.NGUYEN VAN AN chuyen tien. ND: TRAN THI BICH tra QR VND"
    assert bank.mask_names(text) == "Ref 9KD21.88776655.TEN NGUOI chuyen tien. ND: TEN NGUOI tra QR VND"


def test_mask_for_ai_drops_balance_and_masks_numbers():
    text = "TK 0011223344556677 -45,000 VND. So du 2,345,000 VND. Ref chuyen cho 0912345678. The 9704xxxx1234"
    masked = bank.mask_for_ai(text)
    assert "2,345,000" not in masked and "0011223344556677" not in masked and "0912345678" not in masked
    assert "-45,000 VND" in masked and "xxxx6677" in masked and "xxxx1234" in masked and "678" in masked
