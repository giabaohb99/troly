"""Công cụ AI của module file: list_files, get_file_link (20 mục 3.7)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import ToolContext, ToolOutput, ToolSpec
from app.modules.file import service

Purpose = Literal["chat_attachment", "voice", "trip_source", "trip_export", "report_export", "other"]


class ListFilesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: Purpose | None = Field(description="Loại tệp; null là mọi loại")
    limit: int | None = Field(description="Số tệp tối đa, mặc định 10, tối đa 50")


class FileLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: int = Field(description="Mã tệp lấy từ list_files hoặc search_everything")


def run_list_files(ctx: ToolContext, data: ListFilesInput) -> ToolOutput:
    limit = min(max(data.limit or 10, 1), 50)
    page = service.list_files(ctx.session, ctx.user.user_id, data.purpose, None, limit)
    items = [
        {
            "file_id": f["id"],
            "name": f["original_name"],
            "mime": f["mime"],
            "purpose": f["purpose"],
            "created_at": f["created_at"],
        }
        for f in page["items"]
    ]
    return ToolOutput(result={"items": items, "con_nua": page["next_cursor"] is not None})


def run_get_file_link(ctx: ToolContext, data: FileLinkInput) -> ToolOutput:
    f = service.get_file(ctx.session, ctx.user.user_id, data.file_id)
    url = f.get("download_url")
    if not url:
        return ToolOutput(result={"file_id": f["id"], "ghi_chu": "Tệp chưa sẵn sàng để mở."})
    name = f["original_name"] or "tệp"
    return ToolOutput(
        result={"file_id": f["id"], "name": name},
        actions=[act.open_link(f"Mở {name}", url, "file")],
    )


TOOLS = [
    ToolSpec(
        name="list_files",
        label="Đang tìm tệp",
        description=(
            "Liệt kê tệp người dùng đã gửi hoặc đã xuất, mới nhất trước. Tìm theo nội dung trong tệp thì "
            "dùng search_everything."
        ),
        input_model=ListFilesInput,
        run=run_list_files,
    ),
    ToolSpec(
        name="get_file_link",
        label="Đang lấy link tệp",
        description="Tạo nút mở một tệp khi người dùng muốn xem hoặc gửi tệp. Không chép link ra chữ.",
        input_model=FileLinkInput,
        run=run_get_file_link,
    ),
]
