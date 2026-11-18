"""Công cụ AI của module file (20 mục 3.7): list_files, get_file_link, export_document, save_file_to_drive,
share_drive_file.

Chia sẻ Drive là việc gửi ra ngoài nên luôn qua thẻ duyệt (QĐ-38); lưu vào Drive của chính người dùng thì không.
Duyệt xong, chat chạy `file/approvals.py` (agent kiến trúc) với đúng `input` của thẻ, không qua `execute` ở đây.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import AiError, ApprovalDraft, ToolContext, ToolOutput, ToolSpec
from app.core.errors import AppError, ValidationError
from app.modules.file import service

Purpose = Literal["chat_attachment", "voice", "trip_source", "trip_export", "report_export", "other"]


class ListFilesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: Purpose | None = Field(description="Loại tệp; null là mọi loại")
    limit: int | None = Field(description="Số tệp tối đa, mặc định 10, tối đa 50")


class FileLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: int = Field(description="Mã tệp lấy từ list_files hoặc search_everything")


class ShareDriveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: int = Field(description="Mã tệp lấy từ list_files hoặc search_everything")
    email: str = Field(description="Email người nhận, do người dùng nói; không đoán")
    role: Literal["reader", "commenter", "writer"] = Field(
        default="reader", description="reader: chỉ xem (mặc định); commenter: được nhận xét; writer: được sửa"
    )
    message: str | None = Field(default=None, description="Lời nhắn kèm thư báo của Google; null là không có")


class DocBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["heading", "paragraph", "bullets", "table"]
    text: str | None = Field(default=None, description="heading, paragraph: nội dung")
    level: int | None = Field(default=None, description="heading: cấp 1 tới 3")
    items: list[str] | None = Field(default=None, description="bullets: các dòng")
    title: str | None = Field(default=None, description="table: tên bảng (thành tên trang tính Excel)")
    header: list[str] | None = Field(default=None, description="table: tên cột")
    rows: list[list[str | float | int | None]] | None = Field(
        default=None, description="table: các dòng, đủ số cột như header; số để kiểu số"
    )


class ExportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["pdf", "docx", "xlsx"] = Field(
        default="pdf",
        description="pdf mặc định; xlsx khi chủ yếu là bảng số; docx khi người dùng muốn sửa tiếp",
    )
    title: str = Field(description="Tiêu đề tài liệu, cũng là tên tệp")
    blocks: list[DocBlock] = Field(description="Nội dung theo thứ tự: heading, paragraph, bullets, table")


ROLE_TEXT = {"reader": "Chỉ xem", "commenter": "Được nhận xét", "writer": "Được sửa"}
NOT_CONNECTED = "GOOGLE_NOT_CONNECTED"


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


def run_export_document(ctx: ToolContext, data: ExportInput) -> ToolOutput:
    blocks = [b.model_dump(exclude_none=True) for b in data.blocks]
    if not blocks:
        raise AiError("VALIDATION_ERROR", "Tài liệu chưa có nội dung.")
    try:
        out = service.save_generated_file(ctx.session, ctx.user, data.format, data.title.strip(), blocks)
    except ValidationError as exc:  # render.validate: nói rõ chỗ sai để model sửa và gọi lại
        detail = "; ".join((exc.fields or {}).values()) or exc.message
        raise AiError("VALIDATION_ERROR", detail) from exc
    card = act.file_card(out)
    return ToolOutput(result=dict(out), actions=[card])


def _not_connected() -> ToolOutput:
    return ToolOutput(
        result={
            "trang_thai": "chua_noi_google",
            "ghi_chu": "Chưa nối Google Drive; nhờ người dùng nối trong Cài đặt.",
        },
        actions=[act.open_screen("Nối Google", "settings_google")],
    )


def run_save_file_to_drive(ctx: ToolContext, data: FileLinkInput) -> ToolOutput:
    f = service.get_file(ctx.session, ctx.user.user_id, data.file_id)
    try:
        service.request_drive_upload(ctx.session, ctx.user.user_id, data.file_id)
    except AppError as exc:
        if getattr(exc, "code", None) == NOT_CONNECTED:
            return _not_connected()
        raise
    return ToolOutput(
        result={"file_id": f["id"], "name": f["original_name"], "trang_thai": "dang_luu_len_drive"},
    )


def _clean_email(value: str) -> str:
    email = value.strip()
    local, _, domain = email.partition("@")
    if not local or "." not in domain or " " in email:
        raise AiError("VALIDATION_ERROR", "Email người nhận chưa đúng.")
    return email


def prepare_share(ctx: ToolContext, data: ShareDriveInput) -> ApprovalDraft:
    f = service.get_file(ctx.session, ctx.user.user_id, data.file_id)
    name = f["original_name"] or "tệp"
    email = _clean_email(data.email)
    message = (data.message or "").strip()[:500] or None
    details = [
        {"label": "Tệp", "value": name},
        {"label": "Người nhận", "value": email},
        {"label": "Quyền", "value": ROLE_TEXT[data.role]},
    ]
    if message:
        details.append({"label": "Lời nhắn", "value": message})
    return ApprovalDraft(
        title="Chia sẻ tệp trên Google Drive",
        summary=f"Chia sẻ {name} cho {email}, quyền {ROLE_TEXT[data.role].lower()}. Google sẽ gửi thư báo.",
        input={"file_id": f["id"], "email": email, "role": data.role, "message": message},
        details=details,
        danger=False,
    )


def execute_share(ctx: ToolContext, tool_input: dict) -> ToolOutput:
    """Chat chạy thẳng `file/approvals.py`; hàm này chỉ để registry đủ cặp prepare, execute và cùng đường chạy."""
    from app.modules.file import approvals

    return ToolOutput(result=approvals.share_drive_file(ctx.session, ctx.user, tool_input))


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
    ToolSpec(
        name="export_document",
        label="Đang xuất tệp",
        description=(
            "Tạo tệp PDF, Word hoặc Excel từ nội dung đã có, trả thẻ tệp trong tin. Lấy số liệu trước bằng công "
            "cụ đọc (get_report, query_expenses, list_events, get_trip...), không bịa số. pdf mặc định; xlsx khi "
            "chủ yếu là bảng số; docx khi người dùng muốn sửa tiếp. Không chép link tệp ra chữ."
        ),
        input_model=ExportInput,
        run=run_export_document,
        phase=4,
    ),
    ToolSpec(
        name="save_file_to_drive",
        label="Đang lưu lên Drive",
        description=(
            "Lưu một tệp vào thư mục Trợ lý trên Google Drive của chính người dùng (chạy nền, không cần duyệt). "
            "Chưa nối Google thì trả nút mở Cài đặt."
        ),
        input_model=FileLinkInput,
        run=run_save_file_to_drive,
        phase=5,
    ),
    ToolSpec(
        name="share_drive_file",
        label="Đang soạn chia sẻ Drive",
        description=(
            "Chia sẻ một tệp trên Google Drive cho người khác (tự lưu lên Drive trước nếu chưa có). Luôn tạo thẻ "
            "duyệt; chỉ chia sẻ khi người dùng bấm Duyệt, không nói là đã chia sẻ trước đó. Email phải do người "
            "dùng nói; chưa có email thì hỏi. Hỏi lại nếu chưa rõ quyền xem hay sửa."
        ),
        input_model=ShareDriveInput,
        run=None,
        needs_approval=lambda data: True,
        prepare=prepare_share,
        execute=execute_share,
        phase=5,
    ),
]
