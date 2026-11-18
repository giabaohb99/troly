"""Đăng nhập một tài khoản, mã làm mới xoay vòng 365 ngày, mã thiết bị (10 mục 3.7)."""

from datetime import datetime, timedelta

import jwt
from fastapi import Depends, Request
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.context import DeviceContext, UserContext
from app.core.db import get_session
from app.core.errors import AppError, NotFoundError, UnauthorizedError, ValidationError
from app.core.logging import user_id_var
from app.core.models import AuthSession, User
from app.core.ratelimit import limiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    new_token,
    sha256_hex,
    verify_password,
)


class InvalidCredentials(AppError):
    status = 401
    code = "AUTH_INVALID_CREDENTIALS"
    message = "Email hoặc mật khẩu không đúng."


class RefreshInvalid(AppError):
    status = 401
    code = "AUTH_REFRESH_INVALID"
    message = "Phiên đăng nhập không còn hiệu lực, đăng nhập lại."


class TokenExpired(AppError):
    status = 401
    code = "AUTH_TOKEN_EXPIRED"
    message = "Phiên đã hết hạn."


class DeviceRevoked(AppError):
    status = 401
    code = "DEVICE_REVOKED"
    message = "Thiết bị đã bị thu hồi."


# ---------- Dịch vụ đăng nhập ----------


def _issue_tokens(session: Session, user: User, auth_session: AuthSession) -> dict:
    settings = get_settings()
    refresh = new_token("rt")
    auth_session.refresh_token_hash = sha256_hex(refresh)
    auth_session.expires_at = clock.now() + timedelta(days=settings.jwt_refresh_days)
    auth_session.last_used_at = clock.now()
    session.flush()
    access, access_expires = create_access_token(user.id, auth_session.id)
    return {
        "access_token": access,
        "access_expires_at": access_expires,
        "refresh_token": refresh,
        "refresh_expires_at": auth_session.expires_at,
        "user": serialize_user(user),
    }


def serialize_user(user: User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "timezone": user.timezone}


def login(session: Session, email: str, password: str, label: str | None, ip: str) -> dict:
    limiter.hit(f"login:{ip}", get_settings().rate_login_per_15min, 15 * 60)
    user = session.scalar(select(User).where(User.email == email.strip()))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    user.last_login_at = clock.now()
    auth_session = AuthSession(
        user_id=user.id,
        label=(label or "")[:120] or None,
        refresh_token_hash=new_token("tmp"),
        expires_at=clock.now(),
    )
    session.add(auth_session)
    session.flush()
    return _issue_tokens(session, user, auth_session)


def refresh(session: Session, refresh_token: str) -> dict:
    row = session.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == sha256_hex(refresh_token))
        .with_for_update()
    )
    if row is None or row.revoked_at is not None or row.expires_at <= clock.now():
        raise RefreshInvalid()
    user = session.get(User, row.user_id)
    if user is None:
        raise RefreshInvalid()
    return _issue_tokens(session, user, row)


def logout(session: Session, user_id: int, session_id: int) -> None:
    session.execute(
        update(AuthSession)
        .where(AuthSession.id == session_id, AuthSession.user_id == user_id)
        .values(revoked_at=clock.now())
    )


def change_password(session: Session, user_id: int, session_id: int, current: str, new: str) -> None:
    user = session.get(User, user_id)
    if user is None or not verify_password(current, user.password_hash):
        raise InvalidCredentials("Mật khẩu hiện tại không đúng.")
    if len(new) < 8 or len(new.encode()) > 72:
        raise ValidationError(fields={"new_password": "Mật khẩu từ 8 ký tự tới 72 byte."})
    user.password_hash = hash_password(new)
    user.password_changed_at = clock.now()
    session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.id != session_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=clock.now())
    )


def list_sessions(session: Session, user_id: int, current_session_id: int) -> list[dict]:
    rows = session.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > clock.now(),
        )
        .order_by(AuthSession.last_used_at.desc().nulls_last())
    )
    return [
        {
            "id": r.id,
            "label": r.label,
            "created_at": r.created_at,
            "last_used_at": r.last_used_at,
            "expires_at": r.expires_at,
            "current": r.id == current_session_id,
        }
        for r in rows
    ]


