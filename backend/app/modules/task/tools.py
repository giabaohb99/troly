"""Công cụ AI của việc cần làm: add_task, update_task, list_tasks, delete_task (20 mục 3.7, việc 3-02).

Xóa một việc làm ngay, có Hoàn tác; xóa từ 2 việc qua thẻ duyệt (QĐ-27). Việc có giờ tự sinh sự kiện lịch.
"""

from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import AiError, ApprovalDraft, ToolContext, ToolOutput, ToolSpec
from app.core import clock
from app.modules.task import service

Priority = Literal["low", "normal", "high"]
UNDO_MINUTES = 10
MAX_DELETE = 50


def _when(t: dict, tz: str) -> str | None:
    if t.get("due_at"):
        return clock.to_local(t["due_at"], tz).strftime("%H:%M %d/%m/%Y")
    if t.get("due_date"):
        return t["due_date"].strftime("%d/%m/%Y")
    return None


def _brief(t: dict, tz: str) -> dict:
    return {
        "task_id": t["id"],
        "title": t["title"],
        "status": t["status"],
        "priority": t["priority"],
        "due": _when(t, tz),
        "note": t.get("note"),
    }


class AddTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(description="Tên việc ngắn")
    due_date: date | None = Field(
        description="Hạn theo ngày (không giờ); null nếu có due_at hoặc không có hạn"
    )
    due_at: datetime | None = Field(description="Hạn có giờ, ISO 8601 có múi giờ; việc có giờ tự lên lịch")
    priority: Priority | None = Field(description="Ưu tiên; null là normal")
    remind_minutes: list[int] | None = Field(description="Nhắc trước bao nhiêu phút (chỉ khi có due_at)")
    note: str | None


class UpdateTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: int
    title: str | None
    due_date: date | None = Field(description="Hạn mới theo ngày; null là giữ nguyên")
    due_at: datetime | None = Field(description="Hạn mới có giờ; null là giữ nguyên")
    clear_due: bool | None = Field(description="true để bỏ hạn")
    priority: Priority | None
    status: Literal["todo", "done"] | None = Field(description="done: đánh dấu xong; todo: mở lại")
    note: str | None


class ListTasksInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["todo", "done", "cancelled", "all"] | None = Field(
        description="null là việc còn làm (todo)"
    )
    due: Literal["overdue", "today", "week", "none"] | None = Field(
        description="Lọc hạn: quá hạn, hôm nay, 7 ngày tới, không hạn; null là mọi hạn"
    )
    limit: int | None = Field(description="Mặc định 20, tối đa 50")


class DeleteTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_ids: list[int] = Field(description="Mã việc cần xóa, 1 tới 50")
    reason: str = Field(description="Vì sao xóa, một câu ngắn")


def run_add_task(ctx: ToolContext, data: AddTaskInput) -> ToolOutput:
    if data.due_date and data.due_at:
        raise AiError("VALIDATION_ERROR", "Chọn một: hạn theo ngày (due_date) hoặc hạn có giờ (due_at).")
    payload = data.model_dump(exclude_none=True)
    t = service.create_task(ctx.session, ctx.user, payload, source="chat")
    return ToolOutput(
        result={**_brief(t, ctx.user.timezone), "da_len_lich": t.get("event_id") is not None},
        actions=[act.open_screen("Xem việc", "task_detail", {"task_id": t["id"]})],
    )


def run_update_task(ctx: ToolContext, data: UpdateTaskInput) -> ToolOutput:
    changes = {
        k: v
        for k, v in data.model_dump(include={"title", "note", "priority", "due_date", "due_at"}).items()
        if v is not None
    }
    if data.clear_due:
        changes.update(due_date=None, due_at=None)
    t = None
    if changes:
        t = service.update_task(ctx.session, ctx.user, data.task_id, changes)
    if data.status == "done":
        t = service.complete_task(ctx.session, ctx.user, data.task_id)
    elif data.status == "todo":
        t = service.reopen_task(ctx.session, ctx.user, data.task_id)
    if t is None:
        raise AiError("VALIDATION_ERROR", "Không có gì để sửa.")
    return ToolOutput(
        result=_brief(t, ctx.user.timezone),
        actions=[act.open_screen("Xem việc", "task_detail", {"task_id": t["id"]})],
    )


