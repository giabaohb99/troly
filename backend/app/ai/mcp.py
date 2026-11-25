"""Gắn kết nối MCP của người dùng vào lượt chat bằng MCP connector của Claude API (QĐ-53, QĐ-56).

Cách gọi theo tài liệu hiện hành (đọc 25/11/2026, platform.claude.com/docs/en/agents-and-tools/mcp-connector):
- `mcp_servers=[{type:"url", url, name, authorization_token}]` và mỗi máy chủ đúng một
  `{type:"mcp_toolset", mcp_server_name}` trong `tools`; beta `mcp-client-2026-09-15` (gồm cả 2025-11-20).
- Lọc công cụ bằng `default_config`/`configs` theo đúng tên (API không lọc theo tiền tố). Ở đây dùng chế độ
  danh sách cho phép: `default_config.enabled = false`, chỉ bật công cụ đọc lấy từ `tools/list` của kết nối, nên
  công cụ mới của máy chủ mặc định tắt.
- Bộ công cụ lớn: hoãn nạp mô tả (`defer_loading`) kèm `tool_search_tool_bm25_20251119` (Haiku 5.5 có).
- Máy chủ gọi công cụ phía Anthropic, kết quả nằm trong khối `mcp_tool_result` của câu trả lời, không qua vòng
  công cụ của app. Vì vậy công cụ ghi không bao giờ bật qua đường này (không qua được thẻ duyệt), kể cả khi người
  dùng đã bật công cụ ghi cho kết nối.

Nguồn: module kết nối của agent Google (`integrations.connectors.service`, sau cờ FEATURE_CONNECTORS).
"""

import logging
import re
import threading
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

MCP_BETA = "mcp-client-2026-09-15"
TOOL_SEARCH = {"type": "tool_search_tool_bm25_20251119", "name": "tool_search_tool_bm25"}

# Đoán công cụ ghi theo tên (máy chủ không ghi readOnlyHint thì chỉ còn cách này): một từ trong tên khớp.
WRITE_WORDS = frozenset(
    {
        "add",
        "approve",
        "archive",
        "assign",
        "book",
        "cancel",
        "close",
        "confirm",
        "create",
        "delete",
        "draft",
        "edit",
        "insert",
        "move",
        "pay",
        "post",
        "propose",
        "publish",
        "reject",
        "remove",
        "reply",
        "revoke",
        "save",
        "send",
        "set",
        "share",
        "submit",
        "update",
        "upload",
        "upsert",
        "write",
    }
)
# Tên trùng công cụ của app (API từ chối tên trùng) hoặc xuất tệp ở hệ thống kia (app xuất bằng export_document).
ALWAYS_OFF = frozenset(
    {"report_issue", "search_chat_history", "export_excel_file", "export_report_file", "export_report"}
)
# Công cụ ERP DEGO hay dùng, để sẵn khi bộ công cụ bị hoãn; đánh giá công việc cần số thật.
EAGER_TOOLS = (
    "my_work_tasks",
    "my_projects",
    "team_capacity",
    "my_approval_tasks",
    "my_requests_status",
    "my_leave_summary",
)
DEFER_OVER = 15  # quá số công cụ này thì hoãn nạp
TOOLS_CACHE_SECONDS = 600

_cache_lock = threading.Lock()
_tools_cache: dict[int, tuple[float, list[str]]] = {}


@dataclass(frozen=True)
class McpServer:
    connector_id: int
    label: str
    url: str
    token: str | None
    tools: tuple[str, ...]  # công cụ đọc được bật

    @property
    def name(self) -> str:
        return f"c{self.connector_id}"


def looks_write(name: str) -> bool:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)  # sendMessage -> send_Message
    words = set(re.split(r"[^a-z0-9]+", spaced.lower()))
    return bool(words & WRITE_WORDS)


def is_read_tool(tool: dict) -> bool:
    """Đọc khi tên không giống ghi và máy chủ không nói rõ là ghi (`read_only_hint` False)."""
    name = tool.get("name") or ""
    if not name or name in ALWAYS_OFF or looks_write(name):
        return False
    return tool.get("read_only_hint") is not False


def _feature_on() -> bool:
    from app.core.config import get_settings

    return bool(get_settings().feature_connectors)


def active_connectors(session, user_id: int) -> list[tuple[int, str]]:
    """(id, tên) của kết nối đang hoạt động, chỉ đọc DB; cờ tắt thì rỗng. Chat dùng để chọn kết nối cho lượt."""
    if not _feature_on():
        return []
    try:
        from app.integrations.connectors import service as connectors
    except ImportError:  # pragma: no cover
        return []
    try:
        return [
            (c["id"], c["name"])
            for c in connectors.list_connectors(session, user_id)
            if c["status"] == "connected"
        ]
    except Exception:
        log.exception("Đọc kết nối lỗi")
        return []


