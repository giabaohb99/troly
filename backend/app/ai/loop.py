"""Một lượt chat: ghép lời nhắc, stream, chạy công cụ, phát sự kiện (20 mục 3.6).

Hợp đồng với module chat (bảng việc mục 5): chat gọi `ai.router.choose_turn`, lưu tin người dùng và tin
`ai.prompt.build_turn_system_message`, rồi lặp `run_turn(ctx, plan, system_parts, history, store)`.
Tự viết vòng lặp (không dùng Tool Runner beta) để lưu từng khối qua TurnStore, chặn công cụ cần duyệt,
gom hành động cho app và phát sự kiện khớp SSE của 12 mục 5.3. Lỗi gọi Claude ném `AiError`.
"""

import json
import logging
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal

from pydantic import ValidationError

from app.ai import actions as act
from app.ai import mcp
from app.ai.client import ClaudeClient, ClaudeResult, get_client
from app.ai.prompt import (
    build_system,
    build_tools,
    normalize_history,
    strip_thinking,
    strip_thinking_before_turn,
)
from app.ai.registry import get_tool, get_tool_definitions
from app.ai.schemas import (
    AiError,
    AiRequestError,
    SystemParts,
    ToolContext,
    ToolOutput,
    ToolSpec,
    TurnEvent,
    TurnPlan,
    TurnStore,
)
from app.ai.settings import AiSettings, get_ai_settings

log = logging.getLogger(__name__)

TEXT_REFUSAL = "Em không làm được yêu cầu này."
TEXT_EMPTY = "Em chưa có câu trả lời, anh hỏi lại giúp em nhé."
TEXT_TOO_LONG = "Việc này dài quá, anh chia nhỏ giúp em nhé."
TEXT_CUT = "(Câu trả lời bị cắt vì quá dài.)"
PARA = "\n\n"
MAX_PAUSE_CONTINUES = 3
MAX_CITATIONS = 5
RESULT_MAX_ITEMS = 50
RESULT_MAX_CHARS = 500
APPROVAL_HOURS = 24


class _Totals:
    def __init__(self):
        self.prompt = 0
        self.cache_read = 0
        self.output = 0
        self.cost = Decimal(0)
        self.last_prompt = 0

    def add(self, res: ClaudeResult):
        self.prompt += res.usage.prompt_tokens
        self.cache_read += res.usage.cache_read_tokens
        self.output += res.usage.output_tokens
        self.cost += res.cost_usd
        self.last_prompt = res.usage.prompt_tokens

    def as_dict(self) -> dict:
        return {
            "input_tokens": self.prompt,
            "output_tokens": self.output,
            "cache_read_tokens": self.cache_read,
            "cost_usd": float(self.cost),
        }


def _texts(content: list[dict]) -> list[dict]:
    return [b for b in content if b.get("type") == "text"]


def _trim(value):
    """Cắt gọn kết quả công cụ: danh sách 50 dòng, chuỗi 500 ký tự."""
    if isinstance(value, str):
        return value if len(value) <= RESULT_MAX_CHARS else value[:RESULT_MAX_CHARS] + "..."
    if isinstance(value, list):
        items = [_trim(v) for v in value[:RESULT_MAX_ITEMS]]
        if len(value) > RESULT_MAX_ITEMS:
            items.append({"con_lai": len(value) - RESULT_MAX_ITEMS})
        return items
    if isinstance(value, dict):
        return {k: _trim(v) for k, v in value.items()}
    return value


def _error(code: str, message: str) -> tuple[dict, bool, None]:
    return {"loi": code, "thong_bao": message}, True, None


GONE_BEFORE_APPROVAL = (
    "Mục cần xóa không còn, đã được xóa trước đó; không tạo thẻ duyệt. Báo người dùng một câu là đã được xóa "
    "trước đó, không gọi lại công cụ."
)


