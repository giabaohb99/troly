"""Chạy bộ câu mẫu với Claude thật (20 mục 6). Chỉ chạy tay: pytest -m ai_eval.

Mỗi câu: DB thử sạch, dữ liệu mẫu cố định, giờ cố định 18/11/2026 11:30 giờ Việt Nam, gọi POST /chat/messages,
chấm bằng luật, ghi kết quả vào results/<ngày>-<model>.json.
Dừng khi tổng tiền vượt AI_EVAL_MAX_USD (mặc định 1).
"""

import json
import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

HERE = Path(__file__).parent
NOW = datetime(2026, 11, 18, 4, 30, tzinfo=UTC)  # 11:30 giờ Việt Nam, thứ Tư
PHASE = int(os.environ.get("AI_EVAL_PHASE", "1"))
MAX_USD = Decimal(os.environ.get("AI_EVAL_MAX_USD", "1"))
_RESULTS: list[dict] = []
_SPENT = {"usd": Decimal(0)}

pytestmark = pytest.mark.ai_eval


def _load_cases() -> list[dict]:
    try:
        import yaml
    except ImportError:
        return []
    cases = yaml.safe_load((HERE / "cases.yaml").read_text(encoding="utf-8"))
    return [c for c in cases if c.get("phase", 1) <= PHASE]


CASES = _load_cases()


@pytest.fixture(scope="module", autouse=True)
def write_results():
    yield
    if not _RESULTS:
        return
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    model = os.environ.get("AI_MODEL_CHAT", "claude-haiku-5-5")
    path = out / f"{datetime.now(UTC):%Y-%m-%d}-{model}.json"
    passed = sum(r["ok"] for r in _RESULTS)
    summary = {
        "passed": passed,
        "total": len(_RESULTS),
        "safety_all_passed": all(r["ok"] for r in _RESULTS if r["group"] == "an_toan"),
        "cost_usd": float(_SPENT["usd"]),
        "cases": _RESULTS,
    }
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _seed(db, user) -> dict:
    """Dữ liệu mẫu: hồ sơ lõi, chi tiêu 3 tháng, một ghi chú visa. Trả số liệu để so."""
    from app.core.context import UserContext
    from app.modules.expense import service as expense
    from app.modules.memory import service as memory

    memory.update_profile(
        db,
        user.user_id,
        "## Xưng hô\n- Gọi đại ca, xưng em\n\n## Thông tin cơ bản\n- Đang ở Cần Thơ\n",
        None,
    )
    memory.create_note(db, user.user_id, "Hồ sơ visa", "Nộp hồ sơ visa Úc trước thứ Sáu 20/11.", ["visa"])
    ctx = UserContext(user.user_id, user.timezone)

    def add(amount, note, at, **kw):
        expense.create_expense(
            db, ctx, {"amount_vnd": amount, "note": note, "spent_at": at, **kw}, source="manual"
        )

    add(35000, "cà phê", NOW - timedelta(hours=4))  # 07:30 hôm nay
    add(30000, "cà phê", NOW - timedelta(days=2))
    add(45000, "cơm trưa", NOW - timedelta(days=1))
    add(1200000, "tiền điện", NOW - timedelta(days=10))
    add(2000000, "mua giày", NOW - timedelta(days=40))
    add(800000, "nhậu", NOW - timedelta(days=70))
    add(500000, "chuyển ví", NOW - timedelta(days=3), kind="transfer", account="vcb", to_account="momo")
    db.flush()
    month_total = expense.summarize(db, ctx, "month", None, None, None, None)["total_expense_vnd"]
    return {"month_total": f"{month_total:,}".replace(",", ".")}


def _tool_calls(db, conversation_id=None) -> list[dict]:
    from app.modules.chat.models import Message

    calls = []
    for m in db.scalars(select(Message).where(Message.role == "assistant").order_by(Message.id)):
        for b in m.content if isinstance(m.content, list) else []:
            if b.get("type") == "tool_use":
                calls.append({"name": b["name"], "input": b.get("input") or {}})
    return calls


def _sentences(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()])


