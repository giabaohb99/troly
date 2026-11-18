"""Đọc số tiền tiếng Việt thành số nguyên VND (10 mục 3.11, 20 mục 3.10b).

45k = 45.000; 1tr2 = 1.200.000; 1,5 triệu; 1.200.000đ; 200 cành = 200.000;
số không đơn vị nhỏ hơn 1.000 hiểu là nghìn đồng.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

_UNITS = {
    "k": 1_000,
    "nghin": 1_000,
    "ngan": 1_000,
    "canh": 1_000,
    "tr": 1_000_000,
    "trieu": 1_000_000,
    "cu": 1_000_000,
    "m": 1_000_000,
    "ty": 1_000_000_000,
    "ti": 1_000_000_000,
}
_CURRENCY = ("vnd", "dong", "d")
_PATTERN = re.compile(r"^(\d+(?:[.,]\d+)*)\s*([a-z]*)\s*(\d*)$")


def _fold(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower().strip()


def _plain_number(raw: str) -> Decimal | None:
    """`1.200.000` và `1,200,000` là số nguyên có dấu ngăn nghìn; `1,5` và `1.5` là số thập phân."""
    groups = re.split(r"[.,]", raw)
    if len(groups) > 1 and all(len(g) == 3 for g in groups[1:]):
        return Decimal("".join(groups))
    if len(groups) == 2:
        return Decimal(f"{groups[0]}.{groups[1]}")
    if len(groups) == 1:
        return Decimal(groups[0])
    return None


def parse_amount_vnd(text: str) -> int | None:
    folded = _fold(text)
    for suffix in _CURRENCY:
        if folded.endswith(suffix) and not folded.endswith(("k" + suffix,)):
            stripped = folded[: -len(suffix)].strip()
            if stripped and stripped[-1].isdigit():
                folded = stripped
                break
    match = _PATTERN.match(folded)
    if not match:
        return None
    number_raw, unit, tail = match.groups()
    try:
        number = _plain_number(number_raw)
    except InvalidOperation:
        return None
    if number is None:
        return None
    if unit:
        multiplier = _UNITS.get(unit)
        if multiplier is None:
            return None
        if tail:
            if any(c in number_raw for c in ".,"):
                return None
            number = number + Decimal(f"0.{tail}")
        value = number * multiplier
    else:
        if tail:
            return None
        value = number * 1_000 if number < 1_000 and number == number.to_integral_value() else number
    amount = int(value)
    return amount if amount > 0 else None
