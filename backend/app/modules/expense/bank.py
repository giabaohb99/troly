"""Bóc tách thông báo ngân hàng, ví bằng mẫu cố định (11 mục 3.9, 70 mục 3.3). Hàm thuần, không đọc DB.

Mẫu tự soạn theo định dạng phổ biến (QĐ-35), thay bằng mẫu thật khi có. Không bao giờ trả số dư (QĐ-22).
Kết quả: `BankTxn` khi đọc được, `IGNORE` khi không phải giao dịch (khuyến mãi, đăng nhập, nhắc nợ),
`None` khi mẫu lạ để worker gọi AI sau khi che bằng `mask_for_ai`.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.modules.expense.amount import parse_amount_vnd

IGNORE = "ignore"
BANK_NAMES = {"vietcombank": "vcb", "vcb": "vcb", "techcombank": "tcb", "tcb": "tcb"}


@dataclass(frozen=True)
class BankTxn:
    direction: str  # out, in
    amount_vnd: int
    txn_type: str  # như BankExtract.txn_type của app.ai.bank_extract
    account_last4: str | None = None
    counterparty: str | None = None
    note: str | None = None
    occurred_at: datetime | None = None
    peer_bank: str | None = None  # bên kia của nạp, rút ví: vcb, tcb hoặc None
    confidence: float = 1.0


def fold(text: str) -> str:
    """Bỏ dấu, chữ thường, giữ nguyên độ dài với chuỗi NFC để cắt lại chuỗi gốc theo vị trí."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFD", ch.replace("đ", "d").replace("Đ", "D"))
        kept = "".join(c for c in base if unicodedata.category(c) != "Mn") or ch
        out.append(kept[0].lower() if len(kept) == 1 else ch.lower())
    return "".join(out)


_NUM = r"(?P<num>\d{1,3}(?:[.,]\d{3})+|\d+)"
_CUR = r"(?P<unit>\s?(?:trieu|tr|k)\b)?\s?(?P<cur>vnd|dong|d\b)?"
_SIGNED = re.compile(r"(?<![\w.,])(?P<sign>[+-])\s?" + _NUM + _CUR)
_OUT_WORDS = re.compile(r"\b(?:vua giam|ghi no|da tru|bi tru)\s*:?\s*" + _NUM + _CUR)
_IN_WORDS = re.compile(r"\b(?:vua tang|ghi co|da cong|duoc cong)\s*:?\s*" + _NUM + _CUR)
_BALANCE = re.compile(r"\b(?:so du(?: kha dung| cuoi(?: ky)?)?|sd(?:tk)?)\s*:?\s*\d[\d.,]*\s*(?:vnd|d\b)?")
_ACCOUNT = re.compile(r"(?:\b\d{0,8}[x*]{2,}|\.{3})(\d{4})\b")
_ACCOUNT_FULL = re.compile(r"\b(?:tk|tai khoan)\s*(?:vcb\s*)?(\d{2,})(\d{4})\b")
_DATE_TIME = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\s*(?:luc\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?")
_TIME_DATE = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(?:ngay\s*)?(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})")
_NOTE = re.compile(r"\b(?:noi dung|nd|mo ta|loi nhan)\s*[:.]\s*(?P<note>[^\n]+)")
_REF = re.compile(r"\bref\s+(?P<token>\S+)(?P<rest>[^\n]*)")
_NOT_TXN = (
    "khuyen mai",
    "uu dai",
    "voucher",
    "giam gia",
    "qua tang",
    "hoan tien len den",
    "dang nhap",
    "nhac no",
    "den han thanh toan",
    "sap den han",
    "lai suat",
)

_MOMO_AMT = r"(?P<num>\d{1,3}(?:[.,]\d{3})+|\d+)\s?(?P<unit>trieu|tr|k)?\s?(?:vnd|d)\b"
_MOMO = [
    (
        re.compile(r"thanh toan thanh cong\s+" + _MOMO_AMT + r"\s+(?:cho|tai)\s+(?P<who>[^.\n]+)"),
        "out",
        "purchase",
    ),
    (
        re.compile(
            r"\b(?:ban\s+)?(?:vua\s+)?nhan\s+(?:duoc\s+)?(?:tien\s+)?"
            + _MOMO_AMT
            + r"\s+tu\s+(?P<who>[^.\n]+)"
        ),
        "in",
        "transfer_in",
    ),
    (
        re.compile(r"nap tien (?:vao vi(?: momo)? )?thanh cong\s+" + _MOMO_AMT + r"(?P<tail>[^\n]*)"),
        "in",
        "wallet_topup",
    ),
    (
        re.compile(r"rut tien (?:ve ngan hang )?thanh cong\s+" + _MOMO_AMT + r"(?P<tail>[^\n]*)"),
        "out",
        "wallet_withdraw",
    ),
    (
        re.compile(r"chuyen tien thanh cong\s+" + _MOMO_AMT + r"\s+(?:toi|den|cho)\s+(?P<who>[^.\n]+)"),
        "out",
        "transfer_out",
    ),
    (re.compile(r"hoan tien thanh cong\s+" + _MOMO_AMT), "in", "refund"),
]


