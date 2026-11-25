"""Khách MCP tối thiểu qua Streamable HTTP: initialize rồi tools/list (để app hiện danh sách công cụ).

Phần gọi công cụ trong lượt chat do agent AI làm (gắn kết nối vào lượt chat); ở đây chỉ dò máy chủ và đọc
danh sách công cụ.
"""

import json

import httpx

from app.integrations.connectors import net

PROTOCOL_VERSION = "2025-06-18"


def _headers(token: str | None, session_id: str | None = None) -> dict:
    h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
         "MCP-Protocol-Version": PROTOCOL_VERSION}  # fmt: skip
    if token:
        h["Authorization"] = f"Bearer {token}"
    if session_id:
        h["Mcp-Session-Id"] = session_id
    return h


def _rpc_result(r: httpx.Response, rpc_id: int) -> dict:
    """Phản hồi JSON thường hoặc SSE (data: {...}); lấy đúng thông điệp có id."""
    ctype = r.headers.get("content-type", "")
    messages = []
    if "text/event-stream" in ctype:
        for line in r.text.splitlines():
            if line.startswith("data:"):
                try:
                    messages.append(json.loads(line[5:].strip()))
                except ValueError:
                    continue
    else:
        data = r.json()
        messages = data if isinstance(data, list) else [data]
    for m in messages:
        if m.get("id") == rpc_id:
            if "error" in m:
                raise net.ConnectorUnavailable(
                    f"Máy chủ MCP báo lỗi: {str(m['error'].get('message', ''))[:200]}"
                )
            return m.get("result") or {}
    raise net.ConnectorUnavailable("Máy chủ không trả lời đúng giao thức MCP.")


def initialize(url: str, token: str | None) -> tuple[httpx.Response, str | None]:
    """Gửi initialize. Trả (phản hồi thô, Mcp-Session-Id). Nơi gọi xem status: 200 là MCP, 401 là cần xác thực."""
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "troly", "version": "1.1"},
        },
    }
    r = net.send("POST", url, headers=_headers(token), json=body)
    return r, r.headers.get("mcp-session-id")


def list_tools(url: str, token: str | None) -> list[dict]:
    """[{name, description, write}] theo annotations: readOnlyHint true là đọc, còn lại coi là ghi."""
    r, session_id = initialize(url, token)
    if r.status_code != 200:
        raise net.ConnectorUnavailable(f"Máy chủ MCP trả {r.status_code}.")
    _rpc_result(r, 1)
    net.send("POST", url, headers=_headers(token, session_id),
             json={"jsonrpc": "2.0", "method": "notifications/initialized"})  # fmt: skip
    tools, cursor, rpc_id = [], None, 2
    for _ in range(10):  # tối đa 10 trang
        params = {"cursor": cursor} if cursor else {}
        r = net.send("POST", url, headers=_headers(token, session_id),
                     json={"jsonrpc": "2.0", "id": rpc_id, "method": "tools/list", "params": params})  # fmt: skip
        result = _rpc_result(r, rpc_id)
        for t in result.get("tools") or []:
            notes = t.get("annotations") or {}
            tools.append(
                {
                    "name": t.get("name"),
                    "title": notes.get("title") or t.get("title"),
                    "description": (t.get("description") or "")[:500],
                    # MCP: thiếu readOnlyHint nghĩa là mặc định false (có thể ghi). Trả cả giá trị thô để nơi
                    # gọi tự quyết với máy chủ không ghi gợi ý.
                    "read_only_hint": notes.get("readOnlyHint")
                    if isinstance(notes.get("readOnlyHint"), bool)
                    else None,
                    "write": not bool(notes.get("readOnlyHint")),
                }
            )
        cursor = result.get("nextCursor")
        rpc_id += 1
        if not cursor:
            break
    return tools


def call_tool(url: str, token: str | None, name: str, arguments: dict | None) -> dict:
    """tools/call qua Streamable HTTP; trả `{content, is_error}` (content là danh sách khối của máy chủ)."""
    r, session_id = initialize(url, token)
    if r.status_code != 200:
        raise net.ConnectorUnavailable(f"Máy chủ MCP trả {r.status_code}.")
    _rpc_result(r, 1)
    net.send("POST", url, headers=_headers(token, session_id),
             json={"jsonrpc": "2.0", "method": "notifications/initialized"})  # fmt: skip
    r = net.send(
        "POST",
        url,
        headers=_headers(token, session_id),
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },  # fmt: skip
    )
    if r.status_code != 200:
        raise net.ConnectorUnavailable(f"Máy chủ MCP trả {r.status_code}.")
    result = _rpc_result(r, 2)
    return {"content": result.get("content") or [], "is_error": bool(result.get("isError"))}
