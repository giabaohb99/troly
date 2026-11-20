"""Module report: thẻ màn Báo cáo, chi phí AI theo tháng, công cụ `get_report` (việc 4-02)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.ai.models import AiRun
from app.ai.schemas import ToolContext
from app.core import clock
from app.modules.calendar import service as calendar
from app.modules.device import service as device
from app.modules.expense import service as expense
from app.modules.inbox import service as inbox
from app.modules.report import service, tools
from app.modules.task import service as task


def vn(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=UTC) - timedelta(hours=7)


NOW = vn(2026, 11, 18, 12)  # thứ Tư


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: NOW)


def _spend(db, user, amount, at, kind="expense", note="com trua"):
    return expense.create_expense(
        db, user, {"amount_vnd": amount, "kind": kind, "spent_at": at, "note": note}
    )


def _run(db, user, usd, at, model="claude-haiku-5-5", purpose="chat", cache_read=0, inp=100):
    db.add(
        AiRun(
            user_id=user.user_id,
            purpose=purpose,
            model=model,
            cost_usd=Decimal(str(usd)),
            input_tokens=inp,
            cache_read_tokens=cache_read,
            created_at=at,
        )
    )
    db.flush()


def _zalo(db, user, sender, text, minutes):
    at = vn(2026, 11, 18, 9) + timedelta(minutes=minutes)
    return inbox.ingest_notification(
        db,
        user,
        parser="zalo",
        app_package="com.zing.zalo",
        payload={"title": sender, "messages": [{"sender": sender, "text": text, "at": at.isoformat()}]},
        posted_at=at,
    )


@pytest.fixture
def seeded(db, user):
    _spend(db, user, 45_000, vn(2026, 11, 3, 12))
    _spend(db, user, 300_000, vn(2026, 11, 10, 19), note="xang xe")
    _spend(db, user, 15_000_000, vn(2026, 11, 5, 9), kind="income", note="luong")
    _spend(db, user, 200_000, vn(2026, 10, 20, 12))
    calendar.create_event(
        db, user, {"title": "Họp quý", "start_at": vn(2026, 11, 19, 9), "end_at": vn(2026, 11, 19, 10)}
    )
    calendar.create_event(
        db, user, {"title": "Ăn tối", "start_at": vn(2026, 11, 16, 19), "end_at": vn(2026, 11, 16, 20)}
    )
    calendar.create_event(
        db, user, {"title": "Tuần sau", "start_at": vn(2026, 11, 24, 9), "end_at": vn(2026, 11, 24, 10)}
    )
    task.create_task(db, user, {"title": "Nộp hồ sơ", "due_date": date(2026, 11, 17)})
    task.create_task(db, user, {"title": "Gọi điện", "due_date": date(2026, 11, 18)})
    task.create_task(db, user, {"title": "Đọc sách"})
    inbox.create_rule(db, user.user_id, "vip_sender", "Mẹ", None)
    _zalo(db, user, "Mẹ", "Tối về ăn cơm không con", 0)
    _zalo(db, user, "Tuấn", "Mai đá bóng nhé", 5)
    _zalo(db, user, "Tuấn", "6h sân cũ", 6)
    device.register(db, user.user_id, {"name": "S25+"})
    _run(db, user, 0.5, vn(2026, 11, 2, 10), model="claude-sonnet-5-5", purpose="trip_evaluate", inp=1000)
    _run(db, user, 0.02, vn(2026, 11, 18, 8), cache_read=3000, inp=1000)
    _run(db, user, 9.0, vn(2026, 10, 30, 10))  # tháng trước
    return user


def test_dashboard_cards_match_app_shape(db, seeded):
    data = service.dashboard(db, seeded, date(2026, 11, 18))
    cards = data["cards"]
    assert set(cards) == {"expense", "calendar", "tasks", "inbox", "ai", "devices", "health"}
    assert all(c["status"] == "ok" for k, c in cards.items() if k != "health")
    assert cards["health"] == {"status": "disabled", "data": None, "message": "Có ở bản V2."}

    exp = cards["expense"]["data"]
    assert (exp["period"], exp["total_vnd"], exp["previous_total_vnd"]) == ("2026-11", 345_000, 200_000)
    assert exp["income_vnd"] == 15_000_000 and exp["top_categories"][0]["total_vnd"] == 300_000

    cal = cards["calendar"]["data"]
    assert cal["week_events"] == 2 and cal["next_event"]["title"] == "Họp quý"
    assert cards["tasks"]["data"] == {"overdue": 1, "today": 1, "open": 3}
    assert cards["inbox"]["data"] == {"important_unseen": 1, "new_count": 3}
    ai = cards["ai"]["data"]
    assert (ai["month_usd"], ai["today_usd"], ai["monthly_warn_usd"]) == (0.52, 0.02, 200)
    dev = cards["devices"]["data"]["items"]
    assert len(dev) == 1 and set(dev[0]) == {
        "id",
        "name",
        "listener_connected",
        "last_event_at",
        "otp_blocked_today",
        "last_seen_at",
    }


def test_failed_card_does_not_break_others(db, seeded, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("hỏng")

    monkeypatch.setattr(service.task, "list_tasks", boom)
    cards = service.dashboard(db, seeded)["cards"]
    assert cards["tasks"]["status"] == "error" and cards["tasks"]["data"] is None
    assert cards["tasks"]["message"]
    assert cards["expense"]["status"] == "ok" and cards["ai"]["status"] == "ok"


def test_ai_cost_month_breakdown(db, seeded):
    cost = service.ai_cost(db, seeded, date(2026, 11, 1))
    assert cost["total_usd"] == 0.52 and cost["today_usd"] == 0.02
    assert len(cost["by_day"]) == 18 and cost["by_day"][1] == {"date": date(2026, 11, 2), "usd": 0.5}
    assert cost["by_model"][0] == {"model": "claude-sonnet-5-5", "usd": 0.5}
    assert {p["purpose"] for p in cost["by_purpose"]} == {"trip_evaluate", "chat"}
    assert cost["cache_read_ratio"] == pytest.approx(3000 / 5000, abs=0.001)
    past = service.ai_cost(db, seeded, date(2026, 10, 1))
    assert past["total_usd"] == 9.0 and len(past["by_day"]) == 31


def test_ai_cost_other_user_sees_nothing(db, seeded):
    from app.core.context import UserContext

    other = UserContext(user_id=seeded.user_id + 999, timezone="Asia/Ho_Chi_Minh")
    cost = service.ai_cost(db, other, date(2026, 11, 1))
    assert cost["total_usd"] == 0 and cost["by_model"] == [] and cost["cache_read_ratio"] is None


def test_api_dashboard_and_ai_cost(client, seeded, monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: datetime.now(UTC))  # mã đăng nhập theo giờ thật
    login = client.post(
        "/api/v1/auth/login", json={"email": "dai.ca@example.com", "password": "matkhau-thu-123"}
    )
    client.headers["Authorization"] = f"Bearer {login.json()['data']['access_token']}"
    auth_client = client
    resp = auth_client.get("/api/v1/reports/dashboard", params={"date": "2026-11-18"})
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["date"] == "2026-11-18" and body["cards"]["expense"]["data"]["total_vnd"] == 345_000
    resp = auth_client.get("/api/v1/reports/ai-cost", params={"month": "2026-11"})
    assert resp.status_code == 200 and resp.json()["data"]["total_usd"] == 0.52
    assert auth_client.get("/api/v1/reports/ai-cost", params={"month": "11-2026"}).status_code == 400


# ---------- get_report ----------


@pytest.fixture
def ctx(db, seeded):
    return ToolContext(session=db, user=seeded, conversation_id=None, now=NOW)


def _report(ctx, **data):
    spec = tools.TOOLS[0]
    return spec.run(ctx, spec.input_model.model_validate(data))


def test_get_report_ai_cost_opens_cost_screen(ctx):
    out = _report(ctx, kind="ai_cost")
    assert out.result["total_usd"] == 0.52 and out.result["month"] == "2026-11"
    assert out.actions[0]["screen"] == "settings_ai_cost"


def test_get_report_expense_custom_range(ctx):
    out = _report(ctx, kind="expense_overview", **{"from": "2026-11-01", "to": "2026-11-05"})
    assert out.result["total_expense_vnd"] == 45_000 and out.result["total_income_vnd"] == 15_000_000
    month = _report(ctx, kind="expense_overview")
    assert month.result["total_vnd"] == 345_000 and month.actions[0]["screen"] == "report"


def test_get_report_week_and_inbox(ctx):
    week = _report(ctx, kind="week_overview")
    assert [e["title"] for e in week.result["events"]] == ["Ăn tối", "Họp quý"]
    assert week.result["tasks"]["overdue"] == 1
    pending = _report(ctx, kind="inbox_pending")
    assert pending.contains_third_party and pending.result["important_unseen"] == 1
    assert pending.result["conversations"][0]["importance"] == "important"


def test_tool_schema_uses_from_alias():
    schema = tools.GetReportInput.model_json_schema()
    assert "from" in schema["properties"] and "from_" not in schema["properties"]


def test_inbox_pending_keeps_important_when_many_newer(ctx, db, user):
    """Danh sách hội thoại xếp theo tin mới nhất: tin quan trọng cũ hơn vẫn phải có trong báo cáo."""
    for i in range(tools.MAX_CONVERSATIONS + 2):
        _zalo(db, user, f"Nhóm {i}", f"tin {i}", 30 + i)  # mới hơn tin của Mẹ
    out = _report(ctx, kind="inbox_pending")
    convs = out.result["conversations"]
    assert len(convs) == tools.MAX_CONVERSATIONS
    assert convs[0]["importance"] == "important" and convs[0]["title"] == "Mẹ"