def read_amount(num: str, unit: str | None = None) -> int | None:
    """`45,000` và `45.000` là 45.000 đồng; `1tr` là 1.000.000. Số không đơn vị giữ nguyên (khác câu chat)."""
    unit = (unit or "").strip()
    if not unit:
        match = re.fullmatch(r"(\d+)((?:[a-z]+)?)", num.strip())
        if match and match.group(2):
            num, unit = match.groups()
    if unit:
        return parse_amount_vnd(f"{num}{unit}")
    groups = re.split(r"[.,]", num)
    if len(groups) > 1 and not all(len(g) == 3 for g in groups[1:]):
        return None
    value = int("".join(groups))
    return value if value > 0 else None


def _blank(text: str, pattern: re.Pattern) -> str:
    return pattern.sub(lambda m: " " * len(m.group(0)), text)


def _slice(orig: str, folded: str, start: int, end: int) -> str:
    return (orig if len(orig) == len(folded) else folded)[start:end]


def _occurred_at(folded: str, posted_at: datetime, tz: str) -> datetime | None:
    m = _DATE_TIME.search(folded)
    if m:
        d, mo, y, h, mi, s = m.groups()
    else:
        m = _TIME_DATE.search(folded)
        if not m:
            return None
        h, mi, s, d, mo, y = m.groups()
    year = int(y) + 2000 if len(y) == 2 else int(y)
    try:
        at = datetime(year, int(mo), int(d), int(h), int(mi), int(s or 0), tzinfo=ZoneInfo(tz))
    except ValueError:
        return None
    return sane_time(at, posted_at)


def sane_time(at: datetime | None, posted_at: datetime) -> datetime | None:
    """Giờ trong nội dung lệch xa giờ hiện thông báo thì không tin (đồng hồ máy, mẫu đọc sai)."""
    if at is None or at.tzinfo is None:
        return None
    if at > posted_at + timedelta(minutes=10) or at < posted_at - timedelta(days=3):
        return None
    return at


def _account_last4(folded: str) -> str | None:
    m = _ACCOUNT.search(folded) or _ACCOUNT_FULL.search(folded)
    return m.groups()[-1] if m else None


def _clean(text: str | None, limit: int = 200) -> str | None:
    text = re.sub(r"\s+", " ", text or "").strip(" .;,-")
    return text[:limit] or None


def _bank_note(orig: str, folded: str) -> str | None:
    m = _NOTE.search(folded)
    if m:
        return _clean(_slice(orig, folded, m.start("note"), m.end("note")))
    m = _REF.search(folded)
    if not m:
        return None
    token = _slice(orig, folded, m.start("token"), m.end("token"))
    rest = _slice(orig, folded, m.start("rest"), m.end("rest"))
    # Mã tham chiếu kiểu MBVCB.12345678.AB12.Com trua: nội dung là đoạn sau dấu chấm cuối của mã.
    head = token.rsplit(".", 1)[-1] if "." in token else ""
    return _clean(f"{head}{rest}" if head else rest)


def _parse_bank(orig: str, folded: str, posted_at: datetime, tz: str) -> BankTxn | str | None:
    work = _blank(folded, _BALANCE)
    m = _SIGNED.search(work)
    while m and not (m.group("cur") or m.group("unit")):
        m = _SIGNED.search(work, m.end())
    if m:
        direction = "out" if m.group("sign") == "-" else "in"
    elif m := _OUT_WORDS.search(work):
        direction = "out"
    elif m := _IN_WORDS.search(work):
        direction = "in"
    else:
        return IGNORE if any(k in work for k in _NOT_TXN) else None
    amount = read_amount(m.group("num"), m.group("unit"))
    if amount is None:
        return None
    # Cắt nội dung từ chuỗi gốc đã xóa trắng số dư ở cùng vị trí, để số dư không lọt vào ghi chú.
    orig_b = "".join(" " if w == " " and f != " " else o for o, f, w in zip(orig, folded, work, strict=False))
    note = _bank_note(orig_b if len(orig) == len(folded) else work, work)
    hint = fold(note or "")
    if direction == "out":
        txn_type = (
            "fee" if re.search(r"\bphi\b", hint) else "transfer_out" if "chuyen" in hint else "purchase"
        )
    else:
        txn_type = "salary" if "luong" in hint else "refund" if "hoan tien" in hint else "transfer_in"
    return BankTxn(
        direction=direction,
        amount_vnd=amount,
        txn_type=txn_type,
        account_last4=_account_last4(work),
        note=note,
        occurred_at=_occurred_at(work, posted_at, tz),
    )


