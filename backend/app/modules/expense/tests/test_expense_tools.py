"""Công cụ AI của chi tiêu, chạy trên DB thử (bài kiểm của agent AI, việc 1-06)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.ai import client as ai_client
from app.ai.registry import get_tool, register_tools, to_strict_schema
from app.ai.schemas import ToolContext
from app.ai.tests.fake_claude import FakeClaude, text_reply, tool_call
from app.core import clock
from app.modules.expense import tools
from app.modules.expense.models import Expense

NOW = datetime(2026, 11, 18, 5, 0, tzinfo=UTC)  # 12:00 giờ Việt Nam


@pytest.fixture
def ctx(db, user, monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: NOW)
    return ToolContext(session=db, user=user, conversation_id=None, now=NOW)


def _spec(name):
    return next(t for t in tools.TOOLS if t.name == name)


def _call(ctx, name, **data):
    spec = _spec(name)
    return spec.run(ctx, spec.input_model.model_validate(data))


def _add(ctx, amount, note, **kw):
    base = {
        "amount_vnd": amount,
        "kind": "expense",
        "account": None,
        "to_account": None,
        "category": None,
        "merchant": None,
        "place": None,
        "note": note,
        "spent_at": None,
    }
    return _call(ctx, "add_expense", **{**base, **kw})


def _query(ctx, **kw):
    base = {
        "from_date": None,
        "to_date": None,
        "kind": None,
        "account": None,
        "category": None,
        "text_contains": None,
        "needs_review": None,
        "group_by": "none",
        "limit": None,
    }
    return _call(ctx, "query_expenses", **{**base, **kw})


def test_schemas_are_strict():
    for spec in tools.TOOLS:
        schema = to_strict_schema(spec.input_model.model_json_schema())
        assert schema["additionalProperties"] is False
        assert "user_id" not in schema["properties"]


def test_add_expense_guesses_category_and_reports_today(ctx):
    out = _add(ctx, 45000, "cơm trưa")
    assert out.result["category"] == "Ăn uống"
    assert out.result["today_total_vnd"] == 45000
    assert out.actions[0]["type"] == "open_screen" and out.actions[0]["screen"] == "expense_detail"


def test_transfer_needs_to_account(ctx):
    from app.ai.schemas import AiError

    with pytest.raises(AiError):
        _add(ctx, 500000, "chuyển", kind="transfer", account="vcb")
    out = _add(ctx, 500000, "chuyển", kind="transfer", account="vcb", to_account="momo")
    assert out.result["kind"] == "transfer"


def test_query_month_excludes_transfer_and_groups(ctx):
    _add(ctx, 45000, "cơm trưa")
    _add(ctx, 30000, "cà phê")
    _add(ctx, 500000, "chuyển", kind="transfer", account="vcb", to_account="momo")
    _add(ctx, 80000, "đổ xăng", spent_at=NOW - timedelta(days=40))
    out = _query(ctx, group_by="category")
    assert out.result["total_expense_vnd"] == 75000
    assert out.result["total_transfer_vnd"] == 500000
    assert out.result["groups"][0]["label"] == "Ăn uống"
    assert len(out.result["items"]) == 3


def test_query_text_filter_sums_matches(ctx):
    _add(ctx, 30000, "cà phê sáng")
    _add(ctx, 35000, "cà phê chiều")
    _add(ctx, 45000, "cơm trưa")
    out = _query(ctx, text_contains="ca phe", limit=0)
    assert out.result["matched_total_vnd"] == 65000 and out.result["matched_count"] == 2
    assert "items" not in out.result


def test_delete_one_runs_now_with_undo(ctx, db):
    eid = _add(ctx, 35000, "cà phê").result["expense_id"]
    spec = _spec("delete_expense")
    data = spec.input_model.model_validate({"expense_ids": [eid], "reason": "nhập nhầm"})
    assert spec.needs_approval(data) is False
    out = spec.run(ctx, data)
    assert out.actions[0]["type"] == "undo" and out.actions[0]["ids"] == [eid]
    assert db.get(Expense, eid).deleted_at is not None


def test_delete_many_prepares_without_deleting(ctx, db):
    ids = [_add(ctx, 30000 + i, f"cà phê {i}").result["expense_id"] for i in range(3)]
    spec = _spec("delete_expense")
    data = spec.input_model.model_validate({"expense_ids": ids, "reason": "dọn"})
    assert spec.needs_approval(data) is True
    draft = spec.prepare(ctx, data)
    assert draft.danger is True and draft.input == {"expense_ids": ids} and len(draft.details) == 3
    assert all(db.get(Expense, i).deleted_at is None for i in ids)
    spec.execute(ctx, draft.input)
    assert all(db.get(Expense, i).deleted_at is not None for i in ids)


def test_other_users_expense_is_not_found(ctx, db):
    from app.core.context import UserContext
    from app.core.models import User
    from app.modules.expense import service

    # Một người dùng (QĐ-27) nhưng mã vẫn lọc user_id: tạo thẳng người thứ hai để kiểm chéo.
    other = User(email="khac@example.com", name="Khác", password_hash="x", timezone="Asia/Ho_Chi_Minh")
    db.add(other)
    db.flush()
    theirs = service.create_expense(db, UserContext(other.id, "Asia/Ho_Chi_Minh"), {"amount_vnd": 1000})
    with pytest.raises(Exception) as exc:
        _call(ctx, "delete_expense", expense_ids=[theirs["id"]], reason="x")
    assert getattr(exc.value, "code", "") == "NOT_FOUND"


def test_chat_turn_records_expense_end_to_end(auth_client, db, monkeypatch):
    """Lát cắt mỏng: câu chat -> Claude giả gọi add_expense -> có dòng chi tiêu -> trả lời."""
    from app.ai.models import DbRunRecorder

    if get_tool("add_expense") is None:
        register_tools(tools.TOOLS)
    fake = FakeClaude(
        [
            tool_call(
                "add_expense",
                {
                    "amount_vnd": 45000,
                    "kind": "expense",
                    "account": None,
                    "to_account": None,
                    "category": None,
                    "merchant": None,
                    "place": None,
                    "note": "cơm trưa",
                    "spent_at": None,
                },
            ),
            text_reply("Đã ghi 45.000đ cơm trưa."),
        ]
    )
    monkeypatch.setattr(ai_client, "_client", ai_client.ClaudeClient(sdk=fake, recorder=DbRunRecorder()))
    resp = auth_client.post(
        "/api/v1/chat/messages", json={"client_message_id": str(uuid.uuid4()), "text": "cơm trưa 45k"}
    )
    assert resp.status_code == 200, resp.text
    msg = resp.json()["data"]["assistant_message"]
    assert msg["text"] == "Đã ghi 45.000đ cơm trưa."
    assert any(a["type"] == "open_screen" for a in msg["actions"])
    rows = list(db.scalars(select(Expense).where(Expense.deleted_at.is_(None))))
    assert [r.amount_vnd for r in rows] == [45000]
