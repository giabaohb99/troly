"""FakeClaude: thay SDK `anthropic` trong bài kiểm (70 mục 3.7). Không gọi mạng.

Mỗi phần tử kịch bản là dict mô tả một phản hồi, hoặc một Exception để ném ra:
    {"content": [khối dict], "stop_reason": "end_turn", "usage": {...}, "model": "...",
     "stop_details": {...}, "parsed_output": obj}
Khối dict dùng đúng hình dạng của API (`text`, `thinking`, `tool_use`, `server_tool_use`,
`web_search_tool_result`, `fallback`...). Yêu cầu đã gửi được ghi lại ở `requests` để soi lời nhắc.
"""

import copy
from dataclasses import dataclass, field
from typing import Any

from app.ai.registry import MAX_OPTIONAL_PARAMS, MAX_STRICT_TOOLS, MAX_UNION_PARAMS, count_complexity
from app.ai.schemas import AiRequestError

# Mã nước web search đã biết là nhận; "VN" bị API từ chối (lỗi thật 18/11/2026). Chỉ thêm mã đã thử được.
SUPPORTED_SEARCH_COUNTRIES = {"US"}


def _blocks(content) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return list(content or [])


def validate_request(kwargs: dict) -> str | None:
    """Kiểm các luật của Messages API mà bài kiểm hay vấp; trả câu lỗi giống API, hoặc None."""
    messages = kwargs.get("messages") or []
    if not messages or messages[0].get("role") != "user":
        return "messages.0: first message must use the user role"
    for i, msg in enumerate(messages):
        role = msg.get("role")
        if role == "system":
            prev = messages[i - 1] if i else None
            prev_ok = prev is not None and (
                prev.get("role") == "user"
                or (
                    prev.get("role") == "assistant"
                    and _blocks(prev["content"])[-1:]
                    and _blocks(prev["content"])[-1].get("type") == "server_tool_use"
                )
            )
            nxt = messages[i + 1] if i + 1 < len(messages) else None
            if not prev_ok or (nxt is not None and nxt.get("role") != "assistant"):
                return f"messages.{i}: role 'system' must precede an 'assistant' message or end the array"
            continue
        for block in _blocks(msg.get("content")):
            if block.get("type") == "text" and not block.get("text"):
                return f"messages.{i}: text content blocks must be non-empty"
            # Khối giữ chỗ nội bộ (troly_file) lọt ra API là 400 thật (gặp khi đọc lịch trình từ ảnh).
            if block.get("type") == "troly_file":
                return f"messages.{i}.content: Input tag 'troly_file' found using 'type' does not match"
        if role == "assistant":
            uses = [b["id"] for b in _blocks(msg["content"]) if b.get("type") == "tool_use"]
            if uses and i + 1 < len(messages):
                nxt = messages[i + 1]
                got = [
                    b.get("tool_use_id")
                    for b in _blocks(nxt.get("content"))
                    if b.get("type") == "tool_result"
                ]
                if nxt.get("role") != "user" or sorted(got) != sorted(uses):
                    return f"messages.{i + 1}: tool_use ids were found without tool_result blocks"
        if role == "user":
            results = [
                b.get("tool_use_id") for b in _blocks(msg.get("content")) if b.get("type") == "tool_result"
            ]
            if results:
                prev = messages[i - 1] if i else {}
                uses = [b.get("id") for b in _blocks(prev.get("content")) if b.get("type") == "tool_use"]
                if prev.get("role") != "assistant" or not set(results) <= set(uses):
                    return f"messages.{i}: unexpected tool_use_id found in tool_result blocks"
    last = messages[-1]
    if last.get("role") == "assistant":
        tail = _blocks(last["content"])[-1:]
        if not tail or tail[0].get("type") != "server_tool_use":
            return "This model does not support assistant message prefill"
    tools = kwargs.get("tools") or []
    for tool in tools:
        loc = tool.get("user_location")
        if loc is not None:
            if loc.get("type") != "approximate" or not any(
                loc.get(k) for k in ("city", "region", "country", "timezone")
            ):
                return (
                    "tools: user_location needs type approximate and one of city, region, country, timezone"
                )
            if loc.get("country") and loc["country"] not in SUPPORTED_SEARCH_COUNTRIES:
                return f"Country code {loc['country']} is not supported"
    strict = [t for t in tools if t.get("strict")]
    optional = union = 0
    for tool in strict:
        o, u = count_complexity(tool.get("input_schema") or {})
        optional, union = optional + o, union + u
    if len(strict) > MAX_STRICT_TOOLS:
        return "Too many strict tools"
    if union > MAX_UNION_PARAMS:
        return f"Schemas contains too many parameters with union types ({union} parameters)"
    if optional > MAX_OPTIONAL_PARAMS:
        return f"Schemas contains too many optional parameters ({optional} parameters)"
    web = any(
        str(t.get("type", "")).startswith(("web_search", "web_fetch")) for t in kwargs.get("tools") or []
    )
    if web and (kwargs.get("output_format") or (kwargs.get("output_config") or {}).get("format")):
        return "Citations are not supported when structured output is enabled"
    return None


