"""OAuth Google: nối tài khoản, lưu và làm mới token, thu hồi (40 mục 3).

Chỉ tệp này giải mã token Google (10 mục 3.14). Luồng máy chủ web mở bằng Custom Tab, PKCE S256,
`state` lưu băm ở tab_google_oauth_state, dùng một lần, hạn 10 phút.
"""

import base64
import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import NotFoundError
from app.core.security import decrypt_bound, encrypt_bound, sha256_hex
from app.integrations.google import http
from app.integrations.google.errors import GoogleNotConnected, GoogleReauthRequired
from app.integrations.google.models import PACKS, GoogleAccount, GoogleOAuthState, GoogleSyncState
from app.integrations.google.settings import get_google_settings

log = logging.getLogger("troly.google")

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"

PROVIDER = "google"
PKCE_PROVIDER = "google_pkce"
STATE_MINUTES = 10
REFRESH_MARGIN = timedelta(minutes=5)
TOKEN_LOCK_NAMESPACE = 7400  # khóa tư vấn hai số (7400, account_id), khác khóa đồng bộ

_G = "https://www.googleapis.com/auth/"
PACK_SCOPES: dict[str, list[str]] = {
    "base": ["openid", "email", "profile"],
    "calendar": [_G + "calendar.events"],
    "tasks": [_G + "tasks"],
    "gmail": [_G + "gmail.readonly", _G + "gmail.compose"],
    "contacts": [_G + "contacts.readonly"],
    "drive": [_G + "drive.file"],
}
# Google trả email, profile dưới dạng URL đầy đủ.
_SCOPE_ALIASES = {_G + "userinfo.email": "email", _G + "userinfo.profile": "profile"}

# Gói có đồng bộ ở Phase 3; gói khác bật quyền nhưng chưa có việc nền.
SYNCED_PACKS = {"calendar": ("calendar", "primary"), "tasks": ("tasks", ""), "gmail": ("gmail", "me")}


@dataclass
class CallbackResult:
    ket_qua: str  # ok, huy, thieu-quyen, da-co, loi
    message: str
    missing_packs: list[str]
    role: str = "primary"


def normalize_scopes(scopes: list[str] | str) -> set[str]:
    items = scopes.split() if isinstance(scopes, str) else scopes
    return {_SCOPE_ALIASES.get(s, s) for s in items}


def granted_packs(scopes: list[str]) -> list[str]:
    have = normalize_scopes(scopes)
    return [p for p in PACKS if set(PACK_SCOPES[p]) <= have]


def get_account(session: Session, user_id: int) -> GoogleAccount | None:
    """Tài khoản chính (Lịch, Việc, Drive và Gmail chính)."""
    return session.scalar(
        select(GoogleAccount).where(GoogleAccount.user_id == user_id, GoogleAccount.role == "primary")
    )


def list_accounts(session: Session, user_id: int) -> list[GoogleAccount]:
    """Tài khoản chính trước, rồi tài khoản thêm theo ngày nối (QĐ-50)."""
    rows = session.scalars(
        select(GoogleAccount).where(GoogleAccount.user_id == user_id).order_by(GoogleAccount.id)
    )
    return sorted(rows, key=lambda a: (a.role != "primary", a.id))


def get_account_by_id(session: Session, user_id: int, account_id: int) -> GoogleAccount:
    account = session.scalar(
        select(GoogleAccount).where(GoogleAccount.id == account_id, GoogleAccount.user_id == user_id)
    )
    if account is None:
        raise NotFoundError("Không tìm thấy tài khoản Google.")
    return account


def gmail_account(
    session: Session, user_id: int, account_id: int | None = None, email: str | None = None
) -> GoogleAccount:
    """Tài khoản đọc, gửi thư: theo id hoặc email nếu có; không thì tài khoản chính nếu đã bật Gmail, rồi tài
    khoản thêm đầu tiên."""
    if account_id is not None:
        account = get_account_by_id(session, user_id, account_id)
    elif email:
        account = next(
            (a for a in list_accounts(session, user_id) if (a.email or "").lower() == email.strip().lower()),
            None,
        )
        if account is None:
            raise NotFoundError(f"Chưa nối tài khoản Gmail {email}.")
    else:
        usable = [a for a in list_accounts(session, user_id) if "gmail" in (a.enabled_packs or [])]
        if not usable:
            raise GoogleNotConnected("Chưa bật gmail trong kết nối Google.")
        account = usable[0]
    if account.status == "revoked":
        raise GoogleNotConnected()
    if account.status == "reauth_required":
        raise GoogleReauthRequired()
    if "gmail" not in (account.enabled_packs or []):
        raise GoogleNotConnected("Chưa bật gmail trong kết nối Google.")
    return account


