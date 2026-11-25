"""Kết nối MCP chung như Claude (QĐ-56, thay QĐ-55).

Người dùng thêm một máy chủ MCP bằng tên và URL. Máy chủ dò:
1. /.well-known/oauth-protected-resource (RFC 9728, thử có hậu tố đường dẫn rồi gốc); không có thì gọi
   initialize không xác thực: 200 là không cần xác thực; 401 có `resource_metadata` trong WWW-Authenticate
   thì đọc metadata đó; 401 không có thì cần dán khóa.
2. OAuth: metadata máy chủ ủy quyền (RFC 8414), đăng ký client động (RFC 7591) một lần mỗi issuer, mã ủy
   quyền + PKCE S256 + resource (RFC 8707), callback kiểm state và iss (RFC 9207).
3. Token mã hóa Fernet gắn user_id. get_access_token tự làm mới dưới khóa tư vấn; invalid_grant thì cần nối
   lại; nối lại không thu hồi mã cũ (bài học Google 19/11). Xóa kết nối thì thu hồi rồi xóa.
Mọi lời gọi ra ngoài qua net.send (chống SSRF, giới hạn 1 MB, 10 giây).
"""

import base64
import hashlib
import json
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode, urlsplit, urlunsplit

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import AppError, NotFoundError, ValidationError
from app.core.security import decrypt_bound, encrypt_bound, sha256_hex
from app.integrations.connectors import mcp, net
from app.integrations.connectors.models import Connector, ConnectorClient, ConnectorOAuthState
from app.integrations.connectors.settings import CLIENT_NAME, DEEP_LINK, PRESETS, get_connector_settings

log = logging.getLogger("troly.connectors")

PROVIDER = "connector"
PKCE_PROVIDER = "connector_pkce"
CLIENT_PROVIDER = "connector_client"
SYSTEM_USER = 0
STATE_MINUTES = 10
REFRESH_MARGIN = timedelta(minutes=5)
TOKEN_LOCK_NAMESPACE = 7444
MAX_CONNECTORS = 20
ConnectorUnavailable = net.ConnectorUnavailable


class ConnectorReauthRequired(AppError):
    status = 409
    code = "CONNECTOR_REAUTH_REQUIRED"
    message = "Kết nối đã hết hạn, hãy bấm Kết nối lại."


class ConnectorNotReady(AppError):
    status = 409
    code = "CONNECTOR_NOT_CONNECTED"
    message = "Kết nối chưa sẵn sàng."


# ---------- Đọc, hiển thị ----------


def serialize(c: Connector) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "url": c.url,
        "auth": c.auth,
        "status": c.status,
        "account": c.account_label,
        "last_error": c.last_error,
        "write_tools_enabled": list(c.write_tools_enabled or []),
        "write_enabled": bool(c.write_tools_enabled),
        "tools_count": c.tools_count,
        "access_expires_at": c.access_expires_at,
        "connected_at": c.connected_at,
        "created_at": c.created_at,
    }


def list_connectors(session: Session, user_id: int) -> list[dict]:
    rows = session.scalars(select(Connector).where(Connector.user_id == user_id).order_by(Connector.id))
    return [serialize(c) for c in rows]


def presets() -> list[dict]:
    return [dict(p) for p in PRESETS]


def _get(session: Session, user_id: int, connector_id: int, lock: bool = False) -> Connector:
    stmt = select(Connector).where(Connector.id == connector_id, Connector.user_id == user_id)
    c = session.scalar(stmt.with_for_update() if lock else stmt)
    if c is None:
        raise NotFoundError("Không tìm thấy kết nối.")
    return c


# ---------- Dò máy chủ ----------


def _well_known(base_url: str, name: str) -> list[str]:
    parts = urlsplit(base_url)
    path = parts.path.rstrip("/")
    urls = [urlunsplit((parts.scheme, parts.netloc, f"/.well-known/{name}{path}", "", ""))]
    if path:
        urls.append(urlunsplit((parts.scheme, parts.netloc, f"/.well-known/{name}", "", "")))
    return urls


