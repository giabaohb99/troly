"""Thiết bị, mã thiết bị, nhịp tim, bản APK mới nhất (11 mục 3.5, 12 mục 5.8)."""

import json
import logging
import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock, storage
from app.core.config import get_settings
from app.core.errors import ExternalServiceError, NotFoundError
from app.core.security import new_token, sha256_hex
from app.modules.device.models import Device

log = logging.getLogger("troly.device")

LATEST_KEY = "releases/latest.json"
CACHE_SECONDS = 300
HEARTBEAT_FIELDS = (
    "app_version_code",
    "app_version_name",
    "manufacturer",
    "default_sms_package",
    "notification_access",
    "listener_connected",
    "notifications_enabled",
    "exact_alarm_allowed",
    "battery_optimization_ignored",
    "queue_size",
    "otp_blocked_today",
)


def serialize(d: Device) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "manufacturer": d.manufacturer,
        "model": d.model,
        "os_version": d.os_version,
        "token_prefix": d.token_prefix,
        "app_version_code": d.app_version_code,
        "app_version_name": d.app_version_name,
        "default_sms_package": d.default_sms_package,
        "notification_access": d.notification_access,
        "listener_connected": d.listener_connected,
        "notifications_enabled": d.notifications_enabled,
        "exact_alarm_allowed": d.exact_alarm_allowed,
        "battery_optimization_ignored": d.battery_optimization_ignored,
        "queue_size": d.queue_size,
        "otp_blocked_today": d.otp_blocked_today,
        "last_seen_at": d.last_seen_at,
        "last_event_at": d.last_event_at,
        "revoked_at": d.revoked_at,
    }


def _get(session: Session, user_id: int, device_id: int) -> Device:
    d = session.scalar(select(Device).where(Device.id == device_id, Device.user_id == user_id))
    if d is None:
        raise NotFoundError("Không tìm thấy thiết bị.")
    return d


def register(session: Session, user_id: int, data: dict) -> dict:
    token = new_token("dev")
    d = Device(
        user_id=user_id,
        name=data["name"],
        manufacturer=data.get("manufacturer"),
        model=data.get("model"),
        os_version=data.get("os_version"),
        app_version_code=data.get("app_version_code"),
        app_version_name=data.get("app_version_name"),
        token_hash=sha256_hex(token),
        token_prefix=token[:8],
        last_seen_at=clock.now(),
    )
    session.add(d)
    session.flush()
    return {"device": serialize(d), "device_token": token}


def list_devices(session: Session, user_id: int) -> list[dict]:
    rows = session.scalars(select(Device).where(Device.user_id == user_id).order_by(Device.id.desc()))
    return [serialize(d) for d in rows]


def rename(session: Session, user_id: int, device_id: int, name: str) -> dict:
    d = _get(session, user_id, device_id)
    d.name = name
    return serialize(d)


def revoke(session: Session, user_id: int, device_id: int) -> None:
    d = _get(session, user_id, device_id)
    if d.revoked_at is None:
        d.revoked_at = clock.now()


def heartbeat(session: Session, user_id: int, device_id: int, data: dict) -> dict:
    d = _get(session, user_id, device_id)
    for key in HEARTBEAT_FIELDS:
        if key in data and data[key] is not None:
            setattr(d, key, data[key])
    d.last_seen_at = clock.now()
    return {"server_time": clock.now(), "config_revision": None}


# ---------- Bản APK (releases/latest.json do CI ghi, 50 mục 3.7) ----------

_cache_lock = threading.Lock()
_cache: dict = {"at": 0.0, "value": None}


def latest_release() -> dict | None:
    """Đọc releases/latest.json trên bucket troly-release, đệm 5 phút. Không có tệp thì None."""
    with _cache_lock:
        if time.monotonic() - _cache["at"] < CACHE_SECONDS:
            return _cache["value"]
    bucket = get_settings().r2_bucket
    value = None
    try:
        if storage.head(bucket, LATEST_KEY) is not None:
            value = json.loads(storage.get_bytes(bucket, LATEST_KEY))
    except (ExternalServiceError, ValueError):
        log.warning("Không đọc được releases/latest.json")
        with _cache_lock:
            return _cache["value"]
    with _cache_lock:
        _cache.update(at=time.monotonic(), value=value)
    return value


def reset_release_cache() -> None:
    with _cache_lock:
        _cache.update(at=0.0, value=None)


def min_supported_version_code() -> int | None:
    latest = latest_release()
    return (
        int(latest["min_supported_version_code"])
        if latest and latest.get("min_supported_version_code")
        else None
    )


def release_info(current_version_code: int | None) -> dict:
    latest = latest_release()
    if not latest:
        return {"update_available": False, "required": False, "latest": None}
    code = int(latest["version_code"])
    min_code = int(latest.get("min_supported_version_code") or 0)
    update = current_version_code is None or code > current_version_code
    return {
        "update_available": update,
        "required": bool(current_version_code is not None and current_version_code < min_code),
        "latest": {
            "version_code": code,
            "version_name": latest.get("version_name"),
            "download_url": storage.presign_get(
                get_settings().r2_bucket, latest["apk_key"], f"troly-{latest.get('version_name')}.apk"
            ),
            "sha256": latest.get("sha256"),
            "size_bytes": latest.get("size_bytes"),
            "notes": latest.get("notes"),
            "min_supported_version_code": min_code or None,
            "published_at": latest.get("published_at"),
        }
        if update
        else None,
    }
