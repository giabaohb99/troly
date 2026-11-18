"""Thiết bị, mã thiết bị, nhịp tim, bản APK mới nhất (11 mục 3.5, 12 mục 5.8)."""

import json
import logging
import threading
import time
from datetime import timedelta
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core import clock, storage
from app.core.config import get_settings
from app.core.context import DeviceContext
from app.core.errors import ConflictError, ExternalServiceError, NotFoundError
from app.core.security import new_token, sha256_hex
from app.modules.device import otp
from app.modules.device.models import Device, DeviceEvent, ListenedApp

log = logging.getLogger("troly.device")

LATEST_KEY = "releases/latest.json"
SMS_DEFAULT = "sms_default"
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
    return {"server_time": clock.now(), "config_revision": device_config(session, user_id)["revision"]}


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


# ---------- App được nghe, cấu hình cho plugin (11 mục 3.5, 12 mục 5.8) ----------

DEFAULT_LISTENED_APPS = (
    ("com.VCB", "Vietcombank", "expense", "vcb"),
    ("vn.com.techcombank.bb.app", "Techcombank", "expense", "tcb"),
    ("com.mservice.momotransfer", "MoMo", "expense", "momo"),
    ("com.zing.zalo", "Zalo", "inbox", "zalo"),
    ("org.telegram.messenger", "Telegram", "inbox", "telegram"),
    ("com.facebook.orca", "Messenger", "inbox", "messenger"),
    (SMS_DEFAULT, "Tin nhắn SMS", "inbox", "sms"),
)
UPLOAD = {"batch_max": 50, "min_interval_seconds": 30}


def serialize_listened_app(a: ListenedApp) -> dict:
    return {
        "id": a.id,
        "package_name": a.package_name,
        "label": a.label,
        "purpose": a.purpose,
        "parser": a.parser,
        "enabled": a.enabled,
        "is_default": a.is_default,
    }


def ensure_listened_apps(session: Session, user_id: int) -> None:
    if session.scalar(select(ListenedApp.id).where(ListenedApp.user_id == user_id).limit(1)):
        return
    for package, label, purpose, parser in DEFAULT_LISTENED_APPS:
        session.add(
            ListenedApp(
                user_id=user_id,
                package_name=package,
                label=label,
                purpose=purpose,
                parser=parser,
                enabled=True,
                is_default=True,
            )
        )
    session.flush()


def _listened_apps(session: Session, user_id: int) -> list[ListenedApp]:
    ensure_listened_apps(session, user_id)
    return list(
        session.scalars(select(ListenedApp).where(ListenedApp.user_id == user_id).order_by(ListenedApp.id))
    )


def list_listened_apps(session: Session, user_id: int) -> list[dict]:
    return [serialize_listened_app(a) for a in _listened_apps(session, user_id)]


def _listened_app(session: Session, user_id: int, app_id: int) -> ListenedApp:
    a = session.scalar(select(ListenedApp).where(ListenedApp.id == app_id, ListenedApp.user_id == user_id))
    if a is None:
        raise NotFoundError("Không tìm thấy app trong danh sách nghe.")
    return a


def create_listened_app(session: Session, user_id: int, data: dict) -> dict:
    ensure_listened_apps(session, user_id)
    exists = session.scalar(
        select(ListenedApp.id).where(
            ListenedApp.user_id == user_id, ListenedApp.package_name == data["package_name"]
        )
    )
    if exists:
        raise ConflictError("App này đã có trong danh sách nghe.")
    a = ListenedApp(
        user_id=user_id,
        enabled=data.get("enabled", True),
        is_default=False,
        **{k: data[k] for k in ("package_name", "label", "purpose", "parser")},
    )
    session.add(a)
    session.flush()
    return serialize_listened_app(a)


def update_listened_app(session: Session, user_id: int, app_id: int, changes: dict) -> dict:
    a = _listened_app(session, user_id, app_id)
    for key in ("label", "purpose", "parser", "enabled"):
        if changes.get(key) is not None:
            setattr(a, key, changes[key])
    session.flush()
    return serialize_listened_app(a)