def _run_tool(
    ctx: ToolContext, spec: ToolSpec, raw_input: dict, store: TurnStore
) -> tuple[dict, bool, ToolOutput | None]:
    """Chạy một công cụ trong savepoint riêng. Trả (kết quả cho Claude, is_error, ToolOutput)."""
    try:
        data = spec.input_model.model_validate(raw_input)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()))
        return _error("VALIDATION_ERROR", f"Đầu vào chưa hợp lệ ở {where or 'công cụ'}.")

    try:
        if spec.needs_approval is not None and spec.needs_approval(data):
            savepoint = ctx.session.begin_nested()
            try:
                draft = spec.prepare(ctx, data)
            except Exception as exc:
                if spec.name.startswith("delete_") and getattr(exc, "code", None) == "NOT_FOUND":
                    # Đối tượng đã bị xóa (vd. người dùng xóa tay trên app): không tạo thẻ.
                    return _error("NOT_FOUND", GONE_BEFORE_APPROVAL)
                raise
            finally:
                savepoint.rollback()  # prepare không được ghi DB
            pa_id = store.create_pending_action(spec.name, draft)
            expires_at = ctx.now + timedelta(hours=APPROVAL_HOURS)
            output = ToolOutput(
                result={
                    "trang_thai": "cho_duyet",
                    "pending_action_id": pa_id,
                    "ghi_chu": "Đã tạo thẻ xác nhận; việc chỉ chạy khi người dùng bấm Duyệt trên thẻ.",
                },
                actions=[
                    act.confirm(
                        pending_action_id=pa_id,
                        title=draft.title,
                        summary=draft.summary,
                        details=draft.details,
                        danger=draft.danger,
                        expires_at=expires_at,
                    )
                ],
            )
        else:
            with ctx.session.begin_nested():
                output = spec.run(ctx, data)
    except AiError as exc:
        return _error(exc.code, exc.message)
    except Exception as exc:  # lỗi nghiệp vụ của core có .code, .message
        code = getattr(exc, "code", None)
        if isinstance(code, str):
            return _error(code, getattr(exc, "message", None) or str(exc))
        log.exception("Công cụ %s lỗi", spec.name)
        return _error("INTERNAL_ERROR", "Công cụ gặp lỗi, thử lại sau.")

    result = _trim(output.result)
    if output.actions:
        labels = [a.get("label") or a.get("type") for a in output.actions]
        result = (
            {**result, "nut_cho_app": labels}
            if isinstance(result, dict)
            else {
                "ket_qua": result,
                "nut_cho_app": labels,
            }
        )
    return result, False, output


def _apply_citations(text_blocks: list[dict], sources: list[dict]) -> str:
    """Ghép chữ, gắn [n] sau đoạn có trích dẫn; điền `sources` {title, url} (tối đa 5, gộp URL trùng)."""
    out = []
    for block in text_blocks:
        piece = block.get("text", "")
        marks = []
        for cit in block.get("citations") or []:
            url = cit.get("url")
            if not url:
                continue
            idx = next((i for i, s in enumerate(sources) if s["url"] == url), None)
            if idx is None and len(sources) < MAX_CITATIONS:
                sources.append({"title": cit.get("title") or url, "url": url})
                idx = len(sources) - 1
            if idx is not None and (idx + 1) not in marks:
                marks.append(idx + 1)
        out.append(piece + "".join(f" [{n}]" for n in marks))
    return "".join(out)


def _search_results(content: list[dict]) -> list[dict]:
    """Kết quả tìm web trong một lần trả lời (kể cả khi tìm qua code execution)."""
    hits = []
    for block in content:
        if block.get("type") == "web_search_tool_result" and isinstance(block.get("content"), list):
            hits.extend(r for r in block["content"] if r.get("type") == "web_search_result" and r.get("url"))
    return hits


def _fallback_sources(hits: list[dict]) -> list[dict]:
    """Không có citations thì lấy tối đa 5 trang đã tìm làm nguồn, gộp URL trùng."""
    out: list[dict] = []
    for r in hits:
        if r["url"] not in (s["url"] for s in out):
            out.append({"title": r.get("title") or r["url"], "url": r["url"]})
        if len(out) == MAX_CITATIONS:
            break
    return out


def _call(client: ClaudeClient, params: dict, plan: TurnPlan, ctx: ToolContext) -> Iterator[TurnEvent]:
    """Stream một lần gọi; phát text.delta; kết quả cuối nằm ở StopIteration.value."""
    gen = client.stream_text(
        params,
        purpose="chat",
        user_id=ctx.user.user_id,
        conversation_id=ctx.conversation_id,
        mode=plan.mode,
    )
    while True:
        try:
            text = next(gen)
        except StopIteration as stop:
            return stop.value
        yield TurnEvent("text.delta", {"text": text})


def _tool_result_block(tool_use_id: str, result, is_error: bool) -> dict:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": json.dumps(result, ensure_ascii=False, default=str),
        "is_error": is_error,
    }


