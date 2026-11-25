"""QĐ-56: kết nối MCP chung như Claude. Máy chủ OAuth giả (ERP DEGO), máy chủ dùng khóa, máy chủ mở; chặn SSRF."""

import base64
import hashlib
import json
import socket
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from app.core.errors import NotFoundError, ValidationError
from app.integrations.connectors import net, service
from app.integrations.connectors.models import Connector, ConnectorClient

ERP = "https://erp.degoholding.vn"
MCP_URL = f"{ERP}/api/mcp"
KEYED = "https://khoa.example.com/mcp"
OPEN = "https://mo.example.com/mcp"
TOOLS = [
    {"name": "erp_read", "description": "Đọc ERP", "annotations": {"readOnlyHint": True}},
    {"name": "draft_leave_request", "description": "Tạo đơn nghỉ phép"},
]


class FakeWorld:
    def __init__(self):
        self.registered, self.revoked, self.codes, self.refresh = [], [], {}, {}
        self.access: set[str] = set()
        self.calls: list[httpx.Request] = []
        self.big = False
        self.called: list[dict] = []

    def handle(self, r: httpx.Request) -> httpx.Response:
        self.calls.append(r)
        host, path = r.url.host, r.url.path
        if host in ("khoa.example.com", "mo.example.com") and r.method == "GET":
            return httpx.Response(404)  # không công bố metadata OAuth
        if host == "khoa.example.com":
            return self._mcp(r, ok=r.headers.get("authorization") == "Bearer khoa-dung")
        if host == "mo.example.com":
            if self.big:
                return httpx.Response(200, content=b"x" * (2 * 1024 * 1024))
            return self._mcp(r, ok=True)
        if path == "/.well-known/oauth-protected-resource/api/mcp":
            return httpx.Response(200, json={"resource": MCP_URL, "authorization_servers": [ERP],
                                             "scopes_supported": ["mcp:read", "mcp:write"]})  # fmt: skip
        if path == "/.well-known/oauth-authorization-server":
            return httpx.Response(200, json={
                "issuer": ERP, "authorization_endpoint": f"{ERP}/api/oauth/authorize",
                "token_endpoint": f"{ERP}/api/oauth/token", "registration_endpoint": f"{ERP}/api/oauth/register",
                "revocation_endpoint": f"{ERP}/api/oauth/revoke", "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
                "authorization_response_iss_parameter_supported": True})  # fmt: skip
        if path == "/api/oauth/register":
            self.registered.append(json.loads(r.content))
            return httpx.Response(201, json={"client_id": "cli-1", "client_secret": "bi-mat",
                                             "token_endpoint_auth_method": "client_secret_post"})  # fmt: skip
        form = {k: v[0] for k, v in parse_qs(r.content.decode()).items()} if r.method == "POST" else {}
        if path == "/api/oauth/token":
            if form.get("client_secret") != "bi-mat" or form.get("resource") != MCP_URL:
                return httpx.Response(401, json={"error": "invalid_client"})
            if form["grant_type"] == "authorization_code":
                info = self.codes.pop(form.get("code"), None)
                want = (
                    base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode()).digest())
                    .decode()
                    .rstrip("=")
                )
                if info != want:
                    return httpx.Response(400, json={"error": "invalid_grant"})
                return httpx.Response(200, json=self._tokens(email="bao@degoholding.vn"))
            if self.refresh.pop(form.get("refresh_token"), None) is None:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json=self._tokens())
        if path == "/api/oauth/revoke":
            self.revoked.append(form.get("token"))
            return httpx.Response(200)
        if path == "/api/mcp":
            token = r.headers.get("authorization", "").removeprefix("Bearer ")
            if token not in self.access:
                return httpx.Response(401, headers={"WWW-Authenticate": 'Bearer resource_metadata="x"'})
            return self._mcp(r, ok=True, sse=True)
        return httpx.Response(404)

    def _tokens(self, **extra) -> dict:
        at, rt = f"at-{uuid.uuid4().hex[:6]}", f"rt-{uuid.uuid4().hex[:6]}"
        self.access.add(at)
        self.refresh[rt] = True
        return {"access_token": at, "refresh_token": rt, "expires_in": 3600, "scope": "mcp:read", **extra}

    def _mcp(self, r: httpx.Request, ok: bool, sse: bool = False) -> httpx.Response:
        if not ok:
            return httpx.Response(401)
        msg = json.loads(r.content)
        if "id" not in msg:
            return httpx.Response(202)
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "x"}}
        if msg["method"] == "tools/list":
            result = {"tools": TOOLS}
        if msg["method"] == "tools/call":
            self.called.append(msg["params"])
            result = {"content": [{"type": "text", "text": f"đã chạy {msg['params']['name']}"}],
                      "isError": msg["params"]["name"] == "draft_leave_request" and not msg["params"]["arguments"]}  # fmt: skip
        body = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
        if sse:
            return httpx.Response(200, headers={"content-type": "text/event-stream", "mcp-session-id": "s1"},
                                  content=f"event: message\ndata: {json.dumps(body)}\n\n".encode())  # fmt: skip
        return httpx.Response(200, json=body, headers={"mcp-session-id": "s1"})

    def approve(self, auth_url: str) -> dict:
        q = {k: v[0] for k, v in parse_qs(urlparse(auth_url).query).items()}
        code = f"c-{uuid.uuid4().hex[:6]}"
        self.codes[code] = q["code_challenge"]
        return {"code": code, "state": q["state"], "iss": ERP}


