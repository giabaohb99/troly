"""Kiểu dữ liệu chung của tầng AI: ngữ cảnh lượt, khuôn công cụ, sự kiện (20 mục 3.2)."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel


class UserLike(Protocol):
    """`UserContext` của core: chỉ cần hai trường này."""

    user_id: int
    timezone: str


@dataclass(frozen=True)
class TurnInput:
    text: str
    mode: str | None = None  # chat | think | research | summary; None = chat


@dataclass(frozen=True)
class PrevMessage:
    role: str  # user | assistant
    text: str
    at: datetime


@dataclass(frozen=True)
class SystemParts:
    profile_md: str = ""
    summary: str | None = None
    prev_tail: list[PrevMessage] = field(default_factory=list)  # 10 tin của phiên trước khi cách dưới 3 giờ


@dataclass(frozen=True)
class TurnPlan:
    mode: str  # chat | think | research | summary
    model: str
    effort: str
    max_tokens: int
    web_tools: bool
    prefix_ttl: str  # "1h" | "5m"
    use_opus: bool = False


@dataclass(frozen=True)
class ToolContext:
    session: Any
    user: UserLike
    conversation_id: int | None
    now: datetime


@dataclass
class ToolOutput:
    result: Any
    actions: list[dict] = field(default_factory=list)
    contains_third_party: bool = False


@dataclass
class ApprovalDraft:
    title: str
    summary: str
    input: dict
    details: list[dict] = field(default_factory=list)  # [{label, value}]
    danger: bool = False


@dataclass
class ToolSpec:
    name: str
    label: str
    description: str
    input_model: type[BaseModel]
    run: Callable[[ToolContext, BaseModel], ToolOutput] | None = None
    needs_approval: Callable[[BaseModel], bool] | None = None
    prepare: Callable[[ToolContext, BaseModel], ApprovalDraft] | None = None
    execute: Callable[[ToolContext, dict], ToolOutput] | None = None
    phase: int = 1
    # strict: true bị API giới hạn cả request (20 công cụ, 16 tham số union, 24 tham số không bắt buộc).
    # Mặc định tắt; đầu vào luôn được kiểm bằng Pydantic ở vòng chat, sai thì trả lỗi để model gọi lại.
    strict: bool = False


class TurnStore(Protocol):
    """Do module chat cài. Mỗi hàm tự commit."""

    def save_assistant_message(
        self,
        content: list[dict],
        ai_run_id: int | None,
        model: str,
        text: str | None,
        citations: list[dict] | None,
        hidden: bool,
    ) -> int: ...

    def save_tool_results(self, content: list[dict], contains_third_party: bool) -> int: ...

    def create_pending_action(self, tool_name: str, draft: "ApprovalDraft") -> int: ...


@dataclass(frozen=True)
class TurnEvent:
    type: str  # text.delta | tool.started | tool.finished | action | turn.completed
    data: dict


class AiError(Exception):
    """Lỗi tầng AI có mã theo 12 mục 3.5 và câu tiếng Việt cho người dùng."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class AiRequestError(AiError):
    """API trả 400: thường do lịch sử, có thể sửa rồi gọi lại."""
