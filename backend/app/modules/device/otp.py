"""Lọc OTP lớp máy chủ, lưới an toàn sau bộ lọc trên điện thoại (60 mục 3.5, QĐ-04).

Cùng bộ luật với plugin Kotlin; đổi luật thì tăng OTP_RULES_VERSION (trả trong /device/config)
và chạy lại testdata/otp-samples.yaml ở cả hai phía. Khớp thì bỏ cả tin, không lưu nội dung.
"""

import re
import unicodedata

OTP_RULES_VERSION = "2026-11-18.3"

KEYWORDS = (
    "otp",
    "smart otp",
    "ma xac thuc",
    "ma xac nhan",
    "ma xac minh",
    "ma kich hoat",
    "ma dang nhap",
    "ma bao mat",
    "mat khau mot lan",
    "khong cung cap ma",
    "verification code",
    "confirmation code",
    "security code",
    "login code",
    "passcode",
    "one-time",
    "one time",
    "2fa",
)
SMS_BRAND_SENDERS = (
    "Vietcombank",
    "VCB",
    "Techcombank",
    "TCB",
    "MoMo",
    "ZaloPay",
    "VNPAY",
    "MBBank",
    "VPBank",
    "ACB",
    "BIDV",
    "VietinBank",
    "Agribank",
    "TPBank",
    "Sacombank",
    "Google",
    "Facebook",
    "Zalo",
    "Shopee",
    "Grab",
)
BANK_PACKAGES = frozenset({"com.VCB", "vn.com.techcombank.bb.app", "com.mservice.momotransfer"})
SMS_PACKAGES = frozenset({"com.samsung.android.messaging", "com.google.android.apps.messaging"})

_KEYWORD = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(k) for k in KEYWORDS) + r")(?![a-z0-9])")
# Mã 4 tới 8 số đứng riêng: không dính ngày, giờ, số tiền có dấu ngăn, mã tham chiếu có dấu chấm.
_CODE = re.compile(r"(?<![\d\-/:.,])\d{4,8}(?![\d\-/:]|[.,]\d)")
_SPLIT_CODE = re.compile(r"(?<![\d\-/:.,])\d{3}[- ]\d{3}(?![\d\-/:]|[.,]\d)")
_LETTER_CODE = re.compile(r"(?<![a-z0-9])[a-z]-\d{4,8}(?!\d)")
# Dấu hiệu số tiền: có dấu ngăn nghìn hoặc có đơn vị tiền. Thiếu thì thông báo app chi tiêu không phải giao dịch.
_AMOUNT = re.compile(r"\d{1,3}(?:[.,]\d{3})+|\d+\s?(?:vnd|dong|d)(?![a-z])")
_BRANDS = frozenset(re.sub(r"\s+", "", b.lower()) for b in SMS_BRAND_SENDERS)


def _fold(text: str) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def contains_otp(
    title: str | None,
    texts: list[str],
    *,
    package: str,
    sms_package: str | None = None,
    expense_app: bool | None = None,
) -> bool:
    """`expense_app`: gói có `purpose = expense` trong danh sách nghe; bỏ trống thì theo 3 gói mặc định."""
    folded = _fold("\n".join([title or "", *[t or "" for t in texts]]))
    if expense_app is None:
        expense_app = package in BANK_PACKAGES
    # Theo nguồn (60 mục 3.5): app ngân hàng, ví mà không có số tiền thì bỏ cả tin, có mã hay không.
    if expense_app and not _AMOUNT.search(folded):
        return True
    if _LETTER_CODE.search(folded):
        return True
    has_code = bool(_CODE.search(folded) or _SPLIT_CODE.search(folded))
    if not has_code:
        return False
    if _KEYWORD.search(folded):
        return True
    if package in SMS_PACKAGES or (sms_package and package == sms_package):
        sender = re.sub(r"\s+", "", _fold(title or ""))
        if sender in _BRANDS:
            return True
    return False
