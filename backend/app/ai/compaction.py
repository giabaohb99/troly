"""Tóm tắt phiên dài và tóm tắt cuối ngày (20 mục 3.5). Hàm thuần: module chat đọc ghi bảng.

Luồng ở chat.service: `should_compact` -> `choose_cut` -> `summarize_messages` -> lưu summary,
summary_upto_id; lần gọi sau đặt SystemParts.strip_thinking = True.
"""

import logging

from pydantic import BaseModel, Field

from app.ai.client import ClaudeClient
from app.ai.extract import extract_structured
from app.ai.settings import AiSettings, get_ai_settings

log = logging.getLogger(__name__)

KEEP_MESSAGES = 6
SUMMARY_MAX_TOKENS = 8192

SUMMARY_SYSTEM = (
    "Bạn tóm tắt một đoạn trò chuyện giữa người dùng và trợ lý cá nhân để trợ lý đọc lại về sau. "
    "Viết tiếng Việt, gọn, đúng số liệu đã nêu (tiền, giờ, ngày). Tin nhắn của người khác chỉ ghi ở mức "
    "*có tin của X về việc Y*, không chép nguyên văn. Không ghi mã OTP, mật khẩu, số tài khoản. "
    "Mỗi mục một câu ngắn (dưới 25 chữ), mỗi phần tối đa 12 mục; gộp mục giống nhau, bỏ chi tiết vụn."
)


class SessionSummary(BaseModel):
    da_lam: list[str] = Field(description="Việc trợ lý đã làm (ghi chi tiêu, tạo việc, ghi nhớ...)")
    so_lieu: list[str] = Field(description="Số liệu, mốc giờ đã nêu trong trò chuyện")
    con_do: list[str] = Field(description="Việc còn dở, câu hỏi chưa trả lời")
    so_thich_moi: list[str] = Field(description="Sở thích, thói quen mới lộ ra")


def should_compact(last_prompt_tokens: int | None, settings: AiSettings | None = None) -> bool:
    settings = settings or get_ai_settings()
    return bool(last_prompt_tokens) and last_prompt_tokens > settings.ai_compact_tokens


def _is_user_text(msg: dict) -> bool:
    """Tin người dùng thật (không phải tin chỉ chứa tool_result): ranh giới lượt."""
    if msg.get("role") != "user":
        return False
    content = msg.get("content")
    if isinstance(content, str):
        return True
    return any(b.get("type") != "tool_result" for b in content or [])


def choose_cut(history: list[dict], keep: int = KEEP_MESSAGES) -> int:
    """Chỉ số tin đầu tiên được giữ: đếm ngược `keep` tin user/assistant rồi lùi về đầu lượt người dùng.

    Trả 0 khi phiên còn ngắn, không có gì để tóm tắt."""
    seen = 0
    idx = None
    for i in range(len(history) - 1, -1, -1):
        if history[i].get("role") in ("user", "assistant"):
            seen += 1
        if seen >= keep:
            idx = i
            break
    if idx is None:
        return 0
    while idx > 0 and not _is_user_text(history[idx]):
        idx -= 1
    return idx


def _render(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            text = content
        else:
            parts = []
            for b in content or []:
                kind = b.get("type")
                if kind == "text":
                    parts.append(b.get("text", ""))
                elif kind == "tool_use":
                    parts.append(f"[gọi {b.get('name')}]")
                elif kind == "tool_result":
                    parts.append(f"[kết quả: {str(b.get('content'))[:300]}]")
            text = " ".join(p for p in parts if p)
        if text.strip():
            lines.append(f"{m.get('role')}: {text.strip()}")
    return "\n".join(lines)


def format_summary(summary: SessionSummary) -> str:
    sections = [
        ("Đã làm", summary.da_lam),
        ("Số liệu", summary.so_lieu),
        ("Còn dở", summary.con_do),
        ("Sở thích mới", summary.so_thich_moi),
    ]
    return "\n".join(f"{title}: " + "; ".join(items) for title, items in sections if items)


def summarize_messages(
    *,
    user_id: int,
    previous_summary: str,
    messages: list[dict],
    client: ClaudeClient | None = None,
) -> str | None:
    """Gộp tóm tắt cũ và đoạn trò chuyện thành tóm tắt mới (Haiku, effort low). None nếu thất bại."""
    body = ""
    if previous_summary.strip():
        body += f"<tom_tat_cu>\n{previous_summary.strip()}\n</tom_tat_cu>\n\n"
    body += f"<tro_chuyen>\n{_render(messages)}\n</tro_chuyen>\n\nViết tóm tắt mới gộp cả hai phần."
    try:
        result = extract_structured(
            user_id=user_id,
            purpose="compaction",
            output_model=SessionSummary,
            content=body,
            system=SUMMARY_SYSTEM,
            effort="low",
            max_tokens=SUMMARY_MAX_TOKENS,
            client=client,
        )
    except Exception as exc:  # nén hỏng (JSON cắt cụt, mạng) không bao giờ được chặn lượt chat
        log.warning("Tóm tắt phiên lỗi, bỏ qua lần nén này: %s", getattr(exc, "code", type(exc).__name__))
        return None
    return format_summary(result) if result else None


def summarize(messages: list[dict], previous_summary: str | None, ctx) -> str | None:
    """Điểm vào cho chat.service: `ctx` là ToolContext (lấy user_id). None nếu Claude không tóm được."""
    return summarize_messages(
        user_id=ctx.user.user_id, previous_summary=previous_summary or "", messages=messages
    )
