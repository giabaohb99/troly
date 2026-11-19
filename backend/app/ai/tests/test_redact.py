"""Che khóa API dán vào chat (QĐ-46). Khóa trong bài là giả."""

import pytest

from app.ai.redact import KEY_MASK, mask_secrets

GEMINI = "AIza" + "SyD3mo0nlyFakeKeyForTests0000000000"
OPENAI = "sk-" + "proj-abcDEF1234567890ghijKLMN"


@pytest.mark.parametrize(
    "text",
    [
        f"khóa gemini của anh đây {GEMINI} lưu giúp",
        f"dùng {OPENAI} nhé",
        "xai-" + "a1B2c3D4e5F6g7H8i9J0k1",
        "api key: Zx9Qw8Er7Ty6Ui5Op4As3Df2Gh1",
        "Khóa là 7f3a9c2e1b4d8f6a0c5e7b9d2f4a6c8e",
        "token=ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7",
    ],
)
def test_masks_api_keys(text):
    out, found = mask_secrets(text)
    assert found and KEY_MASK in out
    assert not any(part in out for part in (GEMINI, OPENAI, "7f3a9c2e1b4d", "Zx9Qw8Er7Ty6", "A1b2C3d4E5f6"))


@pytest.mark.parametrize(
    "text",
    [
        "nhớ khóa cửa nhà trước khi đi Vũng Tàu",
        "key của chuyến đi là đổ xăng đủ",
        "mã đơn hàng DH2026111900123 giao chưa",
        "https://www.google.com/maps/search/?api=1&query=cho+phuoc+hai",
        "",
    ],
)
def test_keeps_normal_text(text):
    out, found = mask_secrets(text)
    assert not found and out == text
