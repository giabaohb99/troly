"""Công cụ AI của Kết nối (QĐ-56, agent AI): bot giúp thêm kết nối, cho biết đang nối gì, và gọi công cụ ghi
người dùng đã bật qua thẻ duyệt (`call_connector_tool`; công cụ đọc đi thẳng qua MCP connector, xem ai/mcp.py).

Dùng service công khai của agent Google (`integrations.connectors.service`). Mật khẩu, mã đăng nhập chỉ nhập trên
trang của hệ thống đó (nút `connect`), không bao giờ qua chat. Nạp sau cờ FEATURE_CONNECTORS.
"""

import json
import re

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.router import normalize
from app.ai.schemas import AiError, ApprovalDraft, ToolContext, ToolOutput, ToolSpec
from app.integrations.connectors import service

NEXT_NOTE = {
    "oauth": "Đã thêm; người dùng bấm nút để đăng nhập và đồng ý trên trang của hệ thống đó.",
    "api_key": "Đã thêm; hệ thống này cần khóa, người dùng bấm nút để dán khóa trong màn Kết nối, không dán vào chat.",
    "ready": "Đã nối xong, hệ thống không cần đăng nhập.",
}


class ConnectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(description="Tên hệ thống người dùng gọi: ERP DEGO, Jira công ty")
    url: str | None = Field(
        default=None, description="Địa chỉ máy chủ MCP https nếu người dùng đưa; không đoán"
    )


class ListConnectionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CallToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connector_id: int = Field(description="connector_id lấy từ list_connections")
    tool: str = Field(description="Tên công cụ ghi đã bật (cong_cu_ghi_da_bat trong list_connections)")
    arguments_json: str = Field(description='Đối số dạng JSON object, ví dụ {"title": "...", "days": 2}')
    reason: str = Field(description="Một câu: việc này làm gì, theo lời người dùng")


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", normalize(text)) if w}


def _preset_url(name: str) -> str | None:
    """Gợi ý sẵn theo tên: *ERP*, *ERP DEGO* ra bản chính; có *thử nghiệm*, *dev* thì ra bản thử nghiệm."""
    wanted = _words(name)
    test = bool(wanted & {"thu", "nghiem", "dev", "test"})
    core = wanted - {"thu", "nghiem", "dev", "test"}
    if not core:
        return None
    hits = [p for p in service.presets() if core <= _words(p["name"])]
    pick = [p for p in hits if ("nghiem" in _words(p["name"])) == test]
    return pick[0]["url"] if pick else None


def _same_url(a: str, b: str) -> bool:
    return a.rstrip("/").lower() == b.rstrip("/").lower()


def run_connect(ctx: ToolContext, data: ConnectInput) -> ToolOutput:
    name = " ".join(data.name.split())[:100]
    url = (data.url or "").strip() or _preset_url(name)
    if not url:
        return ToolOutput(
            result={
                "trang_thai": "can_dia_chi",
                "ghi_chu": "Chưa biết địa chỉ máy chủ; nút mở form để người dùng điền.",
            },
            actions=[act.connect(f"Thêm kết nối {name}", name=name)],
        )
    for c in service.list_connectors(ctx.session, ctx.user.user_id):
        if _same_url(c["url"], url):
            if c["status"] == "connected":
                return ToolOutput(result={"trang_thai": "da_noi", "connector_id": c["id"], "ten": c["name"]})
            return ToolOutput(
                result={
                    "trang_thai": "can_dang_nhap",
                    "connector_id": c["id"],
                    "ghi_chu": NEXT_NOTE["oauth"],
                },
                actions=[act.connect(f"Kết nối {c['name']}", connector_id=c["id"])],
            )
    out = service.create(ctx.session, ctx.user.user_id, name, url)  # dò máy chủ; URL sai thì lỗi có code
    c, step = out["connector"], out["next"]
    actions = [] if step == "ready" else [act.connect(f"Kết nối {c['name']}", connector_id=c["id"])]
    return ToolOutput(
        result={
            "trang_thai": "da_them",
            "connector_id": c["id"],
            "ten": c["name"],
            "ghi_chu": NEXT_NOTE[step],
        },
        actions=actions,
    )


def run_list_connections(ctx: ToolContext, data: ListConnectionsInput) -> ToolOutput:
    items = [
        {
            "connector_id": c["id"],
            "ten": c["name"],
            "trang_thai": c["status"],  # connected, not_connected, reauth_required, error
            "tai_khoan": c.get("account"),
            "so_cong_cu": c.get("tools_count"),
            "cong_cu_ghi_da_bat": c.get("write_tools_enabled") or [],
        }
        for c in service.list_connectors(ctx.session, ctx.user.user_id)
    ]
    actions = [
        act.connect(f"Kết nối lại {i['ten']}", connector_id=i["connector_id"])
        for i in items
        if i["trang_thai"] in ("reauth_required", "not_connected")
    ][:3]
    note = "Chưa có kết nối nào." if not items else "Công cụ của kết nối chỉ đọc trong chat."
    return ToolOutput(result={"items": items, "ghi_chu": note}, actions=actions)


