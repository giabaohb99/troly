import os
from pathlib import Path

import pytest
import yaml

from app.modules.device.otp import contains_otp
from app.modules.expense.tests.samples import load_samples

SAMSUNG = "com.samsung.android.messaging"
GOOGLE = "com.google.android.apps.messaging"

BLOCK = [
    (SAMSUNG, "Vietcombank", "Ma OTP cua Quy khach la 482913. Tuyet doi KHONG cung cap ma nay."),
    (GOOGLE, "Techcombank", "Mã xác thực giao dịch của Quý khách là 5821. Không cung cấp mã cho bất kỳ ai."),
    (SAMSUNG, "Google", "G-482913 là mã xác minh Google của bạn."),
    (GOOGLE, "Facebook", "48291374 is your Facebook confirmation code"),
    (SAMSUNG, "MoMo", "482 913"),
    ("com.zing.zalo", "Zalo", "Mã đăng nhập Zalo của bạn là 7731"),
    ("com.VCB", "VCB Digibank", "Smart OTP: 482913"),
    ("com.VCB", "VCB Digibank", "Ma giao dich 48291374 co hieu luc trong 3 phut"),
    ("org.telegram.messenger", "Telegram", "Login code: 48291. Do not give this code to anyone."),
    (SAMSUNG, "Shopee", "Your verification code is 4829"),
]
PASS = [
    ("com.zing.zalo", "Lan", "Hẹn 1530 ở quán cũ nhé, mang 200.000đ trả tiền cơm"),
    (SAMSUNG, "0912xxx678", "Anh ơi phòng 2104 tầng 21 nha"),
    (
        "com.VCB",
        "Thông báo VCB",
        "So du TK VCB 0011xxxx9876 -45,000 VND luc 18-11-2026 12:05:11. Ref MBVCB.12345678.AB12.Com trua",
    ),
    (
        "vn.com.techcombank.bb.app",
        "Techcombank",
        "TK 19xxxx4321\nSo tien: -85,000 VND\nThoi gian: 18/11/2026 09:15",
    ),
    ("com.facebook.orca", "Minh", "Năm 2026 mình đi Đà Lạt nhé"),
]


@pytest.mark.parametrize("package, title, text", BLOCK)
def test_blocks_otp(package, title, text):
    assert contains_otp(title, [text], package=package)


@pytest.mark.parametrize("package, title, text", PASS)
def test_passes_normal_messages(package, title, text):
    assert not contains_otp(title, [text], package=package)


def test_brand_sender_rule_uses_device_default_sms_package():
    assert contains_otp("ACB", ["8812 la ma cua ban"], package="com.other.sms", sms_package="com.other.sms")
    assert not contains_otp(
        "ACB", ["8812 la ma cua ban"], package="com.other.chat", sms_package="com.other.sms"
    )


def test_bank_transactions_are_not_blocked_and_no_amount_is_dropped():
    for s in load_samples():
        blocked = contains_otp(s.get("title"), [s["text"]], package=s["package"])
        if s["expect"]["kind"] != "ignore":
            assert not blocked, s["id"]
    assert contains_otp("VCB Digibank", ["Quy khach vua dang nhap tren thiet bi moi"], package="com.VCB")
    assert contains_otp(
        "MoMo", ["Xac nhan chuyen tien bang ma gui toi ban"], package="com.mservice.momotransfer"
    )
    assert not contains_otp("VPBank", ["Ban vua dang nhap"], package="vn.vpbank", expense_app=False)
    assert contains_otp("VPBank", ["Ban vua dang nhap"], package="vn.vpbank", expense_app=True)


def _shared_samples() -> list[dict]:
    path = (
        Path(os.environ.get("TESTDATA_DIR") or Path(__file__).resolve().parents[5] / "testdata")
        / "otp-samples.yaml"
    )
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else []


def test_shared_otp_samples():
    """Bộ mẫu chung với Kotlin (70 mục 3.4): mọi mẫu block bị chặn, chặn nhầm tối đa 10 phần trăm."""
    samples = _shared_samples()
    if not samples:
        pytest.skip("Chưa có testdata/otp-samples.yaml")
    missed = [
        s["id"]
        for s in samples
        if s["expect"] == "block" and not contains_otp(s.get("title"), [s["text"]], package=s["package"])
    ]
    passes = [s for s in samples if s["expect"] == "pass"]
    wrong = [s["id"] for s in passes if contains_otp(s.get("title"), [s["text"]], package=s["package"])]
    assert not missed
    assert len(wrong) <= 0.1 * max(len(passes), 1), wrong
