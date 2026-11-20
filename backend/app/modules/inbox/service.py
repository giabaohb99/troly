"""Hộp tin từ thông báo tin nhắn (11 mục 3.10, 12 mục 5.4, 60 mục 3.6). Gmail thêm ở V1.8.

Mỗi tin trong `messages[]` của thông báo thành một dòng; thông báo MessagingStyle gửi lại cả lịch sử
nên chống trùng bằng `dedupe_hash`. Tin người khác giữ 180 ngày (job cleanup_old_data).
"""

import hashlib
import re
import unicodedata
from datetime import UTC, datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import UserContext
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.inbox.models import InboxMessage, InboxRule

APP_BY_PARSER = {"zalo": "zalo", "telegram": "telegram", "messenger": "messenger", "sms": "sms"}
STATUSES = ("new", "seen", "done")
HIDDEN_TEXT = "(Nội dung bị ẩn)"
MARK_MAX = 500
AI_TEXT_MAX = 500
_PHONE = re.compile(r"(?<!\d)(?:\+?84|0)\d{6,8}(\d{3})(?!\d)")
# Zalo đặt tên nhóm vào tiêu đề kèm tiền tố, không đặt conversation_title hay is_group_conversation.
_GROUP_TITLE = re.compile(r"^\s*(?:Nhóm|Nhom|Group)\s*:\s*(?P<name>.+?)\s*$", re.IGNORECASE)
# Tin trong nhóm thiếu người gửi: chữ có dạng `Tên: nội dung`.
_NAME_PREFIX = re.compile(r"^(?P<name>[^:\n]{1,60}?):\s+(?P<body>.+)$", re.DOTALL)
# Tiêu đề trùng tên app là thông báo của chính app (tóm tắt, nhắc), không phải tin của ai.
SYSTEM_TITLES = frozenset({"zalo", "telegram", "messenger", "facebook", "tin nhan", "messages"})


def fold(value: str | None) -> str:
    value = (value or "").replace("đ", "d").replace("Đ", "d")
    value = unicodedata.normalize("NFD", value)
    return re.sub(r"\s+", " ", "".join(c for c in value if unicodedata.category(c) != "Mn")).strip().lower()


def mask_phone(value: str | None) -> str | None:
    return _PHONE.sub(lambda m: "xxxxxxx" + m.group(1), value) if value else value


def _hash(*parts: str, size: int = 32) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:size]


def conversation_key(app: str, sender_key: str, conversation_title: str | None, is_group: bool) -> str:
    """Băm (app, tên nhóm) với nhóm, (app, người gửi) với chat một một (11 mục 3.10)."""
    basis = f"group:{fold(conversation_title)}" if is_group and conversation_title else sender_key
    return _hash(app, basis, size=24)


def _message_time(raw, fallback: datetime) -> tuple[datetime, bool]:
    if isinstance(raw, str) and raw.isdigit():
        raw = int(raw)
    if isinstance(raw, int) and raw > 0:
        return datetime.fromtimestamp(raw / 1000, tz=UTC), True
    if isinstance(raw, str):
        try:
            at = datetime.fromisoformat(raw)
            if at.tzinfo is not None:
                return at, True
        except ValueError:
            pass
    return fallback, False


# ---------- Luật ----------


def _rules(session: Session, user_id: int) -> list[InboxRule]:
    return list(session.scalars(select(InboxRule).where(InboxRule.user_id == user_id)))


def _match(
    rules: list[InboxRule], kind: str, app: str, *, equals: tuple = (), within: str | None = None
) -> InboxRule | None:
    """Luật khớp khi giá trị (bỏ dấu) bằng một trong `equals` hoặc nằm trong chuỗi `within`."""
    for r in rules:
        if r.kind != kind or (r.app is not None and r.app != app):
            continue
        value = fold(r.value)
        if value in equals or (within is not None and value and value in within):
            return r
    return None


def serialize_rule(r: InboxRule) -> dict:
    return {"id": r.id, "kind": r.kind, "value": r.value, "app": r.app, "created_at": r.created_at}


def list_rules(session: Session, user_id: int) -> list[dict]:
    return [serialize_rule(r) for r in sorted(_rules(session, user_id), key=lambda r: r.id)]


def create_rule(session: Session, user_id: int, kind: str, value: str, app: str | None) -> dict:
    value = value.strip()
    if not value:
        raise ValidationError(fields={"value": "Nhập giá trị cho luật."})
    exists = session.scalar(
        select(InboxRule.id).where(
            InboxRule.user_id == user_id,
            InboxRule.kind == kind,
            func.lower(InboxRule.value) == value.lower(),
            func.coalesce(InboxRule.app, "") == (app or ""),
        )
    )
    if exists:
        raise ConflictError("Luật này đã có.")
    r = InboxRule(user_id=user_id, kind=kind, value=value, app=app)
    session.add(r)
    session.flush()
    return serialize_rule(r)