def run_list_tasks(ctx: ToolContext, data: ListTasksInput) -> ToolOutput:
    status = None if data.status == "all" else (data.status or "todo")
    limit = min(max(data.limit or 20, 1), 50)
    page = service.list_tasks(ctx.session, ctx.user, status=status, due=data.due, limit=limit)
    tz = ctx.user.timezone
    return ToolOutput(
        result={"items": [_brief(t, tz) for t in page["items"]], "con_nua": page["next_cursor"] is not None},
        actions=[act.open_screen("Mở danh sách việc", "task_list")],
    )


def _ids(data: DeleteTaskInput) -> list[int]:
    ids = list(dict.fromkeys(data.task_ids))
    if not 1 <= len(ids) <= MAX_DELETE:
        raise AiError("VALIDATION_ERROR", f"Xóa từ 1 tới {MAX_DELETE} việc mỗi lần.")
    return ids


def run_delete_one(ctx: ToolContext, data: DeleteTaskInput) -> ToolOutput:
    ids = _ids(data)
    t = service.get_task(ctx.session, ctx.user, ids[0])
    service.delete_task(ctx.session, ctx.user, ids[0])
    return ToolOutput(
        result={"da_xoa": ids, "ghi_chu": "Người dùng có nút Hoàn tác trong 10 phút."},
        actions=[
            act.undo(f"Đã xóa việc: {t['title']}", "task", ids, ctx.now + timedelta(minutes=UNDO_MINUTES))
        ],
    )


def prepare_delete(ctx: ToolContext, data: DeleteTaskInput) -> ApprovalDraft:
    ids = _ids(data)
    rows = [service.get_task(ctx.session, ctx.user, i) for i in ids]
    details = [{"label": f"Việc {i + 1}", "value": t["title"]} for i, t in enumerate(rows[:5])]
    if len(rows) > 5:
        details.append({"label": "Còn", "value": f"{len(rows) - 5} việc nữa"})
    return ApprovalDraft(
        title=f"Xóa {len(rows)} việc",
        summary=f"Lý do: {data.reason}",
        input={"task_ids": ids},
        details=details,
        danger=True,
    )


def execute_delete(ctx: ToolContext, tool_input: dict) -> ToolOutput:
    ids = list(tool_input["task_ids"])
    for task_id in ids:
        service.delete_task(ctx.session, ctx.user, task_id)
    return ToolOutput(result={"da_xoa": ids})


TOOLS = [
    ToolSpec(
        name="add_task",
        label="Đang thêm việc",
        description=(
            "Thêm việc cần làm. Có giờ cụ thể (họp, hẹn lúc mấy giờ) thì dùng add_event thay vì việc; "
            "việc có hạn giờ (nộp báo cáo trước 17:00) thì đặt due_at, tự lên lịch. Không bịa hạn khi "
            "người dùng không nói."
        ),
        input_model=AddTaskInput,
        run=run_add_task,
        phase=3,
    ),
    ToolSpec(
        name="update_task",
        label="Đang sửa việc",
        description="Sửa việc, dời hạn, đánh dấu xong hoặc mở lại. Lấy task_id từ list_tasks.",
        input_model=UpdateTaskInput,
        run=run_update_task,
        phase=3,
    ),
    ToolSpec(
        name="list_tasks",
        label="Đang xem việc",
        description="Liệt kê việc còn làm, việc hôm nay, việc quá hạn, việc tuần này; tìm task_id để sửa, xóa.",
        input_model=ListTasksInput,
        run=run_list_tasks,
        phase=3,
    ),
    ToolSpec(
        name="delete_task",
        label="Đang xóa việc",
        description=(
            "Xóa việc. Một việc: xóa ngay, có nút Hoàn tác. Từ 2 việc: chỉ tạo thẻ xác nhận, chưa xóa tới khi "
            "người dùng bấm Duyệt."
        ),
        input_model=DeleteTaskInput,
        run=run_delete_one,
        needs_approval=lambda data: len(set(data.task_ids)) >= 2,
        prepare=prepare_delete,
        execute=execute_delete,
        phase=3,
    ),
]