def run_turn(
    ctx: ToolContext,
    plan: TurnPlan,
    system_parts: SystemParts,
    history: list[dict],
    store: TurnStore,
    *,
    client: ClaudeClient | None = None,
    settings: AiSettings | None = None,
) -> Iterator[TurnEvent]:
    """Chạy một lượt. `history`: tin đã lưu đúng khối Claude, đã gồm tin người dùng và tin system của lượt."""
    settings = settings or get_ai_settings()
    client = client or get_client()
    tz = ctx.user.timezone or "Asia/Ho_Chi_Minh"

    # Lượt có kết nối MCP (QĐ-53, QĐ-56): gắn máy chủ còn dùng được; không còn cái nào thì lượt chạy như thường.
    connector_ids = tuple(cid for cid, _ in getattr(plan, "connectors", ()) or ())
    servers = mcp.connected_servers(ctx.session, ctx.user.user_id, connector_ids)
    mcp_servers = mcp.build_mcp_servers(servers)
    # Bỏ khối thinking của các lượt trước: không bao giờ gửi lại khối có prefix đã đổi (lỗi 400).
    messages = strip_thinking_before_turn(normalize_history(list(history)))
    messages = mcp.strip_mcp_blocks(messages, {s.name for s in servers})
    system = build_system(system_parts, plan.prefix_ttl, tz)
    tools = build_tools(get_tool_definitions(), plan, mcp.build_toolsets(servers))
    totals = _Totals()
    actions: list[dict] = []
    sources: list[dict] = []
    search_hits: list[dict] = []
    turn_texts: list[str] = []
    model_used = plan.model
    max_tokens = plan.max_tokens
    retried_cut = False
    retried_thinking = False
    pauses = 0
    rounds = 0
    final_text: str | None = None
    final_id: int | None = None

    while rounds < settings.ai_max_tool_rounds:
        rounds += 1
        params = {
            "model": plan.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "output_config": {"effort": plan.effort},
            "cache_control": {"type": "ephemeral"},
        }
        if tools:
            params["tools"] = tools
        if mcp_servers:
            params["mcp_servers"] = mcp_servers
        try:
            res = yield from _call(client, params, plan, ctx)
        except AiRequestError as exc:
            # Khối thinking không còn hợp lệ: bỏ hết rồi thử lại một lần.
            if not retried_thinking and "signature" in exc.message.lower():
                retried_thinking = True
                messages = strip_thinking(messages)
                rounds -= 1
                continue
            log.warning("Claude trả lỗi 400: %s", exc.message)
            raise AiError("AI_UNAVAILABLE", "AI đang lỗi, thử lại sau ít phút.") from exc

        totals.add(res)
        model_used = res.model
        content = res.content
        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        if mcp_servers:
            mcp.inspect_response(content, servers)
        # Kết quả MCP nằm ngay trong tin assistant: đánh dấu dữ liệu bên thứ ba như kết quả công cụ.
        third_party_reply = mcp.has_mcp_results(content)

        if res.stop_reason == "refusal":
            # Bỏ phần chữ dở; lưu một câu cố định làm câu trả lời của lượt.
            final_text = TEXT_REFUSAL
            final_id = store.save_assistant_message(
                [{"type": "text", "text": TEXT_REFUSAL}], res.run_id, model_used, TEXT_REFUSAL, None, False
            )
            break

        if res.stop_reason == "max_tokens" and (tool_uses or not _texts(content)) and not retried_cut:
            retried_cut = True
            max_tokens = min(max_tokens * 2, 32000)
            rounds -= 1
            continue

        round_text = _apply_citations(_texts(content), sources)
        search_hits.extend(_search_results(content))
        if round_text.strip():
            turn_texts.append(round_text.strip())
        pausing = res.stop_reason == "pause_turn" and pauses < MAX_PAUSE_CONTINUES
        is_final = not pausing and (res.stop_reason != "tool_use" or not tool_uses)
        if is_final:
            if res.stop_reason == "max_tokens":
                turn_texts.append(TEXT_CUT)
            final_text = PARA.join(turn_texts) or TEXT_EMPTY
            if not sources:
                sources = _fallback_sources(search_hits)
            if tool_uses:  # bị cắt giữa lúc gọi công cụ: không để tool_use thiếu kết quả trong lịch sử
                content = [b for b in content if b.get("type") != "tool_use"]
                content = content if _texts(content) else [*content, {"type": "text", "text": final_text}]
            final_id = store.save_assistant_message(
                content,
                res.run_id,
                model_used,
                final_text,
                sources or None,
                False,
                contains_third_party=third_party_reply,
            )
            break
        store.save_assistant_message(
            content, res.run_id, model_used, round_text, None, True, contains_third_party=third_party_reply
        )
        messages.append({"role": "assistant", "content": content})
        if pausing:
            pauses += 1
            rounds -= 1
            continue

        results = []
        third_party = False
        for block in tool_uses:
            name = block.get("name")
            spec = get_tool(name)
            if spec is None:
                results.append(
                    _tool_result_block(
                        block["id"], {"loi": "NOT_FOUND", "thong_bao": "Không có công cụ này."}, True
                    )
                )
                continue
            yield TurnEvent("tool.started", {"name": name, "label": spec.label})
            result, is_error, output = _run_tool(ctx, spec, block.get("input") or {}, store)
            yield TurnEvent("tool.finished", {"name": name, "ok": not is_error})
            if output is not None:
                third_party = third_party or output.contains_third_party
                for action in output.actions:
                    action = {"id": f"a{len(actions) + 1}", **action}
                    actions.append(action)
                    yield TurnEvent("action", action)
            results.append(_tool_result_block(block["id"], result, is_error))
        store.save_tool_results(results, third_party)
        messages.append({"role": "user", "content": results})
    else:
        # Hết vòng mà model vẫn gọi công cụ: lượt cuối là tin kết quả, thêm câu trả lời cố định.
        turn_texts.append(TEXT_TOO_LONG)
        final_text = PARA.join(turn_texts)
        final_id = store.save_assistant_message(
            [{"type": "text", "text": TEXT_TOO_LONG}], None, model_used, final_text, sources or None, False
        )

    yield TurnEvent(
        "turn.completed",
        {
            "text": final_text or TEXT_EMPTY,
            "actions": actions,
            "model": model_used,
            "citations": sources,
            "usage": totals.as_dict(),
            "last_prompt_tokens": totals.last_prompt,
            "message_id": final_id,
        },
    )
