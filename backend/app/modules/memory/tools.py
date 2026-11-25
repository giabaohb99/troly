"""Công cụ AI của module memory: remember, forget, save_note (20 mục 3.5, 3.7)."""

import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import AiError, ToolContext, ToolOutput, ToolSpec
from app.modules.memory import service

SECTIONS = [
    "Xưng hô",
    "Thông tin cơ bản",
    "Gia đình và người quan trọng",
    "Công việc",
    "Ăn uống, sức khỏe",
    "Thói quen và lịch cố định",
    "Mục tiêu",
    "Ghi nhớ khác",
]
Section = Literal[
    "Xưng hô",
    "Thông tin cơ bản",
    "Gia đình và người quan trọng",
    "Công việc",
    "Ăn uống, sức khỏe",
    "Thói quen và lịch cố định",
    "Mục tiêu",
    "Ghi nhớ khác",
]


def _fold(text: str) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "d")
    text = unicodedata.normalize("NFD", text)
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").lower().split())


def _parse(markdown: str) -> tuple[list[str], dict[str, list[str]]]:
    """Tách hồ sơ thành phần mở đầu (trước mục đầu tiên) và các mục `## Tên`."""
    head: list[str] = []
    sections: dict[str, list[str]] = {}
    current: list[str] = head
    for line in markdown.replace("\r\n", "\n").split("\n"):
        if line.startswith("## "):
            current = sections.setdefault(line[3:].strip(), [])
        else:
            current.append(line)
    return head, sections


def _render(head: list[str], sections: dict[str, list[str]]) -> str:
    order = [s for s in SECTIONS if s in sections] + [s for s in sections if s not in SECTIONS]
    parts = []
    head_text = "\n".join(head).strip()
    if head_text:
        parts.append(head_text)
    for name in order:
        body = "\n".join(line for line in sections[name] if line.strip()).strip()
        parts.append(f"## {name}" + (f"\n{body}" if body else ""))
    return "\n\n".join(parts).strip() + "\n"


def add_fact(markdown: str, section: str, fact: str) -> str | None:
    """Thêm `- fact` vào mục; trả None nếu đã có dòng gần như trùng."""
    fact = " ".join(fact.split()).lstrip("-• ").strip()
    if not fact:
        raise AiError("VALIDATION_ERROR", "Điều cần nhớ đang trống.")
    if _fold(fact) in _fold(markdown):
        return None
    head, sections = _parse(markdown)
    sections.setdefault(section, []).append(f"- {fact}")
    return _render(head, sections)


def find_lines(markdown: str, match: str) -> list[str]:
    needle = _fold(match)
    return [
        line
        for line in markdown.replace("\r\n", "\n").split("\n")
        if line.strip() and not line.startswith("## ") and needle in _fold(line)
    ]


def remove_line(markdown: str, line: str) -> str:
    lines = markdown.replace("\r\n", "\n").split("\n")
    lines.remove(line)
    head, sections = _parse("\n".join(lines))
    return _render(head, sections)


def apply_changes(markdown: str, changes: list[dict]) -> str | None:
    """Áp các thay đổi rút từ lượt chat (QĐ-59) vào hồ sơ: bỏ dòng khớp đúng một dòng, thêm dòng chưa có. Không đổi
    gì thì None."""
    content = markdown
    for change in changes:
        if change.get("op") == "remove":
            lines = find_lines(content, change.get("match") or "")
            if len(lines) == 1:
                content = remove_line(content, lines[0])
        elif change.get("op") == "add":
            added = add_fact(content, change.get("section") or "Ghi nhớ khác", change.get("fact") or "")
            if added is not None:
                content = added
    return None if content.strip() == markdown.strip() else content


class RememberInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: Section = Field(description="Mục của hồ sơ lõi")
    fact: str = Field(description="Một câu ngắn cần nhớ lâu dài, ví dụ: Dị ứng tôm")
    reason: str = Field(description="Vì sao ghi, một câu ngắn")


class ForgetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match: str = Field(description="Cụm chữ có trong dòng cần quên, ví dụ: Cần Thơ")
    reason: str = Field(description="Vì sao quên, một câu ngắn")


class SaveNoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(description="Tiêu đề ngắn")
    body: str = Field(description="Nội dung, Markdown")
    tags: list[str] = Field(description="Nhãn, có thể rỗng")


def _save_profile(ctx: ToolContext, content: str, reason: str) -> tuple[int, int]:
    current = service.get_profile(ctx.session, ctx.user.user_id)
    saved = service.update_profile(
        ctx.session, ctx.user.user_id, content, current["version"], changed_by="ai", reason=reason[:200]
    )
    return saved["version"], current["version"]


def run_remember(ctx: ToolContext, data: RememberInput) -> ToolOutput:
    markdown = service.get_profile_markdown(ctx.session, ctx.user.user_id)
    content = add_fact(markdown, data.section, data.fact)
    if content is None:
        return ToolOutput(result={"trang_thai": "da_co", "ghi_chu": "Hồ sơ đã có điều này, không ghi thêm."})
    version, undo_version = _save_profile(ctx, content, data.reason)
    return ToolOutput(
        result={"trang_thai": "da_ghi", "section": data.section, "fact": data.fact, "version": version},
        actions=[act.memory_changed(f"Đã ghi nhớ: {data.fact}", version, undo_version)],
    )


def run_forget(ctx: ToolContext, data: ForgetInput) -> ToolOutput:
    markdown = service.get_profile_markdown(ctx.session, ctx.user.user_id)
    lines = find_lines(markdown, data.match)
    if not lines:
        raise AiError("NOT_FOUND", "Hồ sơ lõi không có dòng nào khớp.")
    if len(lines) > 1:
        options = [
            (line.lstrip("-• ").strip()[:60], f"Quên dòng: {line.lstrip('-• ').strip()}") for line in lines
        ]
        return ToolOutput(
            result={
                "trang_thai": "nhieu_dong",
                "candidates": lines[:5],
                "ghi_chu": "Hỏi người dùng muốn quên dòng nào.",
            },
            actions=[act.choices("Quên dòng nào?", options)],
        )
    content = remove_line(markdown, lines[0])
    version, undo_version = _save_profile(ctx, content, data.reason)
    text = lines[0].lstrip("-• ").strip()
    return ToolOutput(
        result={"trang_thai": "da_quen", "removed": text, "version": version},
        actions=[act.memory_changed(f"Đã quên: {text}", version, undo_version)],
    )


def run_save_note(ctx: ToolContext, data: SaveNoteInput) -> ToolOutput:
    note = service.create_note(ctx.session, ctx.user.user_id, data.title, data.body, data.tags, source="ai")
    return ToolOutput(result={"note_id": note["id"], "title": note["title"]})


TOOLS = [
    ToolSpec(
        name="remember",
        label="Đang ghi nhớ",
        description=(
            "Ghi một điều bền lâu vào hồ sơ lõi (nạp vào mọi lượt chat). Gọi khi người dùng nói "
            '"nhớ giúp", "từ giờ", hoặc nêu sự thật lâu dài về bản thân: dị ứng, nơi ở, người thân, '
            "công việc, mục tiêu, cách xưng hô. Không ghi chuyện một lần hay chỉ đúng hôm nay. "
            "Điều cũ mâu thuẫn thì gọi forget trước."
        ),
        input_model=RememberInput,
        run=run_remember,
    ),
    ToolSpec(
        name="forget",
        label="Đang bỏ khỏi hồ sơ",
        description=(
            "Xóa một dòng khỏi hồ sơ lõi. Gọi khi người dùng bảo quên, hoặc điều cũ trong hồ sơ đã sai. "
            "Nhiều dòng khớp thì công cụ trả nút để người dùng chọn."
        ),
        input_model=ForgetInput,
        run=run_forget,
    ),
    ToolSpec(
        name="save_note",
        label="Đang lưu ghi chú",
        description=(
            "Lưu ghi chú: ý tưởng, tài liệu, thông tin dài cần tra lại sau. Hỏi lại ghi chú cũ thì dùng "
            "search_everything."
        ),
        input_model=SaveNoteInput,
        run=run_save_note,
    ),
]
