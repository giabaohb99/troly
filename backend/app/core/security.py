"""Băm mật khẩu, mã ngẫu nhiên, JWT, mã hóa Fernet có phiên bản khóa (10 mục 3.7, 3.14)."""

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core import clock
from app.core.config import get_settings

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def same_hash(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def new_token(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def create_access_token(user_id: int, session_id: int) -> tuple[str, datetime]:
    settings = get_settings()
    issued = clock.now()
    expires = issued + timedelta(minutes=settings.jwt_access_minutes)
    payload = {"sub": str(user_id), "sid": session_id, "typ": "access", "iat": issued, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM), expires


def decode_access_token(token: str) -> dict:
    """Ném jwt.ExpiredSignatureError khi hết hạn, jwt.InvalidTokenError khi sai."""
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[JWT_ALGORITHM])
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("Sai loại mã")
    return payload


def _keyring() -> list[tuple[int, Fernet]]:
    raw = get_settings().token_encryption_keys
    ring: list[tuple[int, Fernet]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        version, _, key = part.partition(":")
        ring.append((int(version.lstrip("v")), Fernet(key.encode())))
    if not ring:
        raise RuntimeError("Thiếu TOKEN_ENCRYPTION_KEYS.")
    return ring


def encrypt_bound(user_id: int, provider: str, secret: str) -> tuple[bytes, int]:
    """Mã hóa bí mật gắn chủ: bản rõ chứa user_id và provider, khóa đầu vòng mã hóa."""
    version, fernet = _keyring()[0]
    plain = json.dumps({"user_id": user_id, "provider": provider, "token": secret}).encode()
    return fernet.encrypt(plain), version


def decrypt_bound(user_id: int, provider: str, blob: bytes, key_version: int) -> str:
    for version, fernet in _keyring():
        if version != key_version:
            continue
        try:
            data = json.loads(fernet.decrypt(blob))
        except InvalidToken as exc:
            raise ValueError("Không giải mã được") from exc
        if data.get("user_id") != user_id or data.get("provider") != provider:
            raise ValueError("Bản mã không thuộc dòng này")
        return data["token"]
    raise ValueError(f"Không có khóa phiên bản v{key_version}")
