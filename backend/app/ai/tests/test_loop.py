import json

import pytest
from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.loop import TEXT_REFUSAL, TEXT_TOO_LONG, run_turn
from app.ai.prompt import build_turn_system_message
from app.ai.registry import register_tools
from app.ai.router import choose_turn
from app.ai.schemas import AiError, AiRequestError, ApprovalDraft, SystemParts, ToolOutput, ToolSpec
from app.ai.tests.fake_claude import FakeClaude, text_reply, tool_call


class AddInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount_vnd: int = Field(description="Số tiền")


class DeleteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[int]


def _add_tool(calls, fail=False):
    def run(tctx, data):
        if fail:
            raise RuntimeError("hỏng")
        calls.append((tctx.user.user_id, data.amount_vnd))
        return ToolOutput(
            result={"expense_id": 5}, actions=[act.open_screen("Sửa khoản này", "expense_detail")]
        )

    return ToolSpec(
        name="add_expense", label="Đang ghi khoản chi", description="Ghi chi", input_model=AddInput, run=run
    )


def _delete_tool(executed):
    return ToolSpec(
        name="delete_expense",
        label="Đang xóa",
        description="Xóa",
        input_model=DeleteInput,
        run=lambda tctx, data: executed.append(data.ids) or ToolOutput(result={"da_xoa": data.ids}),
        needs_approval=lambda data: len(data.ids) >= 2,
        prepare=lambda tctx, data: ApprovalDraft(
            title="Xóa 2 khoản", summary="Xóa", input={"ids": data.ids}, danger=True
        ),
        execute=lambda tctx, inp: ToolOutput(result={}),
    )


def _run(ctx, store, client, settings, text="cơm trưa 45k", mode=None, history=None):
    plan = choose_turn(text, mode, settings=settings)
    if history is None:
        history = [{"role": "user", "content": [{"type": "text", "text": text}]}]
    history = [*history, build_turn_system_message(ctx.now, ctx.user.timezone, plan)]
    parts = SystemParts(profile_md="## Xưng hô\nGọi đại ca.")
    events = list(run_turn(ctx, plan, parts, history, store, client=client, settings=settings))
    return events, events[-1]


def test_plain_reply_streams_and_saves(ctx, store, make_client, settings):
    fake = FakeClaude([text_reply("Chào đại ca.")])
    events, done = _run(ctx, store, make_client(fake), settings, text="chào")
    assert "".join(e.data["text"] for e in events if e.type == "text.delta") == "Chào đại ca."
    assert done.type == "turn.completed"
    assert done.data["text"] == "Chào đại ca." and done.data["model"] == "claude-haiku-5-5"
    assert set(done.data["usage"]) == {"input_tokens", "output_tokens", "cache_read_tokens", "cost_usd"}
    assert store.assistant[-1]["hidden"] is False and store.assistant[-1]["text"] == "Chào đại ca."
    req = fake.requests[0]
    assert req["beta"] is False and "fallbacks" not in req  # Haiku không có dự phòng phía máy chủ
    assert req["messages"][-1]["role"] == "system"
    assert "Thời điểm hiện tại: thứ Tư, 18/11/2026, 11:30" in req["messages"][-1]["content"]
    assert req["output_config"] == {"effort": "low"}
    assert "temperature" not in req


def test_tool_round_runs_tool_and_emits_action(ctx, store, make_client, settings, session):
    calls = []
    register_tools([_add_tool(calls)])
    fake = FakeClaude([tool_call("add_expense", {"amount_vnd": 45000}), text_reply("Đã ghi 45.000đ.")])
    events, done = _run(ctx, store, make_client(fake), settings)
    types = [e.type for e in events]
    assert types.index("tool.started") < types.index("tool.finished") < types.index("action")
    assert calls == [(1, 45000)] and session.released == 1
    assert done.data["actions"][0]["id"] == "a1" and done.data["actions"][0]["type"] == "open_screen"
    result_msg = fake.requests[1]["messages"][-1]
    assert result_msg["role"] == "user" and result_msg["content"][0]["type"] == "tool_result"
    payload = json.loads(result_msg["content"][0]["content"])
    assert payload["expense_id"] == 5 and payload["nut_cho_app"] == ["Sửa khoản này"]
    assert store.order == ["assistant", "tool_results", "assistant"]
    assert [m["hidden"] for m in store.assistant] == [True, False]


def test_tool_crash_rolls_back_savepoint_and_reports_error(ctx, store, make_client, settings, session):
    register_tools([_add_tool([], fail=True)])
    fake = FakeClaude([tool_call("add_expense", {"amount_vnd": 1}), text_reply("Lỗi rồi.")])
    _run(ctx, store, make_client(fake), settings)
    assert session.rollbacks == 1
    block = fake.requests[1]["messages"][-1]["content"][0]
    assert block["is_error"] is True and json.loads(block["content"])["loi"] == "INTERNAL_ERROR"


