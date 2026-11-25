"""Công cụ connect_service, list_connections (QĐ-56, agent AI) trên service giả theo hợp đồng của agent Google."""

import importlib
import sys
import types
from datetime import UTC, datetime

import pytest

from app.ai.redact import PASSWORD_MASK, mask_secrets
from app.ai.schemas import ToolContext
from app.ai.tests.conftest import FakeUser

ERP_URL = "https://erp.degoholding.vn/api/mcp"
DEV_URL = "https://deverp.degoholding.vn/api/mcp"


@pytest.fixture
def svc(monkeypatch):
    state = {"rows": [], "created": []}
    mod = types.ModuleType("app.integrations.connectors.service")
    mod.list_connectors = lambda session, user_id: [dict(r) for r in state["rows"]]

    def create(session, user_id, name, url):
        state["created"].append((name, url))
        row = {"id": 40 + len(state["created"]), "name": name, "url": url, "status": "not_connected"}
        state["rows"].append(row)
        return {"connector": row, "next": "oauth"}

    mod.create = create
    mod.presets = lambda: [
        {"name": "ERP DEGO", "url": ERP_URL},
        {"name": "ERP DEGO (thử nghiệm)", "url": DEV_URL},
    ]
    monkeypatch.setitem(sys.modules, "app.integrations.connectors.service", mod)
    import app.integrations.connectors as pkg

    monkeypatch.setattr(pkg, "service", mod, raising=False)
    sys.modules.pop("app.integrations.connectors.tools", None)
    tools = importlib.import_module("app.integrations.connectors.tools")

    yield state, tools
    sys.modules.pop("app.integrations.connectors.tools", None)


def _call(tools, tool_name, **data):
    spec = next(t for t in tools.TOOLS if t.name == tool_name)
    ctx = ToolContext(
        session=None, user=FakeUser(), conversation_id=None, now=datetime(2026, 11, 25, tzinfo=UTC)
    )
    return spec.run(ctx, spec.input_model.model_validate(data))


def test_connect_erp_uses_preset_and_returns_login_button(svc):
    state, tools = svc
    out = _call(tools, "connect_service", name="ERP DEGO")
    assert state["created"] == [("ERP DEGO", ERP_URL)]
    assert out.result["trang_thai"] == "da_them" and "trang của hệ thống" in out.result["ghi_chu"]
    assert out.actions == [{"type": "connect", "label": "Kết nối ERP DEGO", "connector_id": 41}]


def test_connect_dev_preset_and_unknown_name(svc):
    state, tools = svc
    _call(tools, "connect_service", name="ERP DEGO thử nghiệm")
    assert state["created"] == [("ERP DEGO thử nghiệm", DEV_URL)]
    out = _call(tools, "connect_service", name="Jira công ty")
    assert out.result["trang_thai"] == "can_dia_chi"
    assert out.actions == [{"type": "connect", "label": "Thêm kết nối Jira công ty", "name": "Jira công ty"}]
    assert len(state["created"]) == 1  # không tạo khi chưa biết địa chỉ


def test_connect_existing_does_not_duplicate(svc):
    state, tools = svc
    state["rows"] = [{"id": 7, "name": "ERP DEGO", "url": ERP_URL + "/", "status": "reauth_required"}]
    out = _call(tools, "connect_service", name="ERP")
    assert state["created"] == [] and out.result["trang_thai"] == "can_dang_nhap"
    assert out.actions[0]["connector_id"] == 7
    state["rows"][0]["status"] = "connected"
    done = _call(tools, "connect_service", name="ERP DEGO")
    assert done.result["trang_thai"] == "da_noi" and done.actions == []


def test_list_connections_offers_reconnect(svc):
    state, tools = svc
    state["rows"] = [
        {"id": 7, "name": "ERP DEGO", "url": ERP_URL, "status": "connected", "account": "bao@dego",
         "tools_count": 60, "write_tools_enabled": []},
        {"id": 8, "name": "CRM", "url": "https://crm.example.com/mcp", "status": "reauth_required"},
    ]  # fmt: skip
    out = _call(tools, "list_connections")
    assert [(i["connector_id"], i["trang_thai"]) for i in out.result["items"]] == [
        (7, "connected"),
        (8, "reauth_required"),
    ]
    assert out.actions == [{"type": "connect", "label": "Kết nối lại CRM", "connector_id": 8}]


