"""Chọn model, effort, bộ công cụ cho một lượt (20 mục 3.1). Mã quyết, model không tự đổi."""

import re
import unicodedata
from dataclasses import replace

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

# Câu hỏi việc ở công ty (QĐ-53): gắn mọi kết nối đang hoạt động. Viết không dấu vì so trên chữ đã normalize.
_WORK = re.compile(
    r"(?<![a-z])("
    r"cong viec|o cong ty|tren cong ty|du an|phieu|mua hang|de nghi mua|don mua|nghi phep|ngay phep|"
    r"cong no|nhan vien|nha cung cap|hop dong|phe duyet|cho duyet|ca lam|lich lam|nang luc nhom"
    r")(?![a-z])"
)
# Từ chung trong tên kết nối, không dùng để nhận ra kết nối.
_NAME_STOP = {
    "the", "and", "cua", "toi", "test", "thu", "nghiem", "dev", "mcp", "server", "app", "cong", "cty", "company",
}  # fmt: skip


def is_work_question(text: str) -> bool:
    """Câu hỏi việc ở công ty: *việc của anh ở công ty*, *phiếu mua hàng chờ duyệt*, *ngày phép còn mấy*."""
    return bool(_WORK.search(normalize(text)))


def _name_words(name: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", normalize(name)) if len(w) >= 3 and w not in _NAME_STOP}


def pick_connectors(
    text: str, connectors: list[tuple[int, str]], use_connectors: bool | list[int] | None
) -> tuple[tuple[int, str], ...]:
    """Kết nối gắn vào lượt (QĐ-56): gọi bằng @ hoặc giữ theo phiên (danh sách id; True là tất cả); không có thì
    kết nối có tên nhắc trong câu (*ERP*, *DEGO*), hoặc tất cả khi câu hỏi việc ở công ty."""
    if not connectors:
        return ()
    if isinstance(use_connectors, list):
        wanted = set(use_connectors)
        return tuple(c for c in connectors if c[0] in wanted)
    if use_connectors:
        return tuple(connectors)
    words = set(re.split(r"[^a-z0-9]+", normalize(text)))
    named = tuple(c for c in connectors if _name_words(c[1]) & words)
    if named:
        return named
    return tuple(connectors) if is_work_question(text) else ()


def normalize(text: str) -> str:
    """Chữ thường, bỏ dấu, gộp khoảng trắng: 'Nghĩ KỸ' thành 'nghi ky'."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text.lower()).strip()


def _has(text: str, phrases: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", text) for p in phrases)


# Câu đáp ngắn nối lượt dựng chuyến (oke, ừ, làm đi, trả lời ngày đi, nơi xuất phát) vẫn đi Sonnet có tìm web.
FOLLOW_UP_MAX_WORDS = 25


def is_follow_up(text: str) -> bool:
    words = normalize(text).split()
    return 0 < len(words) <= FOLLOW_UP_MAX_WORDS


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


def plan_turn(
    turn: TurnInput,
    settings: AiSettings,
    previous_task: str | None = None,
    connectors: tuple[tuple[int, str], ...] = (),
) -> TurnPlan:
    plan = _plan_turn(turn, settings, previous_task)
    if not connectors:
        return plan
    # Tra hệ thống ngoài nhiều bước (tìm công cụ, gọi vài công cụ): Haiku chat nâng lên effort medium.
    effort = "medium" if plan.effort == "low" else plan.effort
    return replace(plan, connectors=tuple(connectors), effort=effort)


def _plan_turn(turn: TurnInput, settings: AiSettings, previous_task: str | None = None) -> TurnPlan:
    mode = detect_mode(turn)
    use_opus = _has(normalize(turn.text), _OPUS)
    trip_plan = mode == "chat" and (
        is_trip_plan(turn.text) or (previous_task == "trip_plan" and is_follow_up(turn.text))
    )
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
            web_tools=True,  # Haiku có web_search cơ bản, tối đa 2 lần (prompt.build_tools)
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
    text: str,
    mode: str | None = None,
    has_attachments: bool = False,
    settings: AiSettings | None = None,
    previous_task: str | None = None,
    use_connectors: bool | list[int] | None = None,
    connectors: list[tuple[int, str]] | None = None,
) -> TurnPlan:
    """Điểm vào cho chat.service. `previous_task` là việc của lượt ngay trước (prompt.turn_task_of).
    `connectors`: (id, tên) kết nối MCP đang hoạt động (`ai.mcp.active_connectors`, rỗng khi cờ
    FEATURE_CONNECTORS tắt); `use_connectors`: kết nối gọi bằng @ trên app hoặc giữ theo phiên (QĐ-56), xem `pick_connectors`.
    `has_attachments` để dành cho luật tóm tắt tệp dài (hiện chưa đổi model)."""
    picked = pick_connectors(text, list(connectors or []), use_connectors)
    return plan_turn(TurnInput(text, mode), settings or get_ai_settings(), previous_task, picked)
