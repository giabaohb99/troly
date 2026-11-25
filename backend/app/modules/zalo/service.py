"""Zalo đầy đủ qua zalo-bridge (QĐ-52): nhận sự kiện, đăng nhập QR, danh bạ, gửi tin, thẻ duyệt khi bot gửi thay.

Luật duyệt: người dùng tự gõ trong app thì gửi thẳng (`send_from_app`); bot gửi thay thì luôn qua thẻ
`send_zalo_message` (`request_send`), thực thi ở `approvals.py`. Tin lưu ở hộp tin qua `inbox.zalo`.
"""

import hmac
import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.context import UserContext
from app.core.errors import NotFoundError, UnauthorizedError, ValidationError
from app.core.models import User
from app.integrations.zalo_bridge import client as bridge
from app.modules.inbox import zalo as inbox_zalo
from app.modules.zalo.models import ZaloAccount

log = logging.getLogger("troly.zalo")

KINDS = ("message", "undo", "seen", "delivered", "reaction", "session")
MAX_EVENTS = 100
MAX_FILES = 5
TEXT_MAX = 2000


# ---------- Sự kiện từ bridge ----------


def check_bridge_token(authorization: str | None) -> None:
    """`Authorization: Bearer <ZALO_BRIDGE_TOKEN>`, so bằng hằng thời gian; chưa cấu hình khóa thì từ chối."""
    expected = get_settings().zalo_bridge_token
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
        raise UnauthorizedError()


def _owner(session: Session) -> ZaloAccount | None:
    """Bridge chạy một tài khoản Zalo: người đã bấm đăng nhập; chưa ai bấm thì người dùng đầu tiên (chủ máy)."""
    acc = session.scalar(select(ZaloAccount).order_by(ZaloAccount.updated_at.desc()).limit(1))
    if acc is not None:
        return acc
    user_id = session.scalar(select(User.id).order_by(User.id).limit(1))
    if user_id is None:
        return None
    acc = ZaloAccount(user_id=user_id)
    session.add(acc)
    session.flush()
    return acc


def _ts(ev: dict) -> datetime:
    return datetime.fromisoformat(str(ev.get("ts") or clock.now().isoformat()).replace("Z", "+00:00"))


def handle_events(session: Session, events: list) -> dict:
    """Trả `{accepted, rejected: [{event_id, reason}]}`; sự kiện hỏng bị từ chối riêng, không làm hỏng lô."""
    if len(events) > MAX_EVENTS:
        raise ValidationError(fields={"events": f"Tối đa {MAX_EVENTS} sự kiện mỗi lô."})
    acc = _owner(session)
    accepted, rejected = 0, []
    for ev in events:
        event_id = ev.get("event_id") if isinstance(ev, dict) else None
        kind = ev.get("kind") if isinstance(ev, dict) else None
        if not event_id or kind not in KINDS:
            rejected.append({"event_id": event_id, "reason": "Thiếu event_id hoặc kind lạ"})
            continue
        if acc is None:
            accepted += 1  # chưa có người dùng: nhận rồi bỏ
            continue
        try:
            with session.begin_nested():
                _apply(session, acc, ev)
            accepted += 1
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("Sự kiện Zalo hỏng", extra={"kind": kind, "error": type(exc).__name__})
            rejected.append({"event_id": event_id, "reason": f"Dữ liệu sai: {type(exc).__name__}"})
    if acc is not None and events:
        acc.last_event_at = clock.now()
    session.flush()
    return {"accepted": accepted, "rejected": rejected}


def _apply(session: Session, acc: ZaloAccount, ev: dict) -> None:
    kind = ev["kind"]
    if kind == "message":
        if not ev.get("thread_id") or not ev.get("msg_id"):
            raise KeyError("thread_id")
        inbox_zalo.save_message(session, acc.user_id, ev)
        if ev.get("is_self"):
            # Mình vừa nhắn trong cuộc này (ở bất kỳ máy nào): các tin trước đó coi như đã đọc.
            key = inbox_zalo.conversation_key(str(ev["thread_id"]), ev.get("thread_type") or "user")
            inbox_zalo.mark_thread_seen(session, acc.user_id, key, _ts(ev))
    elif kind == "seen":
        # Nhóm: Zalo báo đã xem kèm mã của chính mình khi đọc ở máy khác.
        if acc.zalo_uid and str(acc.zalo_uid) in [str(u) for u in ev.get("seen_uids") or []] and ev.get("thread_id"):
            key = inbox_zalo.conversation_key(str(ev["thread_id"]), ev.get("thread_type") or "user")
            inbox_zalo.mark_thread_seen(session, acc.user_id, key, _ts(ev))
    elif kind == "undo":
        inbox_zalo.recall_message(session, acc.user_id, str(ev.get("undo_msg_id") or ev["msg_id"]), _ts(ev))
    elif kind == "session":
        acc.state = str(ev["state"])
        account = ev.get("account") or None
        if account and account.get("uid"):
            acc.zalo_uid, acc.display_name = account.get("uid"), account.get("name")
    # delivered, reaction: chưa lưu (app chưa hiện), nhận để bridge không gửi lại.