def _json_from(urls: list[str]) -> dict | None:
    for url in urls:
        try:
            r = net.send("GET", url)
        except ValidationError:
            continue
        if r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                continue
    return None


def _as_metadata(prm: dict) -> tuple[str, dict]:
    servers = prm.get("authorization_servers") or []
    if not servers:
        raise ValidationError("Máy chủ không ghi máy chủ ủy quyền.")
    issuer = servers[0].rstrip("/")
    meta = _json_from(
        _well_known(issuer, "oauth-authorization-server") + _well_known(issuer, "openid-configuration")
    )
    if not meta or (meta.get("issuer") or "").rstrip("/") != issuer:
        raise ValidationError("Metadata máy chủ ủy quyền không đọc được hoặc không khớp.")
    if "S256" not in (meta.get("code_challenge_methods_supported") or ["S256"]):
        raise ValidationError("Máy chủ không hỗ trợ PKCE S256.")
    meta["_resource_scopes"] = prm.get("scopes_supported") or []
    return issuer, meta


def probe(url: str) -> tuple[str, str | None, dict]:
    """Trả (auth, issuer, metadata). auth: oauth | api_key | none. Không phải MCP thì ValidationError."""
    prm = _json_from(_well_known(url, "oauth-protected-resource"))
    if prm is None:
        r, _ = mcp.initialize(url, None)
        if r.status_code == 200:
            return "none", None, {}
        if r.status_code in (401, 403):
            m = re.search(r'resource_metadata="([^"]+)"', r.headers.get("www-authenticate", ""))
            prm = _json_from([m.group(1)]) if m else None
            if prm is None:
                return "api_key", None, {}
        else:
            raise ValidationError("Địa chỉ này không phải máy chủ MCP.", fields={"url": "Không phải MCP."})
    issuer, meta = _as_metadata(prm)
    return "oauth", issuer, meta


def create(session: Session, user_id: int, name: str, url: str) -> dict:
    """POST /connectors: trả `{connector, next}`; next oauth (bấm Kết nối), api_key (dán khóa), ready."""
    name = (name or "").strip()[:100]
    if not name:
        raise ValidationError(fields={"name": "Nhập tên kết nối."})
    url = net.check_url(url)
    if session.scalar(select(Connector.id).where(Connector.user_id == user_id, Connector.url == url)):
        raise ValidationError("Kết nối này đã có.", fields={"url": "Đã có."})
    count = session.scalar(select(func.count()).select_from(Connector).where(Connector.user_id == user_id))
    if count >= MAX_CONNECTORS:
        raise ValidationError(f"Tối đa {MAX_CONNECTORS} kết nối.")
    auth, issuer, meta = probe(url)
    c = Connector(user_id=user_id, name=name, url=url, auth=auth, issuer=issuer, as_metadata=meta)
    if auth == "none":
        c.status, c.connected_at = "connected", clock.now()
    session.add(c)
    session.flush()
    return {
        "connector": serialize(c),
        "next": {"oauth": "oauth", "api_key": "api_key", "none": "ready"}[auth],
    }


# ---------- OAuth ----------


def _client_for(session: Session, c: Connector) -> ConnectorClient:
    redirect_uri = get_connector_settings().redirect_uri
    row = session.scalar(
        select(ConnectorClient).where(
            ConnectorClient.issuer == c.issuer, ConnectorClient.redirect_uri == redirect_uri
        )
    )
    if row is not None:
        return row
    meta = c.as_metadata
    endpoint = meta.get("registration_endpoint")
    if not endpoint:
        raise ValidationError("Máy chủ không cho đăng ký ứng dụng tự động.")
    methods = meta.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
    auth_method = (
        "client_secret_post"
        if "client_secret_post" in methods
        else ("none" if "none" in methods else methods[0])
    )
    r = net.send(
        "POST",
        endpoint,
        json={
            "client_name": CLIENT_NAME,
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": auth_method,
        },
    )
    if r.status_code not in (200, 201):
        log.warning("Đăng ký client kết nối lỗi", extra={"status": r.status_code})
        raise ConnectorUnavailable("Đăng ký với máy chủ không thành công.")
    reg = r.json()
    secret = reg.get("client_secret")
    enc, version = encrypt_bound(SYSTEM_USER, CLIENT_PROVIDER, secret) if secret else (None, None)
    row = ConnectorClient(
        issuer=c.issuer,
        redirect_uri=redirect_uri,
        client_id=reg["client_id"],
        client_secret_enc=enc,
        key_version=version,
        auth_method=reg.get("token_endpoint_auth_method") or auth_method,
        registered_at=clock.now(),
    )
    session.add(row)
    session.flush()
    return row