def delete_rule(session: Session, user_id: int, rule_id: int) -> None:
    r = session.scalar(select(InboxRule).where(InboxRule.id == rule_id, InboxRule.user_id == user_id))
    if r is None:
        raise NotFoundError("Không tìm thấy luật.")
    session.delete(r)
    session.flush()


def hidden_apps(session: Session, user_id: int) -> list[str]:
    """App hộp tin đang tắt trong danh sách nghe (QĐ-42: Telegram, Messenger): tin cũ của chúng không xóa,
    chỉ ẩn khỏi hộp tin, đếm tin mới, tóm tắt và tìm. Đọc tab_listened_app bằng SQL (bảng của device)."""
    rows = session.execute(
        text(
            "SELECT parser FROM tab_listened_app WHERE user_id = :u AND purpose = 'inbox' AND enabled = false"
        ),
        {"u": user_id},
    ).scalars()
    return sorted({APP_BY_PARSER.get(p, "other") for p in rows} - {"other"})


def private_keys(session: Session, user_id: int) -> set[str]:
    return set(
        session.scalars(
            select(InboxRule.value).where(
                InboxRule.user_id == user_id, InboxRule.kind == "private_conversation"
            )
        )
    )


# ---------- Nhận thông báo (worker/jobs/device_events.py gọi) ----------


def ingest_notification(
    session: Session,
    user: UserContext,
    *,
    parser: str,
    app_package: str,
    payload: dict,
    posted_at: datetime,
    device_id: int | None = None,
    device_event_id: int | None = None,
) -> dict:
    """Trả `{status (done, ignored), result_kind (inbox_message, none), result_id, reason, created}`."""
    app = APP_BY_PARSER.get(parser, "other")
    rules = _rules(session, user.user_id)
    ignored = {"status": "ignored", "result_kind": "none", "result_id": None, "created": 0}
    if _match(rules, "muted_app", app, equals=(app, fold(app_package))):
        return {**ignored, "reason": "App đã tắt tiếng"}

    title = unicodedata.normalize("NFC", payload.get("title") or "").strip()
    is_group = bool(payload.get("is_group_conversation"))
    conv_title = payload.get("conversation_title") or None
    if fold(title) in SYSTEM_TITLES and not conv_title and app != "sms":
        return {**ignored, "reason": "Thông báo của chính app"}
    group_label = None
    if match := _GROUP_TITLE.match(title):
        is_group, group_label = True, title
        conv_title = conv_title or match.group("name")
    hidden = bool(payload.get("hidden_content"))
    items = payload.get("messages") or [{"sender": title, "text": payload.get("text"), "at": None}]
    created_ids, muted = [], 0
    for item in items:
        sender = item.get("sender")
        if sender and (sender == group_label or (is_group and fold(sender) in SYSTEM_TITLES)):
            sender = None
        body = (item.get("text") or "").strip()
        if is_group and not sender and (named := _NAME_PREFIX.match(body)):
            sender, body = named.group("name").strip(), named.group("body").strip()
        sender = sender or (None if is_group else title or None) or conv_title
        body = body or (HIDDEN_TEXT if hidden else "")
        if not body:
            continue
        sender_key = f"{app}:{fold(sender) or '?'}"
        key = conversation_key(app, sender_key, conv_title, is_group)
        at, exact = _message_time(item.get("at"), posted_at)
        stamp = f"{at:%Y%m%d%H%M%S}" if exact else f"{posted_at:%Y%m%d%H%M}"
        folded_sender, folded_body = fold(sender), fold(body)
        muted_by = _match(rules, "muted_sender", app, equals=(folded_sender, sender_key.split(":", 1)[1]))
        if muted_by or _match(rules, "muted_keyword", app, within=folded_body):
            muted += 1
            continue
        importance, reason = "normal", None
        if rule := _match(rules, "vip_sender", app, equals=(folded_sender,)):
            importance, reason = "important", f"Người gửi quan trọng: {rule.value}"
        elif rule := _match(rules, "urgent_keyword", app, within=folded_body):
            importance, reason = "important", f"Có từ khóa: {rule.value}"
        stmt = (
            pg_insert(InboxMessage)
            .values(
                user_id=user.user_id,
                source="notification",
                app=app,
                app_package=app_package,
                device_id=device_id,
                device_event_id=device_event_id,
                sender=sender,
                sender_key=sender_key,
                conversation_key=key,
                conversation_title=conv_title if is_group else (conv_title or sender),
                is_group=is_group,
                text=body[:4000],
                hidden_content=hidden,
                posted_at=at,
                importance=importance,
                importance_reason=reason,
                dedupe_hash=_hash(key, sender_key, body, stamp),
            )
            .on_conflict_do_nothing(index_elements=["user_id", "dedupe_hash"])
            .returning(InboxMessage.id)
        )
        new_id = session.execute(stmt).scalar()
        if new_id is not None:
            created_ids.append(new_id)
    if not created_ids:
        return {**ignored, "reason": "Tin đã tắt tiếng" if muted else "Tin trùng"}
    return {
        "status": "done",
        "result_kind": "inbox_message",
        "result_id": created_ids[-1],
        "reason": None,
        "created": len(created_ids),
    }