# ---------- Đăng nhập, trạng thái ----------


def _account(session: Session, user_id: int) -> ZaloAccount:
    acc = session.scalar(select(ZaloAccount).where(ZaloAccount.user_id == user_id))
    if acc is None:
        acc = ZaloAccount(user_id=user_id)
        session.add(acc)
        session.flush()
    return acc


def status(session: Session, user: UserContext) -> dict:
    """`{state, account, qr_png_base64, qr_expires_at, last_event_at}`; bridge tắt thì `state = unavailable`."""
    acc = _account(session, user.user_id)
    try:
        data = bridge.login_status()
    except bridge.ZaloError as exc:
        return {
            "state": "unavailable",
            "message": exc.message,
            "account": None,
            "last_event_at": acc.last_event_at,
        }
    acc.state = data.get("state") or acc.state
    account = data.get("account") or None
    if account:
        acc.zalo_uid, acc.display_name = account.get("uid"), account.get("name")
    session.flush()
    return {
        "state": acc.state,
        "account": account,
        "qr_png_base64": data.get("qr_png_base64"),
        "qr_expires_at": data.get("qr_expires_at"),
        "last_event_at": acc.last_event_at,
    }


def start_login(session: Session, user: UserContext) -> dict:
    acc = _account(session, user.user_id)
    acc.updated_at = clock.now()  # người bấm đăng nhập gần nhất nhận sự kiện
    data = bridge.start_login()
    acc.state = data.get("state") or "waiting_scan"
    session.flush()
    return {
        "state": acc.state,
        "qr_png_base64": data.get("qr_png_base64"),
        "qr_expires_at": data.get("qr_expires_at"),
    }


def logout(session: Session, user: UserContext) -> dict:
    acc = _account(session, user.user_id)
    bridge.logout()
    acc.state = "logged_out"
    session.flush()
    return {"state": acc.state}


def contacts(user: UserContext) -> list[dict]:
    """Bạn bè và nhóm (để mở cuộc trò chuyện mới), kèm `conversation_key` của hộp tin."""
    return [
        {
            **c,
            "conversation_key": inbox_zalo.conversation_key(
                str(c["thread_id"]), c.get("thread_type") or "user"
            ),
        }
        for c in bridge.contacts()
        if c.get("thread_id")
    ]


def _fold_name(name: str | None) -> str:
    from app.modules.inbox.service import fold

    return fold(name or "").strip()


def _match_contact(items: list[dict], title: str | None, is_group: bool | None) -> dict | None:
    want = _fold_name(title)
    if not want:
        return None
    hits = [
        c
        for c in items
        if _fold_name(c.get("name")) == want
        and (is_group is None or (c.get("thread_type") == "group") == is_group)
    ]
    return hits[0] if len(hits) == 1 else None


def link_thread(session: Session, user: UserContext, conversation_key: str, items: list[dict] | None = None) -> str | None:
    """Cuộc Zalo đọc từ thông báo: tìm đúng một người hoặc nhóm cùng tên trong danh bạ Zalo rồi kéo cả cuộc sang khóa
    thật (nhắn được, tin bridge về sau gộp vào). Đã là khóa thật thì trả lại; không khớp hoặc trùng tên thì None."""
    if inbox_zalo.parse_key(conversation_key):
        return conversation_key
    threads = {k: (t, g) for k, t, g in inbox_zalo.notification_threads(session, user.user_id)}
    if conversation_key not in threads:
        return None
    title, is_group = threads[conversation_key]
    hit = _match_contact(items if items is not None else contacts(user), title, is_group)
    if hit is None:
        return None
    new_key = inbox_zalo.conversation_key(str(hit["thread_id"]), hit.get("thread_type") or "user")
    inbox_zalo.move_conversation(session, user.user_id, conversation_key, new_key, hit.get("name") or title)
    session.flush()
    return new_key


def link_all_threads(session: Session, user: UserContext) -> dict:
    """Nối mọi cuộc Zalo từ thông báo với danh bạ (một lần gọi danh bạ)."""
    items = contacts(user)
    linked = unmatched = 0
    for key, _title, _group in inbox_zalo.notification_threads(session, user.user_id):
        if link_thread(session, user, key, items):
            linked += 1
        else:
            unmatched += 1
    return {"linked": linked, "unmatched": unmatched}


