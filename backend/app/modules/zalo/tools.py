"""Công cụ AI của Zalo (QĐ-52, agent AI): bot soạn tin Zalo, tin chỉ đi khi người dùng bấm Duyệt.

Dùng `zalo.service.request_send` của agent kiến trúc: service tự tạo thẻ `send_zalo_message` và trả
`{pending_action}`; công cụ đổi thành hành động `confirm`. Duyệt xong `zalo/approvals.py` gửi. Module nạp sau cờ
FEATURE_ZALO_BRIDGE.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import ToolContext, ToolOutput, ToolSpec
from app.modules.zalo import service


class SendZaloInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_key: str = Field(
        description="Khóa cuộc trò chuyện Zalo lấy từ list_inbox (zalo:u:<id> người, zalo:g:<id> nhóm); không đoán"
    )
    text: str = Field(description="Nội dung tin, đúng lời người dùng muốn gửi, ngắn gọn")


def run_send_zalo(ctx: ToolContext, data: SendZaloInput) -> ToolOutput:
    out = service.request_send(
        ctx.session,
        ctx.user,
        conversation_key=data.conversation_key.strip(),
        text=data.text,
        conversation_id=ctx.conversation_id,
    )
    pending = out["pending_action"]
    expires = pending["expires_at"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    return ToolOutput(
        result={
            "trang_thai": "cho_duyet",
            "pending_action_id": pending["id"],
            "ghi_chu": "Đã soạn thẻ gửi Zalo; tin chỉ đi khi người dùng bấm Duyệt trên thẻ.",
        },
        actions=[
            act.confirm(
                pending_action_id=pending["id"],
                title=pending["title"],
                summary=pending["summary"],
                details=pending.get("details") or [],
                danger=bool(pending.get("danger")),
                expires_at=expires,
            )
        ],
    )


TOOLS = [
    ToolSpec(
        name="send_zalo_message",
        label="Đang soạn tin Zalo",
        description=(
            "Soạn tin Zalo gửi thay người dùng tới một người hoặc nhóm; luôn tạo thẻ duyệt, tin chỉ đi khi người dùng "
            "bấm Duyệt. Chỉ dùng khi người dùng nhờ gửi, nhắn, trả lời qua Zalo. Lấy conversation_key bằng list_inbox "
            "(app zalo) trước; không thấy người nhận thì hỏi lại, không đoán."
        ),
        input_model=SendZaloInput,
        run=run_send_zalo,
        phase=5,
    ),
]
