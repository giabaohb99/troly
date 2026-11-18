"""Bóc tách thông báo ngân hàng, ví bằng Haiku khi mẫu cố định không khớp (20 mục 3.10, việc 2-03, QĐ-35).

Lúc mới cài chưa có mẫu thật nên đây là đường chính. Hàm tự che lần nữa trước khi gửi Claude (worker đã che):
số tài khoản, số thẻ còn xxxx + 4 số cuối; bỏ số dư; thông báo có dấu hiệu OTP thì không gửi Claude, trả
*không phải giao dịch*. Hàm không ghi DB nghiệp vụ; worker quyết theo `classify`.
"""

import logging
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.ai.client import ClaudeClient
from app.ai.extract import extract_structured
from app.ai.schemas import AiError

log = logging.getLogger(__name__)

REVIEW_CONFIDENCE = 0.7

TxnType = Literal[
    "purchase",
    "transfer_out",
    "transfer_in",
    "wallet_topup",
    "wallet_withdraw",
    "fee",
    "refund",
    "salary",
    "other",
]

SYSTEM = """Bạn đọc một thông báo biến động tài khoản ngân hàng hoặc ví điện tử ở Việt Nam và trả về dữ liệu có cấu trúc.
- is_transaction: true chỉ khi thông báo báo một giao dịch tiền đã xảy ra. Quảng cáo, khuyến mãi, nhắc nợ, nhắc thanh toán sắp tới, đăng nhập, mã xác nhận, giao dịch thất bại là false.
- direction: out khi tiền rời tài khoản (dấu -, thanh toán, chuyển đi, rút), in khi tiền vào (dấu +, nhận, hoàn tiền, lương).
- amount_vnd: số tiền giao dịch, số nguyên dương, đơn vị đồng. 1,234,567 VND hoặc 1.234.567đ là 1234567. Không lấy số dư, không lấy phí đi kèm.
- account_last4: đúng 4 số cuối của tài khoản hoặc thẻ của người dùng nếu có (dạng xxxx1234), không thì null.
- txn_type: purchase (trả tiền mua hàng, dịch vụ, kể cả thanh toán hóa đơn điện, nước, internet, điện thoại), transfer_out, transfer_in, wallet_topup (nạp tiền từ ngân hàng vào ví), wallet_withdraw (rút từ ví về ngân hàng), fee (phí), refund (hoàn tiền), salary (lương), other.
- counterparty: tên người nhận, người chuyển hoặc cửa hàng nếu có. description: nội dung chuyển khoản nếu có.
- occurred_at: thời điểm giao dịch ghi trong thông báo, ISO 8601 có múi giờ +07:00; không có thì null.
- confidence: 0 tới 1, mức chắc chắn về số tiền và chiều tiền; thông báo cụt, mơ hồ thì để thấp.
Không bịa: trường không có trong thông báo thì để null. Không phải giao dịch thì direction, amount_vnd để null."""  # noqa: E501

_CURRENCY = r"(?:vnd|vnđ|đ|d|dong|đồng)\b"
_BALANCE = re.compile(
    r"(?i)(?:s[ốo]\s*d[ưu]|\bsd\b|balance|\bbal\b)(?:\s*(?:cu[ốo]i|kh[ảa]\s*d[ụu]ng|hi[ệe]n\s*t[ạa]i))?"
    r"\s*[:=]?\s*[+-]?\s*\d[\d.,]*\s*(?:" + _CURRENCY + ")?"
)
_ACCOUNT = re.compile(r"(?i)(?<![\d.,+\-])[0-9x*]{4,}([0-9]{4})(?![\d.,])(?!\s*" + _CURRENCY + ")")
_OTP = re.compile(
    r"(?i)\botp\b|m[ãa]\s*x[áa]c\s*(?:th[ựu]c|nh[ậa]n|minh)|m[ãa]\s*k[íi]ch\s*ho[ạa]t|verification code|passcode"
    r"|one[-\s]?time|security code|login code|\b2fa\b|kh[ôo]ng\s*(?:cung\s*c[ấa]p|chia\s*s[ẻe])\s*m[ãa]"
)


class BankExtract(BaseModel):
    is_transaction: bool
    direction: Literal["out", "in"] | None
    amount_vnd: int | None
    account_last4: str | None
    txn_type: TxnType
    counterparty: str | None
    description: str | None
    occurred_at: datetime | None
    confidence: float = Field(description="0 tới 1")


NOT_TRANSACTION = BankExtract(
    is_transaction=False,
    direction=None,
    amount_vnd=None,
    account_last4=None,
    txn_type="other",
    counterparty=None,
    description=None,
    occurred_at=None,
    confidence=1.0,
)


def mask_sensitive(text: str) -> str:
    """Bỏ số dư; số tài khoản, số thẻ (từ 8 ký tự) còn xxxx + 4 số cuối. Số tiền có đơn vị hoặc dấu giữ nguyên."""
    text = _BALANCE.sub("[đã bỏ số dư]", text or "")
    return _ACCOUNT.sub(lambda m: "xxxx" + m.group(1), text)


def looks_like_otp(text: str) -> bool:
    return bool(_OTP.search(text or ""))


def classify(result: BankExtract | None) -> Literal["ignore", "review", "record"]:
    """ignore: không phải giao dịch hoặc thiếu số tiền, chiều tiền; review: ghi kèm Cần xem lại; record: ghi."""
    if result is None or not result.is_transaction or not result.amount_vnd or result.direction is None:
        return "ignore"
    return "review" if result.confidence < REVIEW_CONFIDENCE else "record"


def _clean(result: BankExtract) -> BankExtract:
    """Kiểm khoảng ở mã (structured outputs không nhận ràng buộc số)."""
    if not result.is_transaction:
        return NOT_TRANSACTION.model_copy(update={"confidence": min(max(float(result.confidence), 0.0), 1.0)})
    amount = result.amount_vnd if result.amount_vnd and 0 < result.amount_vnd < 10_000_000_000 else None
    last4 = (
        result.account_last4
        if result.account_last4 and re.fullmatch(r"\d{4}", result.account_last4)
        else None
    )
    return result.model_copy(
        update={
            "amount_vnd": amount,
            "account_last4": last4,
            "confidence": min(max(float(result.confidence), 0.0), 1.0),
            "counterparty": (result.counterparty or "").strip()[:200] or None,
            "description": (result.description or "").strip()[:500] or None,
        }
    )


def extract_bank_notification(
    user_id: int,
    bank: str,
    title: str,
    text: str,
    posted_at: datetime,
    *,
    client: ClaudeClient | None = None,
) -> BankExtract | None:
    if looks_like_otp(title) or looks_like_otp(text):
        log.info("Thông báo có dấu hiệu OTP: không gửi Claude, coi là không phải giao dịch")
        return NOT_TRANSACTION
    content = (
        f"Nguồn: {bank}\n"
        f"Giờ hiện thông báo: {posted_at.isoformat()}\n"
        f"Tiêu đề: {mask_sensitive(title)}\n"
        f"Nội dung: {mask_sensitive(text)}"
    )
    try:
        result = extract_structured(
            user_id=user_id,
            purpose="bank_extract",
            output_model=BankExtract,
            content=content,
            system=SYSTEM,
            effort="low",
            max_tokens=1024,
            client=client,
        )
    except AiError as exc:
        log.warning("Bóc tách thông báo bằng AI lỗi: %s", exc.code)
        return None
    return _clean(result) if result is not None else None