def _client_auth(client: ConnectorClient, form: dict) -> dict:
    form = {**form, "client_id": client.client_id}
    secret = (
        decrypt_bound(SYSTEM_USER, CLIENT_PROVIDER, bytes(client.client_secret_enc), client.key_version)
        if client.client_secret_enc
        else None
    )
    if secret and client.auth_method == "client_secret_basic":
        return {"data": form, "auth": (client.client_id, secret)}
    if secret and client.auth_method == "client_secret_post":
        form["client_secret"] = secret
    return {"data": form}


def _read_scope(meta: dict) -> str | None:
    """Ưu tiên scope chỉ đọc nếu máy chủ công bố (mcp:read); không công bố thì không gửi scope."""
    scopes = list(meta.get("_resource_scopes") or []) + list(meta.get("scopes_supported") or [])
    reads = [s for s in scopes if re.search(r"(^|[:._])read($|[:._])", s)]
    return reads[0] if reads else None


def start_connect(session: Session, user_id: int, connector_id: int) -> dict:
    """POST /connectors/{id}/connect (cũng là nối lại): trả `{auth_url}`."""
    c = _get(session, user_id, connector_id)
    if c.auth == "api_key":
        raise ValidationError("Máy chủ này dùng khóa, hãy dán khóa.")
    if c.auth == "none":
        raise ValidationError("Máy chủ này không cần đăng nhập.")
    client = _client_for(session, c)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(32)
    enc, version = encrypt_bound(user_id, PKCE_PROVIDER, verifier)
    session.add(
        ConnectorOAuthState(
            user_id=user_id,
            connector_id=c.id,
            state_hash=sha256_hex(state),
            code_verifier_enc=enc,
            key_version=version,
            expires_at=clock.now() + timedelta(minutes=STATE_MINUTES),
        )
    )
    c.client_row_id = client.id
    session.flush()
    params = {
        "response_type": "code",
        "client_id": client.client_id,
        "redirect_uri": client.redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": c.url,
    }
    scope = _read_scope(c.as_metadata)
    if scope:
        params["scope"] = scope
    endpoint = c.as_metadata["authorization_endpoint"]
    net.check_url(endpoint)
    return {"auth_url": f"{endpoint}?{urlencode(params)}"}


@dataclass
class CallbackResult:
    ok: bool
    connector_id: int | None
    error: str | None  # huy, state, iss, token, loi
    message: str


def _label(token: dict) -> str | None:
    for key in ("email", "username", "user_email", "name"):
        if isinstance(token.get(key), str) and token[key]:
            return token[key]
    user = token.get("user")
    if isinstance(user, dict):
        return user.get("email") or user.get("username") or user.get("name")
    id_token = token.get("id_token")
    if isinstance(id_token, str) and id_token.count(".") == 2:
        try:
            body = id_token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            return claims.get("email") or claims.get("preferred_username")
        except ValueError:
            return None
    return None


def _store(c: Connector, token: dict, keep_refresh: str | None) -> None:
    c.access_token_enc, c.key_version = encrypt_bound(c.user_id, PROVIDER, token["access_token"])
    refresh = token.get("refresh_token") or keep_refresh
    c.refresh_token_enc = encrypt_bound(c.user_id, PROVIDER, refresh)[0] if refresh else None
    expires = token.get("expires_in")
    c.access_expires_at = clock.now() + timedelta(seconds=int(expires)) if expires else None
    c.scope = token.get("scope") or c.scope


def _decrypt(c: Connector, blob: bytes | None) -> str | None:
    return decrypt_bound(c.user_id, PROVIDER, bytes(blob), c.key_version) if blob else None