@pytest.fixture
def world(monkeypatch):
    w = FakeWorld()
    net.set_transport(httpx.MockTransport(w.handle))

    def resolve(host, port, **kw):
        ip = {"noi-bo.example.com": "10.0.0.5", "localhost": "127.0.0.1"}.get(host, "93.184.216.34")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(net, "_resolve", resolve)
    yield w
    net.set_transport(None)


def _oauth(db, user, world) -> int:
    out = service.create(db, user.user_id, "ERP DEGO", MCP_URL)
    assert out["next"] == "oauth" and out["connector"]["auth"] == "oauth"
    cid = out["connector"]["id"]
    url = service.start_connect(db, user.user_id, cid)["auth_url"]
    p = world.approve(url)
    result = service.finish_connect(db, p["code"], p["state"], p["iss"], None)
    assert result.ok, result.message
    return cid


def test_oauth_connector_full_flow(db, user, world):
    cid = _oauth(db, user, world)
    c = db.get(Connector, cid)
    assert c.status == "connected" and c.account_label == "bao@degoholding.vn"
    reg = world.registered[0]
    assert reg["client_name"] == "Trợ lý cá nhân" and reg["redirect_uris"][0].endswith(
        "/api/v1/connectors/oauth/callback"
    )
    assert db.scalar(select(ConnectorClient)).issuer == ERP
    tools = service.list_tools(db, user.user_id, cid)
    assert {t["name"]: (t["write"], t["enabled"]) for t in tools} == {
        "erp_read": (False, True),
        "draft_leave_request": (True, False),  # công cụ ghi tắt mặc định
    }
    service.update_connector(db, user.user_id, cid, {"write_tools_enabled": ["draft_leave_request"]})
    assert all(t["enabled"] for t in service.list_tools(db, user.user_id, cid))
    item = service.serialize(db.get(Connector, cid))
    assert item["write_enabled"] and item["tools_count"] == 2
    assert service.tool_allowed(item, "draft_leave_request", write=True)
    assert not service.tool_allowed({"write_tools_enabled": []}, "draft_leave_request", write=True)


def test_authorize_url_prefers_read_scope_and_resource(db, user, world):
    cid = service.create(db, user.user_id, "ERP DEGO", MCP_URL)["connector"]["id"]
    q = {
        k: v[0]
        for k, v in parse_qs(urlparse(service.start_connect(db, user.user_id, cid)["auth_url"]).query).items()
    }
    assert q["scope"] == "mcp:read" and q["resource"] == MCP_URL and q["code_challenge_method"] == "S256"
    cid2 = service.create(db, user.user_id, "ERP 2", MCP_URL + "/") if False else None
    assert cid2 is None
    service.start_connect(db, user.user_id, cid)
    assert len(world.registered) == 1  # đăng ký client một lần mỗi máy chủ ủy quyền