def delete_listened_app(session: Session, user_id: int, app_id: int) -> None:
    a = _listened_app(session, user_id, app_id)
    if a.is_default:
        raise ConflictError("App mặc định chỉ tắt được, không xóa.")
    session.delete(a)
    session.flush()


def device_config(session: Session, user_id: int) -> dict:
    apps = [
        {"package_name": a.package_name, "purpose": a.purpose, "parser": a.parser, "enabled": a.enabled}
        for a in _listened_apps(session, user_id)
    ]
    body = {
        "listened_apps": apps,
        "otp_rules_version": otp.OTP_RULES_VERSION,
        "sms_brand_senders": list(otp.SMS_BRAND_SENDERS),
        "upload": UPLOAD,
    }
    revision = sha256_hex(json.dumps(body, sort_keys=True))[:16]
    return {"revision": revision, **body}


def resolve_listened_app(session: Session, user_id: int, device_id: int, package: str) -> ListenedApp | None:
    """App đang bật ứng với gói của sự kiện; gói SMS thật ứng với dòng `sms_default` (K14)."""
    apps = {a.package_name: a for a in _listened_apps(session, user_id) if a.enabled}
    if package != SMS_DEFAULT and package in apps:
        return apps[package]
    sms = apps.get(SMS_DEFAULT)
    if sms is None:
        return None
    default_sms = session.scalar(select(Device.default_sms_package).where(Device.id == device_id))
    return sms if package in otp.SMS_PACKAGES or (default_sms and package == default_sms) else None


# ---------- Nhận sự kiện từ điện thoại (12 mục 5.8) ----------

MAX_AGE = timedelta(days=7)
MAX_AHEAD = timedelta(minutes=10)


class _EventIn(BaseModel):
    client_event_id: UUID
    kind: Literal["notification", "reminder_action"]
    app_package: str | None = Field(default=None, max_length=200)
    posted_at: AwareDatetime
    payload: dict


def _str(value, limit: int) -> str | None:
    return value[:limit] if isinstance(value, str) and value else None


def _clean_notification(p: dict) -> dict | None:
    """Chỉ giữ trường của 11 mục 3.5; trường lạ không lưu."""
    messages = []
    for m in p.get("messages") or []:
        if isinstance(m, dict) and isinstance(m.get("text"), str):
            at = m.get("at")
            at = str(at) if isinstance(at, int) and not isinstance(at, bool) else _str(at, 40)
            messages.append({"sender": _str(m.get("sender"), 200), "text": m["text"][:4000], "at": at})
    out = {
        "title": _str(p.get("title"), 500),
        "text": _str(p.get("text"), 4000),
        "conversation_title": _str(p.get("conversation_title"), 300),
        "messages": messages[:30],
        "is_group_conversation": bool(p.get("is_group_conversation")),
        "category": _str(p.get("category"), 50),
        "notification_key_hash": _str(p.get("notification_key_hash"), 128),
        "hidden_content": bool(p.get("hidden_content")),
    }
    return out if out["title"] or out["text"] or messages else None


def _clean_reminder(p: dict) -> dict | None:
    if not _str(p.get("reminder_key"), 200) or p.get("source") not in ("event", "task"):
        return None
    if p.get("action") not in ("done", "ack", "snooze"):
        return None
    return {
        "reminder_key": p["reminder_key"][:200],
        "source": p["source"],
        "source_id": str(p.get("source_id"))[:64] if p.get("source_id") is not None else None,
        "action": p["action"],
        "at": _str(p.get("at"), 40),
    }


def _insert_event(session: Session, device: DeviceContext, ev: _EventIn, payload: dict, **extra) -> bool:
    stmt = (
        pg_insert(DeviceEvent)
        .values(
            user_id=device.user_id,
            device_id=device.device_id,
            client_event_id=ev.client_event_id,
            kind=ev.kind,
            app_package=ev.app_package,
            posted_at=ev.posted_at,
            payload=payload,
            **extra,
        )
        .on_conflict_do_nothing(index_elements=["device_id", "client_event_id"])
        .returning(DeviceEvent.id)
    )
    return session.execute(stmt).scalar() is not None