def _parse_momo(orig: str, folded: str, posted_at: datetime, tz: str) -> BankTxn | str | None:
    for pattern, direction, txn_type in _MOMO:
        m = pattern.search(folded)
        if not m:
            continue
        amount = read_amount(m.group("num"), m.group("unit"))
        if amount is None:
            return None
        groups = m.groupdict()
        who = _clean(_slice(orig, folded, m.start("who"), m.end("who"))) if groups.get("who") else None
        peer = None
        if groups.get("tail"):
            peer = next(
                (code for name, code in BANK_NAMES.items() if re.search(rf"\b{name}\b", groups["tail"])), None
            )
        note_m = _NOTE.search(folded)
        note = _clean(_slice(orig, folded, note_m.start("note"), note_m.end("note"))) if note_m else None
        return BankTxn(
            direction=direction,
            amount_vnd=amount,
            txn_type=txn_type,
            counterparty=who,
            note=note,
            occurred_at=_occurred_at(folded, posted_at, tz),
            peer_bank=peer,
        )
    return IGNORE if any(k in folded for k in _NOT_TXN) else None


def parse_notification(
    parser: str, title: str, text: str, posted_at: datetime, tz: str
) -> BankTxn | str | None:
    orig = unicodedata.normalize("NFC", text or "")
    folded = fold(orig)
    if parser == "momo":
        result = _parse_momo(orig, folded, posted_at, tz)
        if result is None and title:
            # Vài thông báo MoMo để câu chính ở tiêu đề.
            t = unicodedata.normalize("NFC", title)
            result = _parse_momo(t, fold(t), posted_at, tz)
        return result
    if parser in ("vcb", "tcb"):
        return _parse_bank(orig, folded, posted_at, tz)
    return None


def to_expense_fields(txn: BankTxn, bank: str, posted_at: datetime) -> dict:
    """Đổi giao dịch đã đọc sang trường `tab_expense` (chưa ghép cặp). Nạp, rút ví là `transfer` ngay."""
    fields = {
        "amount_vnd": txn.amount_vnd,
        "kind": "expense" if txn.direction == "out" else "income",
        "account": bank,
        "account_last4": txn.account_last4,
        "to_account": None,
        "to_account_last4": None,
        "merchant": txn.counterparty,
        "note": txn.note,
        "spent_at": txn.occurred_at or posted_at,
    }
    if bank == "momo" and txn.txn_type == "wallet_topup":
        fields.update(
            kind="transfer", account=txn.peer_bank or "other", account_last4=None, to_account="momo"
        )
    elif bank == "momo" and txn.txn_type == "wallet_withdraw":
        fields.update(
            kind="transfer", account="momo", account_last4=None, to_account=txn.peer_bank or "other"
        )
    return fields


_PHONE = re.compile(r"(?<!\d)(?:\+?84|0)\d{6}(\d{3})(?!\d)")
_LONG_DIGITS = re.compile(r"(?<!\d)\d{5,}(\d{4})(?!\d)")
_MASKED_ACCOUNT = re.compile(r"(?<![\w])\d{0,8}[xX*]{2,}(\d{4})\b")


def mask_for_ai(text: str) -> str:
    """Che trước khi gửi Claude (60 mục 3.6): bỏ số dư, số tài khoản và thẻ còn xxxx + 4 số cuối,
    số điện thoại còn 3 số cuối. Thông báo có OTP đã bị bỏ từ lúc nhận nên không tới đây."""
    orig = unicodedata.normalize("NFC", text or "")
    folded = fold(orig)
    if len(orig) == len(folded):
        for m in reversed(list(_BALANCE.finditer(folded))):
            orig = orig[: m.start()] + "[đã bỏ số dư]" + orig[m.end() :]
    else:
        orig = _BALANCE.sub("[đã bỏ số dư]", folded)
    orig = _PHONE.sub(lambda m: "xxxxxxx" + m.group(1), orig)
    orig = _MASKED_ACCOUNT.sub(lambda m: "xxxx" + m.group(1), orig)
    return _LONG_DIGITS.sub(lambda m: "xxxx" + m.group(1), orig)


_WORD = re.compile(r"[^\W\d_]+")
_KEEP_UPPER = frozenset(
    {
        "VCB",
        "TCB",
        "MOMO",
        "VND",
        "QR",
        "ND",
        "TK",
        "SD",
        "REF",
        "ATM",
        "CK",
        "GD",
        "IBFT",
        "MBVCB",
        "NAPAS",
        "POS",
    }
)
NAME_PLACEHOLDER = "TEN NGUOI"


def mask_names(text: str) -> str:
    """Che tên người cho tệp mẫu (70 mục 3.3): cụm từ 2 chữ viết hoa liền nhau trở lên (NGUYEN VAN AN).
    Che dư tên cửa hàng viết hoa cũng được; tên viết thường người duyệt che tay."""
    words = [m for m in _WORD.finditer(text) if m.group(0).isupper() and m.group(0) not in _KEEP_UPPER]
    runs, current = [], []
    for m in words:
        if current and text[current[-1].end() : m.start()].strip() == "":
            current.append(m)
        else:
            if len(current) >= 2:
                runs.append(current)
            current = [m]
    if len(current) >= 2:
        runs.append(current)
    for run in reversed(runs):
        text = text[: run[0].start()] + NAME_PLACEHOLDER + text[run[-1].end() :]
    return text