# ---------- Đọc, đánh dấu ----------


def serialize_message(m: InboxMessage) -> dict:
    return {
        "id": m.id,
        "source": m.source,
        "app": m.app,
        "sender": m.sender,
        "conversation_key": m.conversation_key,
        "conversation_title": m.conversation_title,
        "is_group": m.is_group,
        "account_email": m.account_email,
        "subject": m.subject,
        "text": m.text,
        "hidden_content": m.hidden_content,
        "posted_at": m.posted_at,
        "status": m.status,
        "importance": m.importance,
        "importance_reason": m.importance_reason,
    }


_CONVERSATIONS = """
    WITH m AS (
        SELECT * FROM tab_inbox_message
        WHERE user_id = :uid
          AND (CAST(:app AS text) IS NULL OR app = :app)
          AND NOT (app = ANY(CAST(:hidden AS text[])))
          AND (CAST(:status AS text) IS NULL OR status = :status)
          AND (CAST(:importance AS text) IS NULL OR importance = :importance)
          AND (CAST(:from_ AS timestamptz) IS NULL OR posted_at >= :from_)
          AND (CAST(:to_ AS timestamptz) IS NULL OR posted_at < :to_)
    ), g AS (
        SELECT conversation_key, max(posted_at) AS last_posted_at,
               count(*) FILTER (WHERE status = 'new') AS unread_count,
               bool_or(importance = 'important' AND status <> 'done') AS has_important
        FROM m GROUP BY conversation_key
    )
    SELECT g.conversation_key, g.last_posted_at, g.unread_count, g.has_important,
           l.app, coalesce(l.conversation_title, l.sender) AS title, l.is_group,
           l.sender AS last_sender, l.text AS last_text, l.account_email
    FROM g JOIN LATERAL (
        SELECT app, conversation_title, sender, is_group, text, account_email FROM m
        WHERE m.conversation_key = g.conversation_key ORDER BY posted_at DESC, id DESC LIMIT 1
    ) l ON true
    WHERE CAST(:c_key AS text) IS NULL
       OR (g.has_important, g.last_posted_at, g.conversation_key) < (CAST(:c_imp AS boolean), :c_at, :c_key)
    ORDER BY g.has_important DESC, g.last_posted_at DESC, g.conversation_key DESC
    LIMIT :limit
"""


def list_conversations(
    session: Session, user_id: int, filters: dict, cursor: str | None, limit: int = 30
) -> dict:
    c_imp = c_at = c_key = None
    if cursor:
        try:
            imp, at, c_key = cursor.split("|", 2)
            c_imp, c_at = imp == "1", datetime.fromisoformat(at)
        except ValueError as exc:
            raise ValidationError(fields={"cursor": "Con trỏ trang không hợp lệ."}) from exc
    params = {
        "uid": user_id,
        "app": filters.get("app"),
        "hidden": hidden_apps(session, user_id),
        "status": filters.get("status"),
        "importance": filters.get("importance"),
        "from_": filters.get("from"),
        "to_": filters.get("to"),
        "c_imp": c_imp,
        "c_at": c_at,
        "c_key": c_key,
        "limit": limit + 1,
    }
    rows = session.execute(text(_CONVERSATIONS), params).all()
    private = private_keys(session, user_id)
    items = [
        {
            "conversation_key": r.conversation_key,
            "app": r.app,
            "title": r.title,
            "is_group": r.is_group,
            "last_sender": r.last_sender,
            "last_text": r.last_text,
            "last_posted_at": r.last_posted_at,
            "unread_count": r.unread_count,
            "importance": "important" if r.has_important else "normal",
            "is_private": r.conversation_key in private,
            "account_email": r.account_email,
        }
        for r in rows[:limit]
    ]
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = (
            f"{int(bool(last.has_important))}|{last.last_posted_at.isoformat()}|{last.conversation_key}"
        )
    return {"items": items, "next_cursor": next_cursor}