def sync_history(session: Session, user: UserContext, conversation_key: str) -> dict:
    """Lấy thêm tin cũ: nhóm thì lấy thẳng 50 tin từ Zalo và lưu; một-một Zalo không có lịch sử nên xin Zalo
    gửi lại tin cũ, tin về sau qua đường sự kiện."""
    thread = inbox_zalo.parse_key(conversation_key)
    if thread is None:
        raise NotFoundError("Không phải cuộc trò chuyện Zalo.")
    thread_id, thread_type = thread
    if thread_type == "group":
        saved = 0
        for item in bridge.group_history(thread_id):
            ev = {**item, "thread_id": item.get("thread_id") or thread_id, "thread_type": "group"}
            if not ev.get("msg_id") or not ev.get("ts"):
                continue
            with session.begin_nested():
                if inbox_zalo.save_message(session, user.user_id, ev) is not None:
                    saved += 1
        return {"mode": "group_history", "saved": saved}
    bridge.request_old_messages("user")
    return {"mode": "requested", "saved": 0}


# ---------- Gửi tin ----------


def _thread(conversation_key: str | None, thread_id: str | None, thread_type: str | None) -> tuple[str, str]:
    if conversation_key:
        thread = inbox_zalo.parse_key(conversation_key)
        if thread is None:
            raise ValidationError(
                fields={"conversation_key": "Chỉ gửi được vào cuộc trò chuyện Zalo đầy đủ."}
            )
        return thread
    if not thread_id or thread_type not in ("user", "group"):
        raise ValidationError(fields={"thread_id": "Cần conversation_key hoặc thread_id và thread_type."})
    return thread_id, thread_type


def _file_links(session: Session, user_id: int, file_ids: list[int]) -> list[dict]:
    from app.modules.file import service as file_service

    if len(file_ids) > MAX_FILES:
        raise ValidationError(fields={"file_ids": f"Tối đa {MAX_FILES} tệp mỗi lần."})
    links = []
    for fid in file_ids:
        f = file_service.get_file(session, user_id, fid)  # 404 nếu không phải tệp của người này
        if f.get("status") != "ready" or not f.get("download_url"):
            raise ValidationError(fields={"file_ids": "Tệp chưa tải lên xong."})
        links.append({"url": f["download_url"], "name": f.get("original_name") or f"tep-{fid}"})
    return links


def send(
    session: Session,
    user: UserContext,
    *,
    conversation_key: str | None = None,
    thread_id: str | None = None,
    thread_type: str | None = None,
    text: str | None = None,
    file_ids: list[int] | None = None,
    client_ref: str | None = None,
) -> dict:
    """Gửi qua bridge, trả `{msg_ids, client_ref, conversation_key}`. Tin hiện trong hộp tin khi bridge báo lại
    sự kiện `is_self` (khử trùng theo msg_id), không lưu trước."""
    thread_id, thread_type = _thread(conversation_key, thread_id, thread_type)
    text = (text or "").strip()[:TEXT_MAX] or None
    files = _file_links(session, user.user_id, file_ids or [])
    if not text and not files:
        raise ValidationError(fields={"text": "Nhập nội dung hoặc chọn tệp."})
    ref = client_ref or str(uuid.uuid4())
    out = bridge.send_message(thread_id, thread_type, text=text, files=files, client_ref=ref)
    return {
        "msg_ids": list(out.get("msg_ids") or []),
        "client_ref": out.get("client_ref") or ref,
        "conversation_key": inbox_zalo.conversation_key(thread_id, thread_type),
    }


def request_send(
    session: Session,
    user: UserContext,
    *,
    conversation_key: str | None = None,
    thread_id: str | None = None,
    thread_type: str | None = None,
    text: str,
    conversation_id: int | None = None,
) -> dict:
    """Bot gửi thay (công cụ của agent AI): luôn qua thẻ duyệt `send_zalo_message`, tin chỉ đi khi duyệt."""
    from app.modules.chat import service as chat_service

    thread_id, thread_type = _thread(conversation_key, thread_id, thread_type)
    text = (text or "").strip()
    if not text:
        raise ValidationError(fields={"text": "Nhập nội dung tin."})
    key = inbox_zalo.conversation_key(thread_id, thread_type)
    to = inbox_zalo.last_title(session, user.user_id, key) or (
        "Nhóm Zalo" if thread_type == "group" else "Zalo"
    )
    pending = chat_service.create_pending_action(
        session,
        user.user_id,
        "send_zalo_message",
        {"thread_id": thread_id, "thread_type": thread_type, "text": text[:TEXT_MAX]},
        title="Gửi tin Zalo",
        summary=f"Gửi Zalo tới {to}. Tin đi ngay khi duyệt.",
        details=[{"label": "Gửi tới", "value": to}, {"label": "Nội dung", "value": text[:500]}],
        danger=False,
        conversation_id=conversation_id,
    )
    return {"pending_action": pending}


def execute_approved(session: Session, user: UserContext, data: dict) -> dict:
    """Thực thi thẻ `send_zalo_message` đã duyệt."""
    out = send(
        session,
        user,
        thread_id=str(data["thread_id"]),
        thread_type=data["thread_type"],
        text=data["text"],
        client_ref=f"approval-{uuid.uuid4()}",
    )
    return {"sent": True, **out}