ARGS_MAX = 4000


def _connector(ctx: ToolContext, connector_id: int) -> dict:
    c = next(
        (c for c in service.list_connectors(ctx.session, ctx.user.user_id) if c["id"] == connector_id), None
    )
    if c is None:
        raise AiError("NOT_FOUND", "Không có kết nối này.")
    if c["status"] != "connected":
        raise AiError("CONFLICT", "Kết nối chưa sẵn sàng; người dùng cần nối lại trong Cài đặt, Kết nối.")
    return c


def prepare_call_tool(ctx: ToolContext, data: CallToolInput) -> ApprovalDraft:
    c = _connector(ctx, data.connector_id)
    if not service.tool_allowed(c, data.tool, write=True):
        raise AiError(
            "VALIDATION_ERROR",
            "Công cụ ghi này chưa được bật; người dùng bật trong Cài đặt, Kết nối nếu muốn.",
        )
    try:
        args = json.loads(data.arguments_json or "{}")
    except ValueError as exc:
        raise AiError("VALIDATION_ERROR", "arguments_json không phải JSON hợp lệ.") from exc
    if not isinstance(args, dict) or len(data.arguments_json) > ARGS_MAX:
        raise AiError("VALIDATION_ERROR", "arguments_json phải là một object JSON ngắn.")
    shown = json.dumps(args, ensure_ascii=False)
    return ApprovalDraft(
        title=f"{c['name']}: {data.tool}"[:120],
        summary=data.reason.strip()[:300] or f"Chạy {data.tool} trên {c['name']}.",
        input={"connector_id": c["id"], "tool": data.tool, "arguments": args},
        details=[
            {"label": "Hệ thống", "value": c["name"]},
            {"label": "Công cụ", "value": data.tool},
            {"label": "Dữ liệu gửi", "value": shown[:500] + ("..." if len(shown) > 500 else "")},
        ],
        danger=True,  # ghi vào hệ thống ngoài, không hoàn tác được từ app
    )


def execute_call_tool(ctx: ToolContext, tool_input: dict) -> ToolOutput:
    """Chạy sau khi người dùng bấm Duyệt (chat gọi). Kết quả là dữ liệu của hệ thống ngoài."""
    out = service.call_tool(
        ctx.session, ctx.user.user_id, tool_input["connector_id"], tool_input["tool"], tool_input["arguments"]
    )
    texts = [
        b.get("text", "") for b in out.get("content") or [] if isinstance(b, dict) and b.get("type") == "text"
    ]
    return ToolOutput(
        result={"loi": bool(out.get("is_error")), "du_lieu_ngoai": "\n".join(texts)[:2000]},
        contains_third_party=True,
    )


TOOLS = [
    ToolSpec(
        name="connect_service",
        label="Đang thêm kết nối",
        description=(
            "Người dùng nói kết nối, nối, liên kết với một hệ thống (ERP DEGO...) thì gọi công cụ này: thêm kết nối "
            "và trả nút mở trang đăng nhập của hệ thống đó. Không bao giờ xin mật khẩu, mã đăng nhập trong chat; "
            "người dùng nhập trên trang của hệ thống."
        ),
        input_model=ConnectInput,
        run=run_connect,
        phase=5,
    ),
    ToolSpec(
        name="list_connections",
        label="Đang xem kết nối",
        description="Liệt kê kết nối hệ thống ngoài của người dùng và trạng thái (đã nối, cần nối lại).",
        input_model=ListConnectionsInput,
        run=run_list_connections,
        phase=5,
    ),
    ToolSpec(
        name="call_connector_tool",
        label="Đang soạn việc cho hệ thống ngoài",
        description=(
            "Chạy một công cụ ghi người dùng đã bật trên kết nối (tạo phiếu, đơn nghỉ phép...): luôn tạo thẻ duyệt, "
            "chỉ chạy khi người dùng bấm Duyệt. Chỉ dùng khi người dùng nhờ làm việc đó; công cụ phải nằm trong "
            "cong_cu_ghi_da_bat của list_connections. Tra cứu thì dùng công cụ đọc của kết nối, không dùng công cụ này."
        ),
        input_model=CallToolInput,
        needs_approval=lambda data: True,
        prepare=prepare_call_tool,
        execute=execute_call_tool,
        phase=5,
    ),
]