def gmail_accounts(session: Session, user_id: int) -> list[GoogleAccount]:
    return [
        a
        for a in list_accounts(session, user_id)
        if a.status == "active" and "gmail" in (a.enabled_packs or [])
    ]


def require_account(session: Session, user_id: int, pack: str | None = None) -> GoogleAccount:
    account = get_account(session, user_id)
    if account is None or account.status == "revoked":
        raise GoogleNotConnected()
    if account.status == "reauth_required":
        raise GoogleReauthRequired()
    if pack and pack not in account.enabled_packs:
        raise GoogleNotConnected(f"Chưa bật {pack} trong kết nối Google.")
    return account


# ---------- Bắt đầu nối ----------


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def start_connect(session: Session, user_id: int, packs: list[str], role: str = "primary") -> str:
    """Tạo state và PKCE, trả auth_url để app mở bằng Custom Tab. role mail: thêm tài khoản chỉ đọc, gửi
    thư (QĐ-50), xin đúng base + gmail, cho chọn tài khoản Google khác."""
    settings = get_google_settings()
    if role == "mail":
        packs = ["gmail"]
    account = get_account(session, user_id) if role == "primary" else None
    # Xin lại cả gói đang bật: quyền cũ có thể đã mất (thu hồi, reauth_required); chỉ xin gói mới thì
    # gói cũ thiếu quyền và bị tắt lặng lẽ. Gói đã cấp thì Google không hỏi lại từng ô.
    keep = list(account.enabled_packs or []) if account is not None and account.status != "revoked" else []
    wanted = ["base"] + [p for p in dict.fromkeys(keep + list(packs)) if p in PACKS and p != "base"]
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)
    enc, version = encrypt_bound(user_id, PKCE_PROVIDER, verifier)
    session.add(
        GoogleOAuthState(
            user_id=user_id,
            state_hash=sha256_hex(state),
            packs=wanted,
            role=role,
            code_verifier_enc=enc,
            key_version=version,
            expires_at=clock.now() + timedelta(minutes=STATE_MINUTES),
        )
    )
    session.flush()
    scopes: list[str] = []
    for pack in wanted:
        scopes.extend(PACK_SCOPES[pack])
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent select_account" if role == "mail" else "consent",
        "include_granted_scopes": "true",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if account is not None:
        params["login_hint"] = account.email
    return f"{AUTH_URL}?{urlencode(params)}"


# ---------- Google gọi về ----------


def _decode_id_token(id_token: str) -> dict:
    """id_token nhận thẳng từ điểm token của Google qua HTTPS nên chỉ đọc phần thân, không kiểm chữ ký."""
    try:
        body = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (IndexError, ValueError) as exc:
        raise ValueError("id_token hỏng") from exc