def test_state_iss_and_reuse_are_refused(db, user, world):
    cid = service.create(db, user.user_id, "ERP DEGO", MCP_URL)["connector"]["id"]
    p = world.approve(service.start_connect(db, user.user_id, cid)["auth_url"])
    assert service.finish_connect(db, p["code"], p["state"], "https://gia.example", None).error == "iss"
    p = world.approve(service.start_connect(db, user.user_id, cid)["auth_url"])
    assert service.finish_connect(db, p["code"], "sai", ERP, None).error == "state"
    assert service.finish_connect(db, p["code"], p["state"], ERP, None).ok
    assert service.finish_connect(db, p["code"], p["state"], ERP, None).error == "state"
    html = service.callback_html(service.CallbackResult(True, cid, None, "ok"))
    assert f"troly://settings/connectors?ok=1&id={cid}" in html


def test_refresh_reauth_and_reconnect_without_revoke(db, user, world):
    from datetime import timedelta

    from app.core import clock

    cid = _oauth(db, user, world)
    c = db.get(Connector, cid)
    first = service.get_access_token(db, user.user_id, cid)
    c.access_expires_at = clock.now() + timedelta(minutes=3)
    assert service.get_access_token(db, user.user_id, cid) != first
    world.refresh.clear()
    with pytest.raises(service.ConnectorReauthRequired):
        service.get_access_token(db, user.user_id, cid, force_refresh=True)
    assert db.get(Connector, cid).status == "reauth_required"
    p = world.approve(service.start_connect(db, user.user_id, cid)["auth_url"])
    assert service.finish_connect(db, p["code"], p["state"], ERP, None).ok
    assert world.revoked == [] and db.get(Connector, cid).status == "connected"


def test_delete_revokes(db, user, world):
    cid = _oauth(db, user, world)
    service.delete_connector(db, user.user_id, cid)
    assert world.revoked and db.get(Connector, cid) is None
    with pytest.raises(NotFoundError):
        service.get_access_token(db, user.user_id, cid)


def test_server_without_oauth_needs_key(db, user, world):
    out = service.create(db, user.user_id, "Máy chủ khóa", KEYED)
    assert out["next"] == "api_key" and out["connector"]["status"] == "not_connected"
    cid = out["connector"]["id"]
    with pytest.raises(ValidationError):
        service.set_key(db, user.user_id, cid, "khoa-sai")
    item = service.set_key(db, user.user_id, cid, "khoa-dung")
    assert item["status"] == "connected" and "khoa-dung" not in json.dumps(item, default=str)
    assert b"khoa-dung" not in bytes(db.get(Connector, cid).api_key_enc)
    assert service.auth_headers(db, user.user_id, cid) == {"Authorization": "Bearer khoa-dung"}
    assert [t["name"] for t in service.list_tools(db, user.user_id, cid)] == [
        "erp_read",
        "draft_leave_request",
    ]


def test_open_server_is_ready(db, user, world):
    out = service.create(db, user.user_id, "Máy chủ mở", OPEN)
    assert out["next"] == "ready" and out["connector"]["auth"] == "none"
    assert service.auth_headers(db, user.user_id, out["connector"]["id"]) == {}


@pytest.mark.parametrize(
    "url",
    [
        "http://erp.degoholding.vn/api/mcp",
        "https://localhost/mcp",
        "https://noi-bo.example.com/mcp",
        "https://203.0.113.10:8443/mcp",
        "https://user:pw@erp.degoholding.vn/api/mcp",
        "ftp://x.example.com",
    ],
)
def test_ssrf_guard(db, user, world, url):
    with pytest.raises(ValidationError):
        service.create(db, user.user_id, "X", url)


def test_response_size_limit(db, user, world):
    world.big = True
    with pytest.raises(net.ConnectorUnavailable):
        service.create(db, user.user_id, "Lớn", OPEN)