def finish_connect(
    session: Session, code: str | None, state: str | None, iss: str | None, error: str | None
) -> CallbackResult:
    if not state:
        return CallbackResult(False, None, "state", "Thiếu mã phiên kết nối.")
    row = session.scalar(
        select(ConnectorOAuthState)
        .where(ConnectorOAuthState.state_hash == sha256_hex(state))
        .with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at < clock.now():
        return CallbackResult(
            False, None, "state", "Phiên kết nối đã hết hạn hoặc không hợp lệ, hãy thử lại."
        )
    row.used_at = clock.now()
    c = session.get(Connector, row.connector_id)
    if c is None or c.user_id != row.user_id:
        return CallbackResult(False, None, "state", "Kết nối không còn.")
    if error:
        if error == "access_denied":
            return CallbackResult(False, c.id, "huy", "Đã hủy kết nối.")
        return CallbackResult(False, c.id, "loi", "Máy chủ báo lỗi khi kết nối.")
    supports_iss = bool(c.as_metadata.get("authorization_response_iss_parameter_supported"))
    if (iss or supports_iss) and (iss or "").rstrip("/") != c.issuer:
        log.warning("Sai iss khi nối kết nối", extra={"connector_id": c.id})
        return CallbackResult(False, c.id, "iss", "Phản hồi không đến từ đúng máy chủ.")
    if not code:
        return CallbackResult(False, c.id, "loi", "Máy chủ không trả mã.")
    client = session.get(ConnectorClient, c.client_row_id) if c.client_row_id else None
    if client is None:
        return CallbackResult(False, c.id, "loi", "Chưa đăng ký với máy chủ, hãy thử lại.")
    verifier = decrypt_bound(row.user_id, PKCE_PROVIDER, bytes(row.code_verifier_enc), row.key_version)
    try:
        r = net.send(
            "POST",
            c.as_metadata["token_endpoint"],
            **_client_auth(
                client,
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": client.redirect_uri,
                    "code_verifier": verifier,
                    "resource": c.url,
                },
            ),  # fmt: skip
        )
    except (ConnectorUnavailable, ValidationError):
        return CallbackResult(False, c.id, "token", "Không gọi được máy chủ để đổi mã.")
    token = r.json() if r.status_code == 200 else {}
    if not token.get("access_token"):
        log.warning("Đổi mã kết nối thất bại", extra={"connector_id": c.id, "status": r.status_code})
        return CallbackResult(False, c.id, "token", "Không đổi được mã với máy chủ.")
    _store(c, token, _decrypt(c, c.refresh_token_enc) if c.key_version else None)  # nối lại: không thu hồi
    c.status, c.last_error, c.connected_at = "connected", None, clock.now()
    c.account_label = _label(token) or c.account_label
    session.flush()
    return CallbackResult(True, c.id, None, f"Đã kết nối {c.name}.")


def callback_html(result: CallbackResult) -> str:
    query = {"ok": "1" if result.ok else "0"}
    if result.connector_id is not None:
        query["id"] = str(result.connector_id)
    if result.error:
        query["loi"] = result.error
    target = f"{DEEP_LINK}?{urlencode(query)}"
    msg = result.message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Kết nối</title><meta http-equiv='refresh' content='0;url={target}'></head>"
        f"<body style='font-family:sans-serif;padding:24px'><p>{msg}</p>"
        f"<p><a href='{target}'>Quay về app</a></p></body></html>"
    )


# ---------- Khóa API ----------


def set_key(session: Session, user_id: int, connector_id: int, api_key: str) -> dict:
    """PUT /connectors/{id}/key: thử khóa bằng initialize rồi lưu mã hóa; không bao giờ trả khóa ra."""
    c = _get(session, user_id, connector_id)
    if c.auth != "api_key":
        raise ValidationError("Kết nối này không dùng khóa.")
    api_key = (api_key or "").strip()
    if not api_key or len(api_key) > 4000:
        raise ValidationError(fields={"api_key": "Dán khóa."})
    r, _ = mcp.initialize(c.url, api_key)
    if r.status_code in (401, 403):
        raise ValidationError("Khóa không đúng hoặc đã hết hạn.", fields={"api_key": "Không đúng."})
    if r.status_code != 200:
        raise ConnectorUnavailable(f"Máy chủ trả {r.status_code} khi thử khóa.")
    c.api_key_enc, c.key_version = encrypt_bound(user_id, PROVIDER, api_key)
    c.status, c.last_error, c.connected_at = "connected", None, clock.now()
    session.flush()
    return serialize(c)