def _check(case: dict, ctx: dict) -> list[str]:
    exp = case.get("expect", {})
    errs: list[str] = []
    calls, reply, msg = ctx["calls"], ctx["reply"], ctx["message"]
    names = [c["name"] for c in calls]
    if exp.get("model") and not (msg.get("model") or "").startswith(exp["model"]):
        errs.append(f"model {msg.get('model')} khác {exp['model']}")
    wanted = exp.get("tools_called")
    if wanted == [] and names:
        errs.append(f"không được gọi công cụ, đã gọi {names}")
    for name in set(wanted or []):
        if names.count(name) < (wanted or []).count(name):
            errs.append(f"thiếu lần gọi {name}")
    for name in exp.get("tools_not_called", []):
        if name in names:
            errs.append(f"không được gọi {name}")
    for name, args in (exp.get("tool_args") or {}).items():
        if not any(c["name"] == name and all(c["input"].get(k) == v for k, v in args.items()) for c in calls):
            errs.append(f"{name} sai tham số, cần {args}")
    for key, want in (exp.get("db_after") or {}).items():
        if key == "tab_expense":
            for field, value in want.items():
                if ctx["expense_delta"][field] != value:
                    errs.append(f"{field} = {ctx['expense_delta'][field]}, cần {value}")
        elif key == "pending_action" and ctx["pending"] != want:
            errs.append(f"pending_action = {ctx['pending']}, cần {want}")
    if exp.get("amounts_added") and sorted(ctx["amounts_added"]) != sorted(exp["amounts_added"]):
        errs.append(f"số tiền ghi {ctx['amounts_added']}, cần {exp['amounts_added']}")
    if exp.get("spent_on_local_date") and exp["spent_on_local_date"] not in ctx["spent_dates"]:
        errs.append(f"ngày chi {ctx['spent_dates']}, cần {exp['spent_on_local_date']}")
    types = [a["type"] for a in msg.get("actions") or []]
    for t in exp.get("actions", []):
        if t not in types:
            errs.append(f"thiếu hành động {t}")
    if exp.get("reply_max_sentences") and _sentences(reply) > exp["reply_max_sentences"]:
        errs.append(f"trả lời {_sentences(reply)} câu, tối đa {exp['reply_max_sentences']}")
    for s in exp.get("reply_must_contain", []):
        s = s.format(**ctx["seed"])
        if s.lower() not in reply.lower():
            errs.append(f"thiếu chữ {s!r}")
    for pattern in exp.get("reply_must_not_match", []):
        if re.search(pattern, reply):
            errs.append(f"có chữ cấm {pattern!r}")
    if exp.get("has_citations") and not msg.get("citations"):
        errs.append("thiếu nguồn web")
    for s in exp.get("profile_contains", []):
        if s not in ctx["profile"]:
            errs.append(f"hồ sơ thiếu {s!r}")
    for s in exp.get("profile_not_contains", []):
        if s in ctx["profile"]:
            errs.append(f"hồ sơ còn {s!r}")
    return errs


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(case, auth_client, db, user, monkeypatch):
    from app.ai import client as ai_client
    from app.ai.models import AiRun
    from app.ai.registry import get_tool
    from app.core import clock
    from app.modules.chat.models import PendingAction
    from app.modules.expense.models import Expense
    from app.modules.memory import service as memory

    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("Chưa có ANTHROPIC_API_KEY")
    if _SPENT["usd"] >= MAX_USD:
        pytest.skip(f"Đã tiêu {_SPENT['usd']} USD, chạm trần {MAX_USD}")
    if case.get("needs_tool") and get_tool(case["needs_tool"]) is None:
        pytest.skip(f"Chưa có công cụ {case['needs_tool']}")

    monkeypatch.setattr(clock, "now", lambda: NOW)
    monkeypatch.setattr(ai_client, "_client", None)
    seed = _seed(db, user)

    def counts():
        alive = db.scalar(select(func.count()).select_from(Expense).where(Expense.deleted_at.is_(None)))
        dead = db.scalar(select(func.count()).select_from(Expense).where(Expense.deleted_at.is_not(None)))
        return alive, dead

    before_alive, before_dead = counts()
    before_ids = set(db.scalars(select(Expense.id)))
    resp = auth_client.post(
        "/api/v1/chat/messages",
        json={"client_message_id": str(uuid.uuid4()), "text": case["user"], "mode": case.get("mode")},
    )
    assert resp.status_code == 200, resp.text
    message = resp.json()["data"]["assistant_message"]
    after_alive, after_dead = counts()
    new_rows = list(db.scalars(select(Expense).where(Expense.id.not_in(before_ids))))
    runs = list(db.scalars(select(AiRun).where(AiRun.purpose == "chat")))
    cost = sum((r.cost_usd for r in runs), Decimal(0))
    _SPENT["usd"] += cost

    ctx = {
        "seed": seed,
        "message": message,
        "reply": message.get("text") or "",
        "calls": _tool_calls(db),
        "expense_delta": {
            "count_delta": after_alive - before_alive,
            "deleted_delta": after_dead - before_dead,
        },
        "amounts_added": [r.amount_vnd for r in new_rows],
        "spent_dates": [clock.to_local(r.spent_at, user.timezone).date().isoformat() for r in new_rows],
        "pending": db.scalar(select(func.count()).select_from(PendingAction)),
        "profile": memory.get_profile_markdown(db, user.user_id),
    }
    errors = _check(case, ctx)
    _RESULTS.append(
        {
            "id": case["id"],
            "group": case.get("group", "thuong"),
            "ok": not errors,
            "errors": errors,
            "model": message.get("model"),
            "reply": ctx["reply"],
            "tools": [c["name"] for c in ctx["calls"]],
            "calls": len(runs),
            "input_tokens": sum(
                r.input_tokens + r.cache_read_tokens + r.cache_write_5m_tokens + r.cache_write_1h_tokens
                for r in runs
            ),
            "cache_read_tokens": sum(r.cache_read_tokens for r in runs),
            "output_tokens": sum(r.output_tokens for r in runs),
            "cost_usd": float(cost),
        }
    )
    assert not errors, "; ".join(errors)
