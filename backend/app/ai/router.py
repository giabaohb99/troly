"""Chọn model, effort, bộ công cụ cho một lượt (20 mục 3.1). Mã quyết, model không tự đổi."""

import re
import unicodedata

from app.ai.schemas import TurnInput, TurnPlan
from app.ai.settings import AiSettings, get_ai_settings

MODES = ("chat", "think", "research", "summary")

_THINK = ("nghi ky",)
_RESEARCH = ("tim tren mang", "tra tren mang", "tra mang", "tim web", "search web", "research")
_OPUS = ("dung opus",)
# Dựng chuyến từ câu mô tả (QĐ-36: không có Maps) cần Sonnet tìm web điểm có thật.
_TRIP_PLAN = re.compile(
    r"(?<![a-z])(tao|lap|len|xep|soan|dung|goi y|thiet ke|plan)(?![a-z]).{0,40}"
    r"(lich trinh|ke hoach (di|du lich|chuyen)|chuyen di)(?![a-z])"
)


def normalize(text: str) -> str:
    """Chữ thường, bỏ dấu, gộp khoảng trắng: 'Nghĩ KỸ' thành 'nghi ky'."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text.lower()).strip()


def _has(text: str, phrases: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", text) for p in phrases)


def is_trip_plan(text: str) -> bool:
    """Câu xin dựng lịch trình mới từ mô tả: *tạo lịch trình đi Vũng Tàu 2 ngày*."""
    return bool(_TRIP_PLAN.search(normalize(text)))


def detect_mode(turn: TurnInput) -> str:
    if turn.mode in MODES:
        return turn.mode
    text = normalize(turn.text)
    if _has(text, _RESEARCH):
        return "research"
    if _has(text, _THINK):
        return "think"
    return "chat"


def plan_turn(turn: TurnInput, settings: AiSettings) -> TurnPlan:
    mode = detect_mode(turn)
    use_opus = _has(normalize(turn.text), _OPUS)
    trip_plan = mode == "chat" and is_trip_plan(turn.text)
    if trip_plan:
        return TurnPlan(
            mode="think",
            model=settings.ai_model_max if use_opus else settings.ai_model_smart,
            effort="medium",
            max_tokens=16000,
            web_tools=True,
            prefix_ttl="5m",
            use_opus=use_opus,
            task="trip_plan",
        )
    if mode == "chat" and not use_opus:
        return TurnPlan(
            mode="chat",
            model=settings.ai_model_chat,
            effort=settings.ai_effort_chat,
            max_tokens=4096,
            web_tools=False,
            prefix_ttl="1h",
        )
    effort = {"chat": "medium", "think": "medium", "research": "medium", "summary": "low"}[mode]
    return TurnPlan(
        mode=mode,
        model=settings.ai_model_max if use_opus else settings.ai_model_smart,
        effort=effort,
        max_tokens=16000,
        web_tools=mode == "research",
        prefix_ttl="5m",
        use_opus=use_opus,
    )


def supports_fallbacks(model: str) -> bool:
    """Sonnet 5.5 và Opus 5.5 có dự phòng phía máy chủ; Haiku 5.5 thì không (gửi sẽ lỗi 400)."""
    return model.startswith(("claude-sonnet-5-5", "claude-opus-5-5"))


def choose_turn(
    text: str, mode: str | None = None, has_attachments: bool = False, settings: AiSettings | None = None
) -> TurnPlan:
    """Điểm vào cho chat.service. `has_attachments` để dành cho luật tóm tắt tệp dài (hiện chưa đổi model)."""
    return plan_turn(TurnInput(text, mode), settings or get_ai_settings())
