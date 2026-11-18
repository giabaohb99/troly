import pytest

from app.modules.expense.amount import parse_amount_vnd


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("45k", 45_000),
        ("45 k", 45_000),
        ("45K", 45_000),
        ("45 nghìn", 45_000),
        ("45 ngàn", 45_000),
        ("1tr2", 1_200_000),
        ("1tr", 1_000_000),
        ("1,5 triệu", 1_500_000),
        ("1.5tr", 1_500_000),
        ("2tr500", 2_500_000),
        ("2tr05", 2_050_000),
        ("1.200.000đ", 1_200_000),
        ("1,200,000 VND", 1_200_000),
        ("120000", 120_000),
        ("200 cành", 200_000),
        ("45", 45_000),
        ("999", 999_000),
        ("1000", 1_000),
        ("1 tỷ", 1_000_000_000),
        ("3k5", 3_500),
    ],
)
def test_parse_amount(raw, expected):
    assert parse_amount_vnd(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "k", "-5k", "0", "0k"])
def test_parse_amount_rejects(raw):
    assert parse_amount_vnd(raw) is None
