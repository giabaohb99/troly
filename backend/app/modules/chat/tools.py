"""Công cụ AI của module chat (QĐ-51, agent AI): tìm điều đã nói trong các phiên cũ.

Dùng service công khai của chat: `list_conversations(q=...)` tìm phiên theo tiêu đề và nội dung, `list_messages` lấy
tin của phiên để cắt đoạn trích quanh chữ khớp. Tin của người dùng và trợ lý là dữ liệu cũ, có thể đã lỗi thời.
"""

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import AiError, ToolContext, ToolOutput, ToolSpec
from app.core import clock
from app.modules.chat import service

MAX_CONVERSATIONS = 5
MESSAGES_PER_CONVERSATION = 200
SNIPPETS_PER_CONVERSATION = 3
SNIPPET_CHARS = 220


class SearchHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(description="Chữ cần tìm, ngắn: quán bún nước lèo, lịch họp quý, khóa học tiếng Anh")
    limit: int | None = Field(default=None, description="Số phiên tối đa, mặc định 5")


def _fold(text: str | None) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return text.lower()


def _snippet(text: str, words: list[str]) -> str | None:
    folded = _fold(text)
    hits = [folded.find(w) for w in words if w and folded.find(w) >= 0]
    if not hits:
        return None
    at = min(hits)
    start = max(at - SNIPPET_CHARS // 3, 0)
    piece = " ".join(text[start : start + SNIPPET_CHARS].split())
    return ("…" if start > 0 else "") + piece + ("…" if start + SNIPPET_CHARS < len(text) else "")


def run_search_history(ctx: ToolContext, data: SearchHistoryInput) -> ToolOutput:
    query = " ".join(data.query.split())
    if len(query) < 2:
        raise AiError("VALIDATION_ERROR", "Cần chữ để tìm.")
    words = [w for w in re.split(r"\s+", _fold(query)) if len(w) >= 2]
    limit = min(max(data.limit or MAX_CONVERSATIONS, 1), 10)
    page = service.list_conversations(ctx.session, ctx.user, None, limit + 1, q=query)
    tz = ctx.user.timezone
    items, actions = [], []
    for c in page["items"]:
        if c["id"] == ctx.conversation_id:
            continue  # phiên đang nói thì model đã có trong lịch sử
        msgs = service.list_messages(ctx.session, ctx.user, c["id"], None, MESSAGES_PER_CONVERSATION)["items"]
        snippets = []
        for m in msgs:
            if m["role"] not in ("user", "assistant") or not m.get("text"):
                continue
            piece = _snippet(m["text"], words)
            if piece:
                at = (
                    clock.to_local(m["created_at"], tz).strftime("%H:%M %d/%m/%Y")
                    if m.get("created_at")
                    else None
                )
                snippets.append(
                    {"role": "người dùng" if m["role"] == "user" else "trợ lý", "at": at, "text": piece}
                )
        if not snippets:
            continue
        when = c.get("last_message_at") or c.get("started_at")
        items.append(
            {
                "conversation_id": c["id"],
                "title": c["title"],
                "ngay": clock.to_local(when, tz).strftime("%d/%m/%Y") if when else None,
                "doan_trich": snippets[-SNIPPETS_PER_CONVERSATION:],  # mới nhất trong phiên
            }
        )
        actions.append(
            act.open_screen(f"Mở phiên {c['title'] or ''}".strip()[:60], "chat", {"conversation_id": c["id"]})
        )
        if len(items) >= limit:
            break
    result: dict = {"items": items}
    if not items:
        result["ghi_chu"] = "Không thấy trong các phiên cũ; nói thẳng là chưa tìm thấy, không đoán."
    else:
        result["ghi_chu"] = (
            "Trích từ phiên cũ, số liệu có thể đã cũ; nói rõ là lần trước đã nói gì, phiên nào."
        )
    return ToolOutput(result=result, actions=actions[:5])


TOOLS = [
    ToolSpec(
        name="search_chat_history",
        label="Đang tìm trong các phiên cũ",
        description=(
            "Tìm điều đã nói trong các phiên trò chuyện cũ (theo tiêu đề và nội dung tin), trả đoạn trích kèm tên "
            "phiên, ngày và nút mở phiên. Người dùng hỏi hôm trước, lần trước đã nói gì về X thì dùng công cụ này, "
            "không đoán. Ghi chú, tệp, hộp tin thì dùng search_everything."
        ),
        input_model=SearchHistoryInput,
        run=run_search_history,
        phase=4,
    ),
]