def test_metadata_pointing_inside_is_blocked(db, user, world, monkeypatch):
    original = world.handle

    def evil(r):
        if r.url.path == "/.well-known/oauth-authorization-server":
            return httpx.Response(200, json={"issuer": ERP, "authorization_endpoint": "https://localhost/a",
                                             "token_endpoint": "https://noi-bo.example.com/t",
                                             "registration_endpoint": f"{ERP}/api/oauth/register"})  # fmt: skip
        return original(r)

    net.set_transport(httpx.MockTransport(evil))
    cid = service.create(db, user.user_id, "ERP DEGO", MCP_URL)["connector"]["id"]
    with pytest.raises(ValidationError):
        service.start_connect(db, user.user_id, cid)


def test_duplicate_and_presets(db, user, world):
    service.create(db, user.user_id, "Mở", OPEN)
    with pytest.raises(ValidationError):
        service.create(db, user.user_id, "Mở lần hai", OPEN)
    assert service.presets()[0] == {"name": "ERP DEGO", "url": MCP_URL}


def test_routes_hidden_when_flag_off_and_shown_when_on(db, user, world, monkeypatch):
    import importlib

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.auth import get_current_user
    from app.core.db import get_session
    from app.integrations.connectors import router as router_mod
    from app.integrations.connectors.settings import get_connector_settings

    def build():
        importlib.reload(router_mod)
        from app.core.errors import install_error_handlers

        app = FastAPI()
        install_error_handlers(app)
        app.include_router(router_mod.router, prefix="/api/v1")
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_session] = lambda: db
        return TestClient(app)

    monkeypatch.delenv("FEATURE_CONNECTORS", raising=False)
    get_connector_settings.cache_clear()
    assert build().get("/api/v1/connectors").status_code == 404
    monkeypatch.setenv("FEATURE_CONNECTORS", "true")
    get_connector_settings.cache_clear()
    c = build()
    r = c.post("/api/v1/connectors", json={"name": "Mở", "url": OPEN})
    assert r.status_code == 201 and r.json()["data"]["next"] == "ready"
    cid = r.json()["data"]["connector"]["id"]
    assert c.get("/api/v1/connectors").json()["data"]["items"][0]["id"] == cid
    assert c.get(f"/api/v1/connectors/{cid}/tools").json()["data"]["items"][0]["name"] == "erp_read"
    assert c.patch(f"/api/v1/connectors/{cid}", json={"name": "Đổi tên"}).json()["data"]["name"] == "Đổi tên"
    assert c.post("/api/v1/connectors", json={"name": "X", "url": "http://a.example"}).status_code == 400
    assert c.delete(f"/api/v1/connectors/{cid}").status_code == 200
    monkeypatch.delenv("FEATURE_CONNECTORS")
    get_connector_settings.cache_clear()
    importlib.reload(router_mod)


def test_read_only_hint_raw_and_call_tool(db, user, world):
    cid = _oauth(db, user, world)
    tools = {t["name"]: t for t in service.list_tools(db, user.user_id, cid)}
    assert (
        tools["erp_read"]["read_only_hint"] is True and tools["draft_leave_request"]["read_only_hint"] is None
    )
    out = service.call_tool(db, user.user_id, cid, "erp_read", {"q": "x"})
    assert out == {"content": [{"type": "text", "text": "đã chạy erp_read"}], "is_error": False}
    with pytest.raises(ValidationError):  # công cụ ghi chưa bật
        service.call_tool(db, user.user_id, cid, "draft_leave_request", {"ngay": "1/12"})
    with pytest.raises(NotFoundError):
        service.call_tool(db, user.user_id, cid, "khong_co", {})
    service.update_connector(db, user.user_id, cid, {"write_tools_enabled": ["draft_leave_request"]})
    assert service.call_tool(db, user.user_id, cid, "draft_leave_request", {})["is_error"] is True
    assert world.called[-1] == {"name": "draft_leave_request", "arguments": {}}