def test_bad_tool_input_returns_error_to_model(ctx, store, make_client, settings):
    register_tools([_add_tool([])])
    fake = FakeClaude([tool_call("add_expense", {"amount_vnd": "nhiều"}), text_reply("Thiếu số tiền.")])
    _run(ctx, store, make_client(fake), settings)
    block = fake.requests[1]["messages"][-1]["content"][0]
    assert block["is_error"] is True and json.loads(block["content"])["loi"] == "VALIDATION_ERROR"


def test_bulk_delete_creates_pending_action_without_running(ctx, store, make_client, settings, session):
    executed = []
    register_tools([_delete_tool(executed)])
    fake = FakeClaude([tool_call("delete_expense", {"ids": [1, 2]}), text_reply("Đã soạn, bấm Duyệt.")])
    _, done = _run(ctx, store, make_client(fake), settings, text="xóa hai khoản")
    assert executed == [] and session.rollbacks == 1  # prepare chạy trong savepoint rồi bỏ
    assert store.pending[0]["tool_name"] == "delete_expense"
    confirm = done.data["actions"][0]
    assert confirm["type"] == "confirm" and confirm["pending_action_id"] == 101 and confirm["danger"] is True
    assert "require_unlock" not in confirm and "payload" not in confirm


def test_single_delete_runs_now(ctx, store, make_client, settings):
    executed = []
    register_tools([_delete_tool(executed)])
    fake = FakeClaude([tool_call("delete_expense", {"ids": [1]}), text_reply("Đã xóa.")])
    _run(ctx, store, make_client(fake), settings, text="xóa khoản cà phê")
    assert executed == [[1]] and store.pending == []


def test_refusal_does_not_run_tools(ctx, store, make_client, settings):
    calls = []
    register_tools([_add_tool(calls)])
    refused = tool_call("add_expense", {"amount_vnd": 1}, stop_reason="refusal")
    refused["stop_details"] = {"type": "refusal", "category": "general_harms"}
    _, done = _run(ctx, store, make_client(FakeClaude([refused])), settings)
    assert calls == [] and done.data["text"] == TEXT_REFUSAL
    assert store.assistant[-1]["content"] == [{"type": "text", "text": TEXT_REFUSAL}]


def test_max_tokens_with_tool_use_retries_bigger(ctx, store, make_client, settings):
    calls = []
    register_tools([_add_tool(calls)])
    cut = tool_call("add_expense", {"amount_vnd": 1}, stop_reason="max_tokens")
    fake = FakeClaude([cut, text_reply("Xong.")])
    _, done = _run(ctx, store, make_client(fake), settings)
    assert calls == [] and fake.requests[1]["max_tokens"] == 8192 and done.data["text"] == "Xong."


def test_cut_twice_never_saves_dangling_tool_use(ctx, store, make_client, settings):
    register_tools([_add_tool([])])
    cut = tool_call("add_expense", {"amount_vnd": 1}, stop_reason="max_tokens")
    _run(ctx, store, make_client(FakeClaude([cut, cut])), settings)
    assert all(b["type"] != "tool_use" for b in store.assistant[-1]["content"])


def test_rounds_exhausted_appends_fixed_answer(ctx, store, make_client, settings):
    register_tools([_add_tool([])])
    settings = settings.model_copy(update={"ai_max_tool_rounds": 2})
    fake = FakeClaude([tool_call("add_expense", {"amount_vnd": 1}, tool_id=f"t{i}") for i in range(2)])
    _, done = _run(ctx, store, make_client(fake), settings)
    assert TEXT_TOO_LONG in done.data["text"]
    assert store.order[-2:] == ["tool_results", "assistant"]


def test_api_error_raises_ai_error(ctx, store, make_client, settings):
    fake = FakeClaude([AiError("AI_UNAVAILABLE", "Không gọi được Claude.")])
    with pytest.raises(AiError) as exc:
        _run(ctx, store, make_client(fake), settings)
    assert exc.value.code == "AI_UNAVAILABLE"


def test_earlier_turn_thinking_is_stripped(ctx, store, make_client, settings):
    history = [
        {"role": "user", "content": "chào"},
        {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "", "signature": "s"},
                {"type": "text", "text": "Chào"},
            ],
        },
        {"role": "user", "content": "nữa"},
    ]
    fake = FakeClaude([text_reply("Ừ.")])
    _run(ctx, store, make_client(fake), settings, text="nữa", history=history)
    sent = fake.requests[0]["messages"][1]["content"]
    assert sent == [{"type": "text", "text": "Chào"}]


def test_thinking_signature_error_strips_and_retries(ctx, store, make_client, settings):
    register_tools([_add_tool([])])
    fake = FakeClaude(
        [
            tool_call("add_expense", {"amount_vnd": 1}),
            AiRequestError("AI_UNAVAILABLE", "Invalid `signature` in `thinking` block"),
            text_reply("Ừ."),
        ]
    )
    # Khối thinking của lượt hiện tại nằm trong tin assistant trước tool_result.
    fake.script[0]["content"].insert(0, {"type": "thinking", "thinking": "", "signature": "s"})
    _, done = _run(ctx, store, make_client(fake), settings)
    assert done.data["text"] == "Ừ."
    resent = fake.requests[2]["messages"]
    assert all(
        b.get("type") != "thinking" for m in resent if isinstance(m["content"], list) for b in m["content"]
    )