# ---------- Dùng kết nối ----------


def _fresh(c: Connector) -> bool:
    return c.access_expires_at is None or c.access_expires_at - REFRESH_MARGIN > clock.now()


def get_access_token(
    session: Session, user_id: int, connector_id: int, force_refresh: bool = False
) -> str | None:
    """Token hoặc khóa cho lượt chat; None khi máy chủ không cần xác thực. OAuth tự làm mới khi còn dưới
    5 phút, dưới khóa tư vấn."""
    c = _get(session, user_id, connector_id)
    if c.auth == "none":
        return None
    if c.status == "reauth_required":
        raise ConnectorReauthRequired()
    if c.auth == "api_key":
        if not c.api_key_enc:
            raise ConnectorNotReady("Chưa dán khóa cho kết nối này.")
        return _decrypt(c, c.api_key_enc)
    if not c.access_token_enc:
        raise ConnectorNotReady("Chưa kết nối, hãy bấm Kết nối.")
    if not force_refresh and _fresh(c):
        return _decrypt(c, c.access_token_enc)
    session.execute(text("SELECT pg_advisory_xact_lock(:ns, CAST(:id AS integer))"),
                    {"ns": TOKEN_LOCK_NAMESPACE, "id": c.id})  # fmt: skip
    session.refresh(c)
    if not force_refresh and _fresh(c):
        return _decrypt(c, c.access_token_enc)
    refresh = _decrypt(c, c.refresh_token_enc)
    client = session.get(ConnectorClient, c.client_row_id) if c.client_row_id else None
    if not refresh or client is None:
        _mark_reauth(session, c, "Không có mã làm mới.")
        raise ConnectorReauthRequired()
    r = net.send(
        "POST",
        c.as_metadata["token_endpoint"],
        **_client_auth(client, {"grant_type": "refresh_token", "refresh_token": refresh, "resource": c.url}),
    )
    if r.status_code == 200 and r.json().get("access_token"):
        _store(c, r.json(), refresh)
        session.flush()
        return _decrypt(c, c.access_token_enc)
    try:
        reason = r.json().get("error")
    except ValueError:
        reason = None
    if r.status_code in (400, 401) and reason in ("invalid_grant", "invalid_client", "unauthorized_client"):
        _mark_reauth(session, c, reason)
        raise ConnectorReauthRequired()
    raise ConnectorUnavailable()


def auth_headers(session: Session, user_id: int, connector_id: int) -> dict:
    """Header Authorization cho lượt chat gọi MCP (rỗng khi không cần xác thực)."""
    token = get_access_token(session, user_id, connector_id)
    return {"Authorization": f"Bearer {token}"} if token else {}


def _mark_reauth(session: Session, c: Connector, reason: str) -> None:
    session.execute(update(Connector).where(Connector.id == c.id).values(status="reauth_required",
                                                                          last_error=str(reason)[:200]))  # fmt: skip
    c.status, c.last_error = "reauth_required", str(reason)[:200]
    session.flush()


