"""Gom công cụ AI. `app/main.py` gọi `register_tools(<module>.tools.TOOLS)`; `ai/` không import module."""

import copy
import json

from app.ai.schemas import AiError, ToolContext, ToolOutput, ToolSpec

_TOOLS: dict[str, ToolSpec] = {}

# Từ khóa JSON Schema mà strict tool use không nhận; SDK Python bỏ khi dùng parse, ta tự bỏ ở đây.
_UNSUPPORTED_KEYS = {
    "title",
    "default",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
    "uniqueItems",
    "examples",
}


def register_tools(tools: list[ToolSpec]) -> None:
    for spec in tools:
        if spec.name in _TOOLS and _TOOLS[spec.name] is not spec:
            raise ValueError(f"Trùng tên công cụ: {spec.name}")
        has_run = spec.run is not None
        has_approval = spec.prepare is not None and spec.execute is not None
        if not has_run and not has_approval:
            raise ValueError(f"Công cụ {spec.name} thiếu hàm chạy")
        if spec.needs_approval is not None and not has_approval:
            raise ValueError(f"Công cụ {spec.name} có duyệt nhưng thiếu prepare hoặc execute")
        _TOOLS[spec.name] = spec


def clear_tools() -> None:
    """Chỉ dùng trong bài kiểm."""
    _TOOLS.clear()


def get_tool(name: str) -> ToolSpec | None:
    return _TOOLS.get(name)


def list_tools() -> list[ToolSpec]:
    return [_TOOLS[n] for n in sorted(_TOOLS)]


def to_strict_schema(schema: dict) -> dict:
    """Đưa JSON Schema của Pydantic về dạng strict: mọi object có additionalProperties false,
    mọi thuộc tính nằm trong required, bỏ ràng buộc không hỗ trợ."""
    schema = copy.deepcopy(schema)

    def walk(node, is_mapping=False):
        if isinstance(node, dict):
            if is_mapping:  # giá trị của properties, $defs: khóa là tên, không phải từ khóa schema
                for value in node.values():
                    walk(value)
                return
            for key in list(node):
                if key in _UNSUPPORTED_KEYS:
                    node.pop(key)
            if node.get("type") == "object" or "properties" in node:
                props = node.setdefault("properties", {})
                node["additionalProperties"] = False
                node["required"] = sorted(props)
            for key, value in node.items():
                walk(value, is_mapping=key in ("properties", "$defs", "definitions"))
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return schema


# Giới hạn của structured outputs cho cả request (trang structured-outputs, mục Schema complexity limits).
MAX_STRICT_TOOLS = 20
MAX_OPTIONAL_PARAMS = 24
MAX_UNION_PARAMS = 16


def tool_definition(spec: ToolSpec) -> dict:
    definition = {
        "name": spec.name,
        "description": spec.description,
        "input_schema": to_strict_schema(spec.input_model.model_json_schema()),
    }
    if spec.strict:
        definition["strict"] = True
    return definition


def count_complexity(schema: dict) -> tuple[int, int]:
    """Đếm (tham số không bắt buộc, tham số có anyOf hoặc mảng type) trong một schema, kể cả lồng nhau."""
    optional = union = 0

    def walk(node):
        nonlocal optional, union
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                required = set(node.get("required") or [])
                for name, sub in props.items():
                    if name not in required:
                        optional += 1
                    if isinstance(sub, dict) and ("anyOf" in sub or isinstance(sub.get("type"), list)):
                        union += 1
            for key, value in node.items():
                if key != "properties":
                    walk(value)
            if isinstance(props, dict):
                for sub in props.values():
                    walk(sub)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return optional, union


def check_strict_limits(defs: list[dict]) -> None:
    strict = [d for d in defs if d.get("strict")]
    optional = union = 0
    for d in strict:
        o, u = count_complexity(d["input_schema"])
        optional, union = optional + o, union + u
    if len(strict) > MAX_STRICT_TOOLS or optional > MAX_OPTIONAL_PARAMS or union > MAX_UNION_PARAMS:
        raise ValueError(
            f"Công cụ strict vượt giới hạn API: {len(strict)}/{MAX_STRICT_TOOLS} công cụ, "
            f"{optional}/{MAX_OPTIONAL_PARAMS} tham số không bắt buộc, {union}/{MAX_UNION_PARAMS} tham số union"
        )


def get_tool_definitions() -> list[dict]:
    """Định nghĩa công cụ app, sắp theo tên, khóa JSON ổn định để giữ cache."""
    defs = [tool_definition(s) for s in list_tools()]
    check_strict_limits(defs)
    return json.loads(json.dumps(defs, sort_keys=True, ensure_ascii=False))


def execute_approved(tctx: ToolContext, tool_name: str, tool_input: dict) -> ToolOutput:
    """Chat gọi khi người dùng bấm Duyệt (POST /chat/actions/{id}/approve); không qua Claude."""
    spec = _TOOLS.get(tool_name)
    if spec is None or spec.execute is None:
        raise AiError("NOT_FOUND", "Không có công cụ này để chạy.")
    return spec.execute(tctx, tool_input)