def _consume_state(session: Session, state: str) -> GoogleOAuthState | None:
    row = session.scalar(
        select(GoogleOAuthState).where(GoogleOAuthState.state_hash == sha256_hex(state)).with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at < clock.now():
        return None
    row.used_at = clock.now()
    return row


def finish_connect(
    session: Session, code: str | None, state: str | None, error: str | None
) -> CallbackResult:
    if not state:
        return CallbackResult("loi", "Thiếu mã phiên kết nối.", [])
    row = _consume_state(session, state)
    if row is None:
        return CallbackResult("loi", "Phiên kết nối đã hết hạn, hãy thử lại.", [])
    role = getattr(row, "role", None) or "primary"
    if error:
        if error == "access_denied":
            return CallbackResult(
                "huy",
                "Google không cho nối hoặc đại ca đã hủy. Nếu Google báo ứng dụng bị chặn, mở Google Cloud > "
                "Google Auth Platform > Audience: đang Testing thì thêm email này vào Test users (hoặc bấm "
                "Publish app), rồi thử lại.",
                [],
                role,
            )
        return CallbackResult("loi", "Google báo lỗi khi kết nối.", [])
    if not code:
        return CallbackResult("loi", "Google không trả mã.", [])
    user_id = row.user_id
    verifier = decrypt_bound(user_id, PKCE_PROVIDER, bytes(row.code_verifier_enc), row.key_version)
    settings = get_google_settings()
    response = http.send(
        "POST",
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
    )
    if response.status_code != 200:
        log.warning("Đổi mã Google thất bại", extra={"status": response.status_code})
        return CallbackResult("loi", "Không đổi được mã với Google.", [])
    token = response.json()
    try:
        claims = _decode_id_token(token.get("id_token", ""))
    except ValueError:
        return CallbackResult("loi", "Google trả thông tin tài khoản không đọc được.", [])
    if claims.get("aud") != settings.google_client_id:
        return CallbackResult("loi", "Thông tin tài khoản không khớp ứng dụng.", [])
    sub, email = str(claims.get("sub", "")), claims.get("email", "")
    granted = sorted(normalize_scopes(token.get("scope", "")))
    packs_ok = granted_packs(granted)
    missing = [p for p in row.packs if p not in packs_ok]
    if role == "mail":
        return _finish_mail(session, user_id, sub, email, granted, packs_ok, token)
    other = session.scalar(select(GoogleAccount).where(GoogleAccount.google_sub == sub))
    if other is not None and (other.user_id != user_id or other.role == "mail"):
        return CallbackResult(
            "da-co", "Tài khoản Google này đã nối làm tài khoản thêm, gỡ trước khi đặt làm chính.", []
        )

    account = get_account(session, user_id)
    if account is not None and account.google_sub != sub and account.status != "revoked":
        return CallbackResult("loi", "Đang nối tài khoản Google khác, hãy ngắt kết nối trước.", [])
    refresh_token = token.get("refresh_token")
    if refresh_token is None and account is None:
        return CallbackResult("loi", "Google không trả mã làm mới, hãy thử lại.", [])

    old_refresh = None
    now = clock.now()
    if account is None:
        account = GoogleAccount(user_id=user_id, google_sub=sub, connected_at=now, enabled_packs=["base"])
        session.add(account)
    else:
        old_refresh = _decrypt(account, account.refresh_token_enc)
    account.email = email
    account.granted_scopes = granted
    account.status = "active"
    account.last_error = None
    account.connected_at = account.connected_at or now
    enabled = set(account.enabled_packs or ["base"]) | {p for p in row.packs if p in packs_ok}
    account.enabled_packs = [p for p in PACKS if p in enabled and p in packs_ok]
    _store_tokens(account, refresh_token or old_refresh, token)
    session.flush()
    _ensure_sync_states(session, account)
    _queue_initial_sync(session, user_id)
    # Không thu hồi mã làm mới cũ: thu hồi một mã là gỡ cả quyền người dùng đã cấp cho app, mã mới vừa
    # nhận cũng chết (invalid_grant ngay lần làm mới sau). Mã cũ quá giới hạn 100 thì Google tự bỏ.
    if missing:
        return CallbackResult("thieu-quyen", "Google chưa cấp đủ quyền cho: " + ", ".join(missing), missing)
    return CallbackResult("ok", "Đã kết nối Google.", [])


def _finish_mail(session, user_id, sub, email, granted, packs_ok, token) -> CallbackResult:
    """Tài khoản thêm chỉ có Gmail; nối lại cùng tài khoản thì chỉ thay mã."""
    existing = session.scalar(select(GoogleAccount).where(GoogleAccount.google_sub == sub))
    if existing is not None and existing.user_id != user_id:
        return CallbackResult("loi", "Tài khoản Google này đã nối với người dùng khác.", [], "mail")
    if existing is not None and existing.role == "primary":
        return CallbackResult("da-co", f"{email} đã là tài khoản Google chính.", [], "mail")
    if "gmail" not in packs_ok:
        return CallbackResult("thieu-quyen", "Google chưa cấp đủ quyền cho: gmail", ["gmail"], "mail")
    refresh_token = token.get("refresh_token")
    now = clock.now()
    if existing is None:
        if refresh_token is None:
            return CallbackResult("loi", "Google không trả mã làm mới, hãy thử lại.", [], "mail")
        existing = GoogleAccount(user_id=user_id, google_sub=sub, role="mail", connected_at=now)
        session.add(existing)
        old_refresh = None
    else:
        old_refresh = _decrypt(existing, existing.refresh_token_enc)
    existing.email, existing.granted_scopes = email, granted
    existing.status, existing.last_error = "active", None
    existing.enabled_packs = ["base", "gmail"]
    _store_tokens(existing, refresh_token or old_refresh, token)
    session.flush()
    _ensure_sync_states(session, existing)
    _queue_initial_sync(session, user_id)
    return CallbackResult("ok", f"Đã thêm tài khoản Gmail {email}.", [], "mail")


def _ensure_sync_states(session: Session, account: GoogleAccount) -> None:
    for pack, (service, resource_id) in SYNCED_PACKS.items():
        if pack not in account.enabled_packs:
            continue
        exists = session.scalar(
            select(GoogleSyncState.id).where(
                GoogleSyncState.google_account_id == account.id, GoogleSyncState.service == service
            )
        )
        if exists is None:
            session.add(
                GoogleSyncState(
                    user_id=account.user_id,
                    google_account_id=account.id,
                    service=service,
                    resource_id=resource_id,
                    initial_sync_state="pending",
                    needs_sync=True,
                )
            )
    session.flush()


def _queue_initial_sync(session: Session, user_id: int) -> None:
    session.execute(
        text(
            "INSERT INTO tab_job_queue (user_id, kind, payload, dedupe_key) "
            "VALUES (:u, 'google_initial_sync', '{}', 'google_initial_sync') "
            "ON CONFLICT DO NOTHING"
        ),
        {"u": user_id},
    )
    session.execute(text("NOTIFY troly_wake, 'job'"))


# ---------- Token ----------


def _decrypt(account: GoogleAccount, blob: bytes) -> str:
    return decrypt_bound(account.user_id, PROVIDER, bytes(blob), account.key_version)


def _store_tokens(account: GoogleAccount, refresh_token: str, token: dict) -> None:
    """Mã hóa lại cả hai mã bằng khóa đầu vòng để chung một key_version."""
    account.refresh_token_enc, account.key_version = encrypt_bound(account.user_id, PROVIDER, refresh_token)
    account.access_token_enc, _ = encrypt_bound(account.user_id, PROVIDER, token["access_token"])
    account.access_expires_at = clock.now() + timedelta(seconds=int(token.get("expires_in", 3600)))


def _mark_reauth(session: Session, account: GoogleAccount, reason: str) -> None:
    account.status = "reauth_required"
    account.invalid_grant_count += 1
    account.last_error = reason
    session.flush()
    log.warning("Token Google hỏng, cần nối lại", extra={"user_id": account.user_id})


def persist_reauth(session: Session, account_id: int) -> None:
    """Ghi lại trạng thái cần nối lại sau khi giao dịch lỗi đã rollback mất lần ghi trong access_token."""
    account = session.get(GoogleAccount, account_id)
    if account is not None and account.status == "active":
        _mark_reauth(session, account, "invalid_grant")


def access_token(session: Session, account: GoogleAccount, force_refresh: bool = False) -> str:
    """Access token còn hạn; còn dưới 5 phút thì làm mới dưới khóa tư vấn theo tài khoản."""
    if account.status == "reauth_required":
        raise GoogleReauthRequired()
    now = clock.now()
    if (
        not force_refresh
        and account.access_token_enc is not None
        and account.access_expires_at is not None
        and account.access_expires_at - REFRESH_MARGIN > now
    ):
        return _decrypt(account, account.access_token_enc)
    session.execute(
        text("SELECT pg_advisory_xact_lock(:ns, CAST(:id AS integer))"),
        {"ns": TOKEN_LOCK_NAMESPACE, "id": account.id},
    )
    session.refresh(account)
    if (
        not force_refresh
        and account.access_token_enc is not None
        and account.access_expires_at is not None
        and account.access_expires_at - REFRESH_MARGIN > clock.now()
    ):
        return _decrypt(account, account.access_token_enc)  # tiến trình khác vừa làm mới
    settings = get_google_settings()
    response = http.send(
        "POST",
        TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": _decrypt(account, account.refresh_token_enc),
            "grant_type": "refresh_token",
        },
    )
    if response.status_code != 200:
        if http.error_reason(response) == "invalid_grant":
            _mark_reauth(session, account, "invalid_grant")
            raise GoogleReauthRequired()
        http.raise_for(response)
    token = response.json()
    _store_tokens(account, token.get("refresh_token") or _decrypt(account, account.refresh_token_enc), token)
    session.flush()
    return token["access_token"]


def revoke_token(token: str) -> bool:
    try:
        response = http.send("POST", REVOKE_URL, data={"token": token})
    except Exception:
        log.warning("Thu hồi token Google lỗi mạng")
        return False
    return response.status_code == 200


def revoke_account_tokens(account: GoogleAccount) -> None:
    try:
        revoke_token(_decrypt(account, account.refresh_token_enc))
    except ValueError:
        log.warning("Không giải mã được token để thu hồi", extra={"user_id": account.user_id})


def callback_html(result: CallbackResult) -> str:
    target = f"troly://cai-dat/google?ket-qua={result.ket_qua}"
    if result.role == "mail":
        target += "&tai-khoan=mail"
    return (
        "<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Kết nối Google</title><meta http-equiv='refresh' content='0;url={target}'></head>"
        "<body style='font-family:sans-serif;padding:24px'>"
        f"<p>{_escape(result.message)}</p>"
        f"<p><a href='{target}'>Quay về app</a></p></body></html>"
    )


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