def list_messages(session: Session, user_id: int, key: str, cursor: str | None, limit: int = 50) -> dict:
    stmt = select(InboxMessage).where(InboxMessage.user_id == user_id, InboxMessage.conversation_key == key)
    hidden = hidden_apps(session, user_id)
    if hidden:
        stmt = stmt.where(InboxMessage.app.not_in(hidden))
    if cursor:
        try:
            at, mid = cursor.rsplit("|", 1)
            at_dt, mid_int = datetime.fromisoformat(at), int(mid)
        except ValueError as exc:
            raise ValidationError(fields={"cursor": "Con trỏ trang không hợp lệ."}) from exc
        stmt = stmt.where(
            (InboxMessage.posted_at < at_dt)
            | ((InboxMessage.posted_at == at_dt) & (InboxMessage.id < mid_int))
        )
    rows = list(
        session.scalars(stmt.order_by(InboxMessage.posted_at.desc(), InboxMessage.id.desc()).limit(limit + 1))
    )
    next_cursor = (
        f"{rows[limit - 1].posted_at.isoformat()}|{rows[limit - 1].id}" if len(rows) > limit else None
    )
    return {"items": [serialize_message(m) for m in rows[:limit]], "next_cursor": next_cursor}


def _check_status(status: str) -> None:
    if status not in STATUSES:
        raise ValidationError(fields={"status": "Trạng thái là new, seen hoặc done."})


def mark_conversation(session: Session, user_id: int, key: str, status: str) -> dict:
    _check_status(status)
    result = session.execute(
        update(InboxMessage)
        .where(
            InboxMessage.user_id == user_id,
            InboxMessage.conversation_key == key,
            InboxMessage.status != status,
        )
        .values(status=status)
    )
    return {"updated": result.rowcount or 0}


def mark_messages(session: Session, user_id: int, ids: list[int], status: str) -> dict:
    _check_status(status)
    if not ids or len(ids) > MARK_MAX:
        raise ValidationError(fields={"ids": f"Chọn từ 1 tới {MARK_MAX} tin."})
    result = session.execute(
        update(InboxMessage)
        .where(InboxMessage.user_id == user_id, InboxMessage.id.in_(ids), InboxMessage.status != status)
        .values(status=status)
    )
    return {"updated": result.rowcount or 0}


def update_message(session: Session, user_id: int, message_id: int, status: str) -> dict:
    _check_status(status)
    m = session.scalar(
        select(InboxMessage).where(InboxMessage.id == message_id, InboxMessage.user_id == user_id)
    )
    if m is None:
        raise NotFoundError("Không tìm thấy tin.")
    m.status = status
    session.flush()
    return serialize_message(m)


def list_messages_for_ai(
    session: Session,
    user_id: int,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    app: str | None = None,
    importance: str | None = None,
    status: str | None = None,
    conversation_key: str | None = None,
    limit: int | None = None,
) -> dict:
    """Cho công cụ AI (60 mục 3.6): bỏ cuộc trò chuyện riêng tư, cắt 500 ký tự, che số điện thoại,
    tối đa AI_INBOX_MAX_ITEMS tin. Nội dung là dữ liệu không tin cậy, bên ai/ bọc khối đánh dấu."""
    cap = min(limit or get_settings().ai_inbox_max_items, get_settings().ai_inbox_max_items)
    stmt = select(InboxMessage).where(InboxMessage.user_id == user_id)
    private = private_keys(session, user_id)
    if private:
        stmt = stmt.where(InboxMessage.conversation_key.not_in(private))
    hidden = hidden_apps(session, user_id)
    if hidden:
        stmt = stmt.where(InboxMessage.app.not_in(hidden))
    for column, value in (
        (InboxMessage.app, app),
        (InboxMessage.importance, importance),
        (InboxMessage.status, status),
        (InboxMessage.conversation_key, conversation_key),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    if start is not None:
        stmt = stmt.where(InboxMessage.posted_at >= start)
    if end is not None:
        stmt = stmt.where(InboxMessage.posted_at < end)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.scalars(stmt.order_by(InboxMessage.posted_at.desc(), InboxMessage.id.desc()).limit(cap))
    items = [
        {
            "id": m.id,
            "app": m.app,
            "sender": mask_phone(m.sender),
            "conversation_key": m.conversation_key,
            "conversation_title": mask_phone(m.conversation_title),
            "is_group": m.is_group,
            "posted_at": m.posted_at,
            "subject": mask_phone(m.subject) if m.subject else None,  # Email (QĐ-43)
            "text": mask_phone(m.text[:AI_TEXT_MAX]),
            "status": m.status,
            "importance": m.importance,
        }
        for m in rows
    ]
    return {"items": items, "total": total, "truncated": total > len(items)}