@pytest.mark.parametrize(
    "text",
    ["mật khẩu là Bao@2026xyz", "password: hunter22", "pass=abcd1234", "mk: Dego#2026"],
)
def test_password_pasted_is_masked(text):
    masked, found = mask_secrets(text)
    assert found and PASSWORD_MASK in masked


@pytest.mark.parametrize("text", ["anh quên mật khẩu rồi", "đổi mật khẩu ERP thế nào", "mật khẩu là gì"])
def test_password_talk_not_masked(text):
    assert mask_secrets(text) == (text, False)


def _ctx():
    return ToolContext(
        session=None, user=FakeUser(), conversation_id=None, now=datetime(2026, 11, 25, tzinfo=UTC)
    )


def _spec(tools, name):
    return next(t for t in tools.TOOLS if t.name == name)


def test_write_tool_needs_card_and_runs_only_on_execute(svc):
    state, tools = svc
    calls = []
    sys.modules["app.integrations.connectors.service"].tool_allowed = lambda c, name, write: (
        (not write) or name in (c.get("write_tools_enabled") or [])
    )

    def call_tool(session, user_id, cid, name, arguments):
        calls.append((cid, name, arguments))
        return {"content": [{"type": "text", "text": "Đã tạo đơn NP-12."}], "is_error": False}

    sys.modules["app.integrations.connectors.service"].call_tool = call_tool
    state["rows"] = [{"id": 7, "name": "ERP DEGO", "url": ERP_URL, "status": "connected",
                      "write_tools_enabled": ["draft_leave_request"]}]  # fmt: skip
    spec = _spec(tools, "call_connector_tool")
    assert spec.needs_approval(None) is True
    data = spec.input_model.model_validate(
        {
            "connector_id": 7,
            "tool": "draft_leave_request",
            "arguments_json": '{"days": 2}',
            "reason": "Nghỉ 2 ngày",
        }
    )
    draft = spec.prepare(_ctx(), data)
    assert draft.input == {"connector_id": 7, "tool": "draft_leave_request", "arguments": {"days": 2}}
    assert draft.danger is True and {"label": "Hệ thống", "value": "ERP DEGO"} in draft.details
    assert calls == []  # chuẩn bị thẻ không gọi hệ thống
    out = spec.execute(_ctx(), draft.input)
    assert calls == [(7, "draft_leave_request", {"days": 2})]
    assert out.result == {"loi": False, "du_lieu_ngoai": "Đã tạo đơn NP-12."} and out.contains_third_party

    off = spec.input_model.model_validate(
        {"connector_id": 7, "tool": "confirm_draft", "arguments_json": "{}", "reason": "x"}
    )
    with pytest.raises(Exception) as exc:
        spec.prepare(_ctx(), off)
    assert exc.value.code == "VALIDATION_ERROR"
    bad = spec.input_model.model_validate(
        {"connector_id": 7, "tool": "draft_leave_request", "arguments_json": "[1", "reason": "x"}
    )
    with pytest.raises(Exception) as exc:
        spec.prepare(_ctx(), bad)
    assert exc.value.code == "VALIDATION_ERROR"


def test_run_recorder_saves_mcp_servers_used(db, user):
    from decimal import Decimal

    from app.ai.client import RunRecord
    from app.ai.models import AiRun, DbRunRecorder
    from app.ai.pricing import UsageCount

    rec = RunRecord(
        user_id=user.user_id, purpose="chat", model="claude-haiku-5-5", mode="chat", effort="medium",
        conversation_id=None, usage=UsageCount(), cost_usd=Decimal(0), rate_card=None, stop_reason="end_turn",
        refusal_category=None, latency_ms=1, request_id=None, error_code=None, fallback_used=False,
        mcp_servers_used=["c3", "c5"],
    )  # fmt: skip
    run_id = DbRunRecorder(session_factory=lambda: _NoClose(db)).record(rec)
    assert db.get(AiRun, run_id).mcp_servers_used == ["c3", "c5"]


class _NoClose:
    """Dùng phiên của bài kiểm (giao dịch bị lùi khi xong) thay cho phiên riêng của recorder."""

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def add(self, row):
        self.db.add(row)

    def commit(self):
        self.db.flush()
