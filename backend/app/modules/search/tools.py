"""Công cụ AI search_everything: tìm toàn văn trên ghi chú, chat, tệp (Phase 1), hộp tin, lịch trình (20 mục 3.8)."""

import re
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai.schemas import ToolContext, ToolOutput, ToolSpec
from app.core import clock
from app.modules.search import service

Source = Literal["note", "chat", "inbox", "trip", "file"]
MAX_BUTTONS = 3
_TAG = re.compile(r"</?b>")


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(description="Chữ cần tìm; gõ không dấu vẫn ra. Dùng từ khóa chính, không cần cả câu")
    types: list[Source] | None = Field(description="Nguồn cần tìm; null là mọi nguồn")
    from_date: date | None = Field(description="Từ ngày (tính cả ngày này); null là không giới hạn")
    to_date: date | None = Field(description="Tới ngày (tính cả ngày này); null là không giới hạn")
    limit: int | None = Field(description="Số kết quả tối đa, mặc định 10, tối đa 20")


def run_search(ctx: ToolContext, data: SearchInput) -> ToolOutput:
    tz = ctx.user.timezone
    start = clock.local_day_start(data.from_date, tz) if data.from_date else None
    end = clock.local_day_start(data.to_date + timedelta(days=1), tz) if data.to_date else None
    limit = min(max(data.limit or 10, 1), 20)
    hits = service.search(
        ctx.session, ctx.user.user_id, data.query, data.types or None, start, end, limit + 5
    )
    # Tin của phiên hôm nay đã nằm trong lịch sử chat (kể cả câu vừa hỏi): bỏ để khỏi tìm ra chính nó.
    hits = [
        h
        for h in hits
        if not (h["source"] == "chat" and h["open"]["params"].get("conversation_id") == ctx.conversation_id)
    ]
    hits = hits[:limit]
    items = [
        {
            "source": h["source"],
            "id": h["id"],
            "title": h["title"],
            "date": clock.to_local(h["date"], tz).strftime("%d/%m/%Y") if h["date"] else None,
            "snippet": _TAG.sub("", h["snippet"]),
        }
        for h in hits
    ]
    third_party = any(h["source"] == "inbox" for h in hits)
    if third_party:
        for item in items:
            if item["source"] == "inbox":
                item["du_lieu_ngoai"] = {"snippet": item.pop("snippet")}
    actions = []
    for h in hits[:MAX_BUTTONS]:
        button = {k: v for k, v in h["open"].items() if k != "id"}
        button["label"] = f"Mở {h['title']}"[:60]
        actions.append(button)
    result = (
        {"items": items}
        if items
        else {"items": [], "ghi_chu": "Không tìm thấy; thử từ khóa khác hoặc ngắn hơn."}
    )
    return ToolOutput(result=result, actions=actions, contains_third_party=third_party)


TOOLS = [
    ToolSpec(
        name="search_everything",
        label="Đang tìm",
        description=(
            "Tìm toàn văn trên mọi thứ đã lưu: ghi chú, chat các ngày trước, chữ trong tệp đã gửi (PDF, Word, ảnh), "
            "hộp tin, lịch trình. Gọi khi người dùng hỏi lại điều đã ghi, đã nói, đã nhận hay đã gửi. "
            "Không ra thì thử lại một lần với từ khóa ngắn hơn."
        ),
        input_model=SearchInput,
        run=run_search,
    ),
]