def test_research_uses_sonnet_web_tools_and_citations(ctx, store, make_client, settings):
    reply = {
        "content": [
            {
                "type": "server_tool_use",
                "id": "srv_1",
                "name": "web_search",
                "input": {"query": "giá vé phà"},
            },
            {"type": "web_search_tool_result", "tool_use_id": "srv_1", "content": []},
            {
                "type": "text",
                "text": "Vé phà khoảng 50.000đ.",
                "citations": [
                    {"type": "web_search_result_location", "url": "https://a.vn/x", "title": "Trang A"}
                ],
            },
            {
                "type": "text",
                "text": " Giờ chạy từ 5:00.",
                "citations": [
                    {"url": "https://a.vn/x", "title": "Trang A"},
                    {"url": "https://b.vn", "title": "B"},
                ],
            },
        ],
        "usage": {"server_tool_use": {"web_search_requests": 2}},
        "model": "claude-sonnet-5-5",
    }
    fake = FakeClaude([reply])
    _, done = _run(ctx, store, make_client(fake), settings, text="giá vé phà", mode="research")
    req = fake.requests[0]
    assert req["model"] == "claude-sonnet-5-5"
    assert req["beta"] is True and req["fallbacks"] == "default"
    assert [t.get("type") for t in req["tools"][-2:]] == ["web_search_20260209", "web_fetch_20260209"]
    assert "tìm web" in req["messages"][-1]["content"]
    assert done.data["text"] == "Vé phà khoảng 50.000đ. [1] Giờ chạy từ 5:00. [1] [2]"
    assert done.data["citations"] == [
        {"title": "Trang A", "url": "https://a.vn/x"},
        {"title": "B", "url": "https://b.vn"},
    ]
    assert store.assistant[-1]["citations"] == done.data["citations"]
    assert done.data["usage"]["cost_usd"] > 0.02  # có tính 2 lần tìm web


def test_pause_turn_resends(ctx, store, make_client, settings):
    paused = {
        "content": [{"type": "server_tool_use", "id": "srv_1", "name": "web_search", "input": {}}],
        "stop_reason": "pause_turn",
    }
    fake = FakeClaude([paused, text_reply("Xong.")])
    _, done = _run(ctx, store, make_client(fake), settings, mode="research")
    assert len(fake.requests) == 2 and fake.requests[1]["messages"][-1]["role"] == "assistant"
    assert done.data["text"] == "Xong."


def test_research_without_citations_falls_back_to_search_results(ctx, store, make_client, settings):
    reply = {
        "content": [
            {"type": "server_tool_use", "id": "srv_1", "name": "web_search", "input": {"query": "phà"}},
            {
                "type": "web_search_tool_result",
                "tool_use_id": "srv_1",
                "content": [
                    {
                        "type": "web_search_result",
                        "url": "https://a.vn/x",
                        "title": "Trang A",
                        "encrypted_content": "e",
                    },
                    {
                        "type": "web_search_result",
                        "url": "https://a.vn/x",
                        "title": "Trang A",
                        "encrypted_content": "e",
                    },
                    {
                        "type": "web_search_result",
                        "url": "https://b.vn",
                        "title": "B",
                        "encrypted_content": "e",
                    },
                ],
            },
            {"type": "text", "text": "Phà chạy từ 6:00."},
        ],
        "model": "claude-sonnet-5-5",
    }
    _, done = _run(ctx, store, make_client(FakeClaude([reply])), settings, text="giờ phà", mode="research")
    assert done.data["citations"] == [
        {"title": "Trang A", "url": "https://a.vn/x"},
        {"title": "B", "url": "https://b.vn"},
    ]
    assert done.data["text"] == "Phà chạy từ 6:00."


def test_delete_target_already_gone_creates_no_card(ctx, store, make_client, settings, session):
    """Người dùng đã xóa tay trên app rồi mới nhờ bot xóa: không tạo thẻ, báo đã xóa trước đó."""
    from app.core.errors import NotFoundError

    def gone(tctx, data):
        raise NotFoundError()

    spec = _delete_tool([])
    import dataclasses

    register_tools([dataclasses.replace(spec, prepare=gone)])
    fake = FakeClaude(
        [tool_call("delete_expense", {"ids": [1, 2]}), text_reply("Hai khoản đó đã được xóa trước đó.")]
    )
    _run(ctx, store, make_client(fake), settings, text="xóa hai khoản")
    assert store.pending == [] and session.rollbacks == 1
    result = next(
        b
        for m in fake.requests[1]["messages"]
        if isinstance(m["content"], list)
        for b in m["content"]
        if b.get("type") == "tool_result"
    )
    assert result["is_error"] is True
    assert "đã được xóa trước đó" in str(result["content"])