def _read_tools(session, user_id: int, connector_id: int) -> list[str]:
    now = time.monotonic()
    with _cache_lock:
        hit = _tools_cache.get(connector_id)
        if hit and now - hit[0] < TOOLS_CACHE_SECONDS:
            return hit[1]
    from app.integrations.connectors import service as connectors

    names = sorted(
        t["name"] for t in connectors.list_tools(session, user_id, connector_id) if is_read_tool(t)
    )
    with _cache_lock:
        _tools_cache[connector_id] = (now, names)
    return names


def clear_cache() -> None:
    with _cache_lock:
        _tools_cache.clear()


def connected_servers(session, user_id: int, connector_ids: tuple[int, ...]) -> list[McpServer]:
    """Máy chủ gắn được cho lượt: token từ get_access_token, công cụ đọc từ tools/list (đệm 10 phút). Kết nối
    lỗi, cần nối lại, không có công cụ đọc nào thì bỏ. Không ném lỗi."""
    if not connector_ids or not _feature_on():
        return []
    from app.integrations.connectors import service as connectors

    rows = {c["id"]: c for c in connectors.list_connectors(session, user_id)}
    out = []
    for cid in connector_ids:
        c = rows.get(cid)
        if c is None or c["status"] != "connected":
            continue
        try:
            token = connectors.get_access_token(session, user_id, cid)
            tools = _read_tools(session, user_id, cid)
        except Exception as exc:  # cần nối lại, máy chủ không trả lời
            log.warning("Bỏ kết nối %s khỏi lượt: %s", cid, type(exc).__name__)
            continue
        if tools:
            out.append(McpServer(cid, c["name"], c["url"], token, tuple(tools)))
    return out


def build_mcp_servers(servers: list[McpServer]) -> list[dict]:
    out = []
    for s in servers:
        entry = {"type": "url", "url": s.url, "name": s.name}
        if s.token:
            entry["authorization_token"] = s.token
        out.append(entry)
    return out


def build_toolsets(servers: list[McpServer]) -> list[dict]:
    """Một mcp_toolset mỗi máy chủ, chế độ cho phép: tắt mặc định, bật từng công cụ đọc. Bộ lớn thì hoãn nạp
    trừ vài công cụ hay dùng, và thêm công cụ tìm (không hoãn) vào đầu."""
    toolsets, deferred = [], False
    for s in servers:
        big = len(s.tools) > DEFER_OVER
        deferred = deferred or big
        configs = {}
        for name in s.tools:
            if big and name not in EAGER_TOOLS:
                configs[name] = {"enabled": True, "defer_loading": True}
            else:
                configs[name] = {"enabled": True}
        toolsets.append(
            {
                "type": "mcp_toolset",
                "mcp_server_name": s.name,
                "default_config": {"enabled": False},
                "configs": configs,
            }
        )
    return ([dict(TOOL_SEARCH)] if deferred else []) + toolsets


def strip_mcp_blocks(messages: list[dict], keep: set[str]) -> list[dict]:
    """Bỏ khối MCP của máy chủ không gắn ở lượt này (API không nhận khối của máy chủ không có trong
    mcp_servers). Tin assistant chỉ còn rỗng thì giữ một dấu chấm để không lệch vai."""
    out = []
    for msg in messages:
        content = msg.get("content")
        if msg.get("role") != "assistant" or not isinstance(content, list):
            out.append(msg)
            continue
        dropped = {
            b.get("id")
            for b in content
            if b.get("type") == "mcp_tool_use" and b.get("server_name") not in keep
        }
        kept = [
            b
            for b in content
            if not (
                (b.get("type") == "mcp_tool_use" and b.get("id") in dropped)
                or (b.get("type") == "mcp_tool_result" and b.get("tool_use_id") in dropped)
                or (b.get("type") == "mcp_tool_listing" and b.get("mcp_server_name") not in keep)
            )
        ]
        if len(kept) == len(content):
            out.append(msg)
        else:
            out.append({**msg, "content": kept or [{"type": "text", "text": "."}]})
    return out


def has_mcp_results(content: list[dict]) -> bool:
    return any(b.get("type") == "mcp_tool_result" for b in content)


def inspect_response(content: list[dict], servers: list[McpServer]) -> None:
    """Báo động nếu model gọi được công cụ không nằm trong danh sách cho phép (không được xảy ra)."""
    allowed = {s.name: set(s.tools) for s in servers}
    for block in content:
        if block.get("type") == "mcp_tool_use":
            server, name = block.get("server_name"), block.get("name")
            if name not in allowed.get(server, set()):
                log.error("Model đã gọi công cụ MCP ngoài danh sách cho phép: %s/%s", server, name)