def ingest_events(session: Session, device: DeviceContext, events: list) -> dict:
    """Lưu lô sự kiện rồi trả ngay; worker xử lý sau (process_device_events). Từ chối từng sự kiện."""
    now = clock.now()
    accepted, duplicates, rejected = 0, 0, []
    default_sms = session.scalar(select(Device.default_sms_package).where(Device.id == device.device_id))
    for raw in events:
        cid = raw.get("client_event_id") if isinstance(raw, dict) else None
        try:
            ev = _EventIn.model_validate(raw)
        except PydanticValidationError:
            rejected.append(
                {"client_event_id": cid if isinstance(cid, str) else None, "code": "INVALID_EVENT"}
            )
            continue
        cid = str(ev.client_event_id)
        if ev.posted_at < now - MAX_AGE:
            rejected.append({"client_event_id": cid, "code": "EVENT_TOO_OLD"})
            continue
        if ev.posted_at > now + MAX_AHEAD:
            rejected.append({"client_event_id": cid, "code": "INVALID_EVENT"})
            continue
        if ev.kind == "notification":
            payload = _clean_notification(ev.payload) if ev.app_package else None
            if payload is None:
                rejected.append({"client_event_id": cid, "code": "INVALID_EVENT"})
                continue
            listened = resolve_listened_app(session, device.user_id, device.device_id, ev.app_package)
            if listened is None:
                rejected.append({"client_event_id": cid, "code": "APP_NOT_LISTENED"})
                continue
            texts = [payload["text"] or "", *[m["text"] for m in payload["messages"]]]
            if otp.contains_otp(
                payload["title"],
                texts,
                package=ev.app_package,
                sms_package=default_sms,
                expense_app=listened.purpose == "expense",
            ):
                # Lưới an toàn: không giữ nội dung, chỉ để đếm otp_blocked_server (phải bằng 0).
                _insert_event(
                    session, device, ev, {}, status="ignored", result_kind="none", error="OTP_DETECTED"
                )
                log.warning("Máy chủ chặn OTP lọt qua điện thoại", extra={"device_id": device.device_id})
                rejected.append({"client_event_id": cid, "code": "OTP_DETECTED"})
                continue
        else:
            payload = _clean_reminder(ev.payload)
            if payload is None:
                rejected.append({"client_event_id": cid, "code": "INVALID_EVENT"})
                continue
        if _insert_event(session, device, ev, payload):
            accepted += 1
        else:
            duplicates += 1
    if accepted:
        session.execute(update(Device).where(Device.id == device.device_id).values(last_event_at=now))
        session.execute(text("NOTIFY troly_wake, 'device_event'"))
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}


def otp_blocked_server_today(session: Session, user_id: int, since) -> int:
    return session.scalar(
        select(func.count())
        .select_from(DeviceEvent)
        .where(
            DeviceEvent.user_id == user_id,
            DeviceEvent.error == "OTP_DETECTED",
            DeviceEvent.received_at >= since,
        )
    )


def claim_pending_events(session: Session, limit: int) -> list[DeviceEvent]:
    """Cho worker: khóa lô sự kiện chờ (SKIP LOCKED), đánh dấu processing."""
    rows = list(
        session.scalars(
            select(DeviceEvent)
            .where(DeviceEvent.status == "pending", DeviceEvent.next_attempt_at <= clock.now())
            .order_by(DeviceEvent.posted_at, DeviceEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    now = clock.now()
    for ev in rows:
        ev.status, ev.locked_at = "processing", now
        ev.attempts += 1
    session.flush()
    return rows


def finish_event(ev: DeviceEvent, status: str, result_kind: str = "none", result_id=None, error=None) -> None:
    ev.status, ev.result_kind, ev.result_id, ev.error = status, result_kind, result_id, error
    ev.processed_at, ev.locked_at = clock.now(), None


def retry_event(ev: DeviceEvent, error: str, max_attempts: int = 5) -> None:
    ev.locked_at, ev.error = None, error
    if ev.attempts >= max_attempts:
        ev.status, ev.processed_at = "failed", clock.now()
    else:
        ev.status = "pending"
        ev.next_attempt_at = clock.now() + timedelta(seconds=30 * 2 ** (ev.attempts - 1))
