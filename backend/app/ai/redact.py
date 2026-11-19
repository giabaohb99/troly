"""Che khóa API người dùng lỡ dán vào chat (QĐ-46): trước khi lưu tin và trước khi gửi Claude.

Bot không nhận khóa qua chat; khóa nhập ở Cài đặt (ô che, máy chủ mã hóa). Mẫu có tiền tố rõ (AIza, sk-, xai-...)
che ngay; chuỗi dài ngẫu nhiên chỉ che khi đứng sau chữ key, khóa, token để không che nhầm chữ thường.
"""

import re

KEY_MASK = "[khóa đã che]"
GENERIC_MIN = 24

_PREFIXED = re.compile(
    r"AIza[0-9A-Za-z_\-]{30,}"  # Google AI Studio, Gemini
    r"|\bsk-(?:ant-|proj-|or-)?[A-Za-z0-9_\-]{20,}"  # Anthropic, OpenAI, OpenRouter, trạm tương thích
    r"|\bxai-[A-Za-z0-9_\-]{20,}"  # xAI
    r"|\bgsk_[A-Za-z0-9]{20,}"  # Groq
    r"|\bhf_[A-Za-z0-9]{20,}"  # Hugging Face
    r"|\bgh[pousr]_[A-Za-z0-9]{30,}"  # GitHub
    r"|\bya29\.[A-Za-z0-9_\-\.]{20,}"  # Google OAuth access token
)
_GENERIC = re.compile(
    r"(?i)\b(api[\s_-]*key|key|khóa|khoá|khoa|token|secret|mật khẩu api)\b(\s*(?:là|:|=)?\s*[\"']?)"
    rf"([A-Za-z0-9_\-\.]{{{GENERIC_MIN},}})"
)


def _random_looking(value: str) -> bool:
    return any(c.isdigit() for c in value) and any(c.isalpha() for c in value)


def mask_secrets(text: str | None) -> tuple[str, bool]:
    """Trả (chữ đã che, có che không)."""
    if not text:
        return text or "", False
    found = False

    def prefixed(_m: re.Match) -> str:
        nonlocal found
        found = True
        return KEY_MASK

    out = _PREFIXED.sub(prefixed, text)

    def generic(m: re.Match) -> str:
        nonlocal found
        if not _random_looking(m.group(3)) or KEY_MASK in m.group(3):
            return m.group(0)
        found = True
        return f"{m.group(1)}{m.group(2)}{KEY_MASK}"

    out = _GENERIC.sub(generic, out)
    return out, found
