"""Tin Zalo đầy đủ qua zalo-bridge (QĐ-52) trong hộp tin: lưu, gộp với tin đọc từ thông báo, thu hồi, tải media.

Tin Zalo có `source = zalo`, `app = zalo`, khóa hội thoại `zalo:u:<thread_id>` (một-một) hoặc `zalo:g:<thread_id>`
(nhóm), khử trùng theo `msg_id` của Zalo (`dedupe_hash`, `external_id`). Tin cùng nội dung đọc từ thông báo máy
(nguồn dự phòng) lệch dưới MERGE_MINUTES thì là một tin: tin bridge về sau thay tin thông báo và kéo cả cuộc trò
chuyện cũ (theo khóa thông báo) sang khóa mới; tin thông báo về sau thì bỏ.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.inbox import service as inbox_service
from app.modules.inbox.models import InboxMessage, InboxRule

log = logging.getLogger("troly.inbox.zalo")

APP = "zalo"
PACKAGE = "com.zing.zalo"
MERGE_MINUTES = 5
RECALLED_TEXT = "(Tin đã thu hồi)"
MEDIA_ATTEMPTS = 3

_LABEL = {
    "image": "[Ảnh]",
    "video": "[Video]",
    "sticker": "[Sticker]",
    "file": "[Tệp]",
    "voice": "[Tin thoại]",
    "location": "[Vị trí]",
    "other": "[Tin Zalo chưa hỗ trợ]",
}


def conversation_key(thread_id: str, thread_type: str) -> str:
    return f"zalo:{'g' if thread_type == 'group' else 'u'}:{thread_id}"


def parse_key(key: str) -> tuple[str, str] | None:
    """`zalo:u:<id>` hoặc `zalo:g:<id>` thành (thread_id, thread_type); khóa khác thì None."""
    parts = key.split(":", 2)
    if len(parts) != 3 or parts[0] != "zalo" or parts[1] not in ("u", "g") or not parts[2]:
        return None
    return parts[2], "group" if parts[1] == "g" else "user"


def _body(content: dict) -> str:
    kind = content.get("type") or "other"
    text = (content.get("text") or "").strip()
    if kind == "text":
        return text
    if kind == "link":
        link = content.get("link") or {}
        return text or " ".join(x for x in (link.get("title"), link.get("url")) if x)
    label = _LABEL.get(kind, _LABEL["other"])
    if kind == "file":
        name = (content.get("media") or {}).get("name")
        label = f"{label} {name}" if name else label
    return f"{label} {text}".strip()


def _media(content: dict) -> list[dict] | None:
    media = content.get("media") or {}
    if not media.get("url") or content.get("type") not in ("image", "video", "file", "voice"):
        return None
    return [
        {
            "type": content.get("type"),
            "name": media.get("name"),
            "size": media.get("size"),
            "url": media["url"],
            "thumb": media.get("thumb"),
            "status": "pending",
            "attempts": 0,
            "file_id": None,
            "mime": None,
        }
    ]


def _find_notification_twin(session: Session, user_id: int, body: str, at: datetime) -> InboxMessage | None:
    window = timedelta(minutes=MERGE_MINUTES)
    return session.scalar(
        select(InboxMessage)
        .where(
            InboxMessage.user_id == user_id,
            InboxMessage.source == "notification",
            InboxMessage.app == APP,
            InboxMessage.text == body,
            InboxMessage.posted_at.between(at - window, at + window),
        )
        .order_by(InboxMessage.id.desc())
        .limit(1)
    )


def _move_conversation(session: Session, user_id: int, old_key: str, new_key: str, title: str | None) -> None:
    """Kéo cả cuộc trò chuyện đọc từ thông báo sang khóa Zalo thật; luật riêng tư theo khóa cũng đổi theo."""
    if old_key == new_key:
        return
    values: dict = {"conversation_key": new_key}
    if title:
        values["conversation_title"] = title
    session.execute(
        update(InboxMessage)
        .where(InboxMessage.user_id == user_id, InboxMessage.conversation_key == old_key)
        .values(**values)
    )
    session.execute(
        update(InboxRule)
        .where(
            InboxRule.user_id == user_id, InboxRule.kind == "private_conversation", InboxRule.value == old_key
        )
        .values(value=new_key)
    )


def save_message(session: Session, user_id: int, ev: dict) -> int | None:
    """Một sự kiện `message` của bridge. Trả id tin mới, None khi trùng, OTP, tắt tiếng hoặc rỗng."""
    from app.modules.device.otp import contains_otp

    thread_id, thread_type = str(ev["thread_id"]), ev.get("thread_type") or "user"
    is_group = thread_type == "group"
    key = conversation_key(thread_id, thread_type)
    content = ev.get("content") or {}
    body = _body(content)
    media = _media(content)
    if not body and not media:
        return None
    if contains_otp("", [body], package=PACKAGE):
        return None  # QĐ-35: không lưu tin có mã OTP
    is_self = bool(ev.get("is_self"))
    at = datetime.fromisoformat(str(ev["ts"]).replace("Z", "+00:00"))
    sender = None if is_self else ((ev.get("from_name") or "").strip() or None)
    sender_key = f"{APP}:{ev.get('from_uid') or inbox_service.fold(sender) or '?'}"
    title = (ev.get("thread_name") or "").strip() or (sender if not is_group else None)
    rules = inbox_service._rules(session, user_id)
    if not is_self and inbox_service._match(rules, "muted_app", APP, equals=(APP, PACKAGE)):
        return None
    folded_sender, folded_body = inbox_service.fold(sender), inbox_service.fold(body)
    if not is_self and (
        inbox_service._match(rules, "muted_sender", APP, equals=(folded_sender,))
        or inbox_service._match(rules, "muted_keyword", APP, within=folded_body)
    ):
        return None
    importance, reason, status = "normal", None, "seen" if is_self else "new"
    if not is_self:
        if rule := inbox_service._match(rules, "vip_sender", APP, equals=(folded_sender,)):
            importance, reason = "important", f"Người gửi quan trọng: {rule.value}"
        elif rule := inbox_service._match(rules, "urgent_keyword", APP, within=folded_body):
            importance, reason = "important", f"Có từ khóa: {rule.value}"
    twin = None if is_self else _find_notification_twin(session, user_id, body, at)
    if twin is not None:
        status, importance, reason = twin.status, twin.importance, twin.importance_reason
        old_key = twin.conversation_key
        session.delete(twin)
        session.flush()
        _move_conversation(session, user_id, old_key, key, title)
    quote = ev.get("quote") if isinstance(ev.get("quote"), dict) else None
    stmt = (
        pg_insert(InboxMessage)
        .values(
            user_id=user_id,
            source="zalo",
            app=APP,
            app_package=PACKAGE,
            sender=sender,
            sender_key=sender_key,
            conversation_key=key,
            conversation_title=title,
            is_group=is_group,
            text=(body or _LABEL.get(content.get("type"), _LABEL["other"]))[:4000],
            posted_at=at,
            status=status,
            importance=importance,
            importance_reason=reason,
            external_id=str(ev["msg_id"]),
            thread_ref=thread_id,
            dedupe_hash=inbox_service._hash("zalo", str(ev["msg_id"])),
            is_self=is_self,
            media=media,
            media_pending=bool(media),
            quote={"msg_id": quote.get("msg_id"), "text": (quote.get("text") or "")[:500]} if quote else None,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "dedupe_hash"])
        .returning(InboxMessage.id)
    )
    new_id = session.execute(stmt).scalar()
    if new_id is not None and title:
        # Tin đầu chưa có tên (tin mình gửi trước): đặt tên cho các tin cũ của cuộc trò chuyện.
        session.execute(
            update(InboxMessage)
            .where(
                InboxMessage.user_id == user_id,
                InboxMessage.conversation_key == key,
                InboxMessage.conversation_title.is_(None),
            )
            .values(conversation_title=title)
        )
    return new_id


def recall_message(session: Session, user_id: int, msg_id: str, at: datetime) -> bool:
    """Sự kiện `undo`: tin bị thu hồi thì bỏ nội dung, giữ dòng (*Tin đã thu hồi*)."""
    m = session.scalar(
        select(InboxMessage).where(
            InboxMessage.user_id == user_id, InboxMessage.source == "zalo", InboxMessage.external_id == msg_id
        )
    )
    if m is None:
        return False
    m.text, m.recalled_at, m.media, m.media_pending, m.quote = RECALLED_TEXT, at, None, False, None
    return True


def is_bridge_duplicate(session: Session, user_id: int, body: str, at: datetime) -> bool:
    """Cho đường thông báo máy: tin Zalo đã về qua bridge thì không lưu lại từ thông báo."""
    window = timedelta(minutes=MERGE_MINUTES)
    return (
        session.scalar(
            select(InboxMessage.id)
            .where(
                InboxMessage.user_id == user_id,
                InboxMessage.source == "zalo",
                InboxMessage.text == body,
                InboxMessage.posted_at.between(at - window, at + window),
            )
            .limit(1)
        )
        is not None
    )


def last_title(session: Session, user_id: int, key: str) -> str | None:
    return session.scalar(
        select(InboxMessage.conversation_title)
        .where(
            InboxMessage.user_id == user_id,
            InboxMessage.conversation_key == key,
            InboxMessage.conversation_title.is_not(None),
        )
        .order_by(InboxMessage.posted_at.desc())
        .limit(1)
    )


# ---------- Tải media về R2 (job fetch_zalo_media) ----------


def pending_media(session: Session, limit: int) -> list[InboxMessage]:
    return list(
        session.scalars(
            select(InboxMessage)
            .where(InboxMessage.media_pending.is_(True))
            .order_by(InboxMessage.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )


def fetch_media_for(session: Session, m: InboxMessage, fetch) -> None:
    """`fetch(url, name) -> (bytes, mime, name)`; lỗi thì thử lại tới MEDIA_ATTEMPTS lần rồi `failed`."""
    from app.modules.file import service as file_service

    items = [dict(x) for x in (m.media or [])]
    for item in items:
        if item.get("status") != "pending":
            continue
        try:
            data, mime, name = fetch(item["url"], item.get("name"))
            f = file_service.store_generated_file(
                session, m.user_id, data, mime, name or item.get("name") or f"zalo-{m.external_id}", "other"
            )
            item.update(status="done", file_id=f["id"], mime=mime, size=len(data), name=f["original_name"])
        except Exception as exc:  # link hết hạn, bridge tắt, tệp quá lớn
            item["attempts"] = int(item.get("attempts") or 0) + 1
            too_large = getattr(exc, "code", None) in ("TOO_LARGE", "PAYLOAD_TOO_LARGE")
            if too_large or item["attempts"] >= MEDIA_ATTEMPTS:
                item["status"] = "failed"
            log.warning("Tải media Zalo lỗi", extra={"message_id": m.id, "attempt": item["attempts"]})
    m.media = items
    m.media_pending = any(x.get("status") == "pending" for x in items)