DEFAULT_USAGE = {
    "input_tokens": 100,
    "output_tokens": 20,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
    "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
    "server_tool_use": {"web_search_requests": 0},
}


@dataclass
class FakeMessage:
    content: list[dict]
    stop_reason: str = "end_turn"
    model: str = "claude-haiku-5-5"
    usage: dict = field(default_factory=lambda: copy.deepcopy(DEFAULT_USAGE))
    stop_details: dict | None = None
    parsed_output: Any = None
    _request_id: str = "req_fake"


class _Stream:
    def __init__(self, message: FakeMessage):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        for block in self._message.content:
            if block.get("type") == "text" and block.get("text"):
                text = block["text"]
                mid = max(1, len(text) // 2)
                yield text[:mid]
                if text[mid:]:
                    yield text[mid:]

    def get_final_message(self) -> FakeMessage:
        return self._message


class _Messages:
    def __init__(self, owner: "FakeClaude", beta: bool):
        self._owner = owner
        self._beta = beta

    def _next(self, kwargs: dict) -> FakeMessage:
        self._owner.requests.append({"beta": self._beta, **copy.deepcopy(kwargs)})
        problem = validate_request(kwargs)
        if problem:
            raise AiRequestError("AI_UNAVAILABLE", problem)
        if not self._owner.script:
            raise AssertionError("FakeClaude hết kịch bản")
        item = self._owner.script.pop(0)
        if isinstance(item, Exception):
            raise item
        data = copy.deepcopy(item)
        usage = copy.deepcopy(DEFAULT_USAGE)
        usage.update(data.pop("usage", {}))
        data.setdefault("model", kwargs.get("model", "claude-haiku-5-5"))
        return FakeMessage(usage=usage, **data)

    def stream(self, **kwargs) -> _Stream:
        return _Stream(self._next(kwargs))

    def create(self, **kwargs) -> FakeMessage:
        return self._next(kwargs)

    def parse(self, **kwargs) -> FakeMessage:
        kwargs = {**kwargs, "output_format": getattr(kwargs.get("output_format"), "__name__", None)}
        return self._next(kwargs)


class _Beta:
    def __init__(self, owner: "FakeClaude"):
        self.messages = _Messages(owner, beta=True)


class FakeClaude:
    def __init__(self, script: list | None = None):
        self.script: list = list(script or [])
        self.requests: list[dict] = []
        self.messages = _Messages(self, beta=False)
        self.beta = _Beta(self)
        self.timeouts: list[float] = []

    def with_options(self, *, timeout: float | None = None, **_):
        self.timeouts.append(timeout)
        return self


def text_reply(text: str, **kw) -> dict:
    return {
        "content": [{"type": "thinking", "thinking": "", "signature": "sig"}, {"type": "text", "text": text}],
        **kw,
    }


def tool_call(name: str, tool_input: dict, tool_id: str = "toolu_1", **kw) -> dict:
    return {
        "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}],
        "stop_reason": "tool_use",
        **kw,
    }