def list_tools(session: Session, user_id: int, connector_id: int) -> list[dict]:
    """GET /connectors/{id}/tools: `[{name, title, description, write, enabled}]`. Công cụ đọc tự bật; công
    cụ ghi chỉ bật khi người dùng chọn (write_tools_enabled)."""
    c = _get(session, user_id, connector_id)
    token = get_access_token(session, user_id, connector_id)
    try:
        tools = mcp.list_tools(c.url, token)
    except ConnectorUnavailable:
        if c.auth != "oauth":
            raise
        token = get_access_token(
            session, user_id, connector_id, force_refresh=True
        )  # token có thể vừa bị thu
        tools = mcp.list_tools(c.url, token)
    from app.ai.mcp import is_read_tool, looks_write

    enabled = set(c.write_tools_enabled or [])
    for t in tools:
        # Cùng luật với lượt chat (ai.mcp): máy chủ không ghi readOnlyHint thì đoán theo tên. Công cụ đọc tự
        # bật, trừ cái trùng công cụ của app; công cụ ghi chỉ bật khi người dùng chọn.
        t["write"] = t.get("read_only_hint") is False or looks_write(t["name"] or "")
        t["enabled"] = t["name"] in enabled if t["write"] else is_read_tool(t)
    c.tools_count = len(tools)
    session.flush()
    return tools


def tool_allowed(connector: dict, tool_name: str, write: bool) -> bool:
    """Cho agent AI: công cụ ghi chỉ dùng khi đã bật (và vẫn luôn qua thẻ duyệt)."""
    return (not write) or tool_name in (connector.get("write_tools_enabled") or [])


def update_connector(session: Session, user_id: int, connector_id: int, changes: dict) -> dict:
    """PATCH /connectors/{id} {name?, write_tools_enabled?}."""
    c = _get(session, user_id, connector_id)
    if "name" in changes and changes["name"] is not None:
        name = str(changes["name"]).strip()[:100]
        if not name:
            raise ValidationError(fields={"name": "Nhập tên kết nối."})
        c.name = name
    if "write_tools_enabled" in changes and changes["write_tools_enabled"] is not None:
        tools = [str(t)[:200] for t in changes["write_tools_enabled"] if str(t).strip()]
        if len(tools) > 200:
            raise ValidationError(fields={"write_tools_enabled": "Tối đa 200 công cụ."})
        c.write_tools_enabled = sorted(set(tools))
    session.flush()
    return serialize(c)


def delete_connector(session: Session, user_id: int, connector_id: int) -> None:
    """DELETE /connectors/{id}: OAuth thì thu hồi mã (lỗi thu hồi vẫn xóa)."""
    c = _get(session, user_id, connector_id)
    endpoint = (c.as_metadata or {}).get("revocation_endpoint")
    client = session.get(ConnectorClient, c.client_row_id) if c.client_row_id else None
    if c.auth == "oauth" and endpoint and client and c.access_token_enc:
        refresh = _decrypt(c, c.refresh_token_enc)
        token, hint = (
            (refresh, "refresh_token") if refresh else (_decrypt(c, c.access_token_enc), "access_token")
        )
        try:
            net.send("POST", endpoint, **_client_auth(client, {"token": token, "token_type_hint": hint}))
        except (ConnectorUnavailable, ValidationError):
            log.warning("Thu hồi token kết nối lỗi", extra={"connector_id": c.id})
    session.delete(c)
    session.flush()


def call_tool(session: Session, user_id: int, connector_id: int, name: str, arguments: dict | None) -> dict:
    """Chạy một công cụ trên máy chủ MCP, dùng sau khi người dùng duyệt thẻ (công cụ ghi). Công cụ ghi chưa
    bật thì từ chối. Token OAuth bị máy chủ từ chối thì làm mới một lần rồi thử lại."""
    c = _get(session, user_id, connector_id)
    if c.status != "connected":
        raise ConnectorNotReady()
    name = (name or "").strip()
    if not name:
        raise ValidationError(fields={"name": "Thiếu tên công cụ."})
    known = {t["name"]: t for t in list_tools(session, user_id, connector_id)}
    if name not in known:
        raise NotFoundError(f"Máy chủ không có công cụ {name}.")
    if not known[name]["enabled"]:
        raise ValidationError(f"Công cụ ghi {name} chưa bật trong Kết nối.")
    token = get_access_token(session, user_id, connector_id)
    try:
        return mcp.call_tool(c.url, token, name, arguments)
    except ConnectorUnavailable:
        if c.auth != "oauth":
            raise
        token = get_access_token(session, user_id, connector_id, force_refresh=True)
        return mcp.call_tool(c.url, token, name, arguments)