def revoke_session(session: Session, user_id: int, session_id: int) -> None:
    result = session.execute(
        update(AuthSession)
        .where(AuthSession.id == session_id, AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=clock.now())
    )
    if result.rowcount == 0:
        raise NotFoundError()


def create_owner(session: Session, email: str, name: str, password: str, timezone: str) -> User:
    if session.scalar(select(User.id).limit(1)) is not None:
        raise AppError("Đã có tài khoản; hệ thống chỉ có một tài khoản.", code="CONFLICT", status=409)
    user = User(
        email=email.strip(), name=name.strip(), password_hash=hash_password(password), timezone=timezone
    )
    session.add(user)
    session.flush()
    return user


# ---------- Dependency cho router ----------


class Caller:
    """Người gọi đã xác thực bằng JWT; giữ thêm sid để đăng xuất, đổi mật khẩu."""

    def __init__(self, user: UserContext, session_id: int):
        self.user = user
        self.session_id = session_id


def _bearer(request: Request, scheme: str) -> str | None:
    header = request.headers.get("authorization", "")
    prefix = f"{scheme} "
    if header[: len(prefix)].lower() == prefix.lower():
        return header[len(prefix) :].strip() or None
    return None


def _user_context(session: Session, user_id: int) -> UserContext:
    tz = session.scalar(select(User.timezone).where(User.id == user_id))
    if tz is None:
        raise UnauthorizedError()
    return UserContext(user_id=user_id, timezone=tz)


def _caller_from_jwt(request: Request, session: Session) -> Caller | None:
    token = _bearer(request, "Bearer")
    if token is None:
        return None
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpired() from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError() from exc
    user = _user_context(session, int(payload["sub"]))
    user_id_var.set(user.user_id)
    limiter.hit(f"user:{user.user_id}", get_settings().rate_user_per_min, 60)
    return Caller(user, int(payload["sid"]))


_LAST_SEEN_THROTTLE = timedelta(minutes=1)


def _device_from_token(request: Request, session: Session) -> DeviceContext | None:
    token = _bearer(request, "Device")
    if token is None:
        return None
    row = session.execute(
        text(
            "SELECT d.id, d.user_id, d.revoked_at, d.last_seen_at, u.timezone "
            "FROM tab_device d JOIN tab_user u ON u.id = d.user_id WHERE d.token_hash = :h"
        ),
        {"h": sha256_hex(token)},
    ).first()
    if row is None:
        raise UnauthorizedError()
    if row.revoked_at is not None:
        raise DeviceRevoked()
    now = clock.now()
    last_seen: datetime | None = row.last_seen_at
    if last_seen is None or now - last_seen > _LAST_SEEN_THROTTLE:
        session.execute(
            text("UPDATE tab_device SET last_seen_at = :n WHERE id = :i"), {"n": now, "i": row.id}
        )
    user_id_var.set(row.user_id)
    return DeviceContext(device_id=row.id, user_id=row.user_id, timezone=row.timezone)


def get_caller(request: Request, session: Session = Depends(get_session)) -> Caller:
    caller = _caller_from_jwt(request, session)
    if caller is None:
        raise UnauthorizedError()
    return caller


def get_current_user(caller: Caller = Depends(get_caller)) -> UserContext:
    return caller.user


def get_current_device(request: Request, session: Session = Depends(get_session)) -> DeviceContext:
    device = _device_from_token(request, session)
    if device is None:
        raise UnauthorizedError()
    return device


def get_device_or_user(request: Request, session: Session = Depends(get_session)) -> UserContext:
    """Cho /device/release, /calendar/reminders: nhận JWT hoặc mã thiết bị."""
    device = _device_from_token(request, session)
    if device is not None:
        return device.user
    caller = _caller_from_jwt(request, session)
    if caller is None:
        raise UnauthorizedError()
    return caller.user


def get_optional_user(request: Request, session: Session = Depends(get_session)) -> UserContext | None:
    """Cho /client-logs: có đăng nhập thì gắn user, không thì vẫn nhận."""
    try:
        device = _device_from_token(request, session)
        if device is not None:
            return device.user
        caller = _caller_from_jwt(request, session)
        return caller.user if caller else None
    except AppError:
        return None
