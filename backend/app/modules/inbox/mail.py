"""Thư Gmail trong hộp tin và nháp Gmail (QĐ-43, 11 mục 3.10, 40 mục 6).

Thư hộp Chính vào tab_inbox_message (`source = gmail`), chỉ metadata và đoạn trích. Nháp lưu
tab_gmail_draft; gửi chỉ khi người dùng duyệt thẻ `send_gmail_draft` (approvals.py), và chỉ khi nháp trên
Gmail còn đúng `body_hash` lúc tạo thẻ. Gọi Google qua `app.integrations.google.gmail`.
"""

import hashlib

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core import clock
from app.core.context import UserContext
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.inbox import service as inbox_service
from app.modules.inbox.models import GmailDraft, InboxMessage

APP = "gmail"
PACKAGE = "com.google.android.gm"
EMPTY_TEXT = "(Không có đoạn trích)"


def _gmail():
    from app.integrations.google import gmail

    return gmail


def rescan_after_categories_change(session: Session, user_id: int, old, new) -> None:
    """Đổi `gmail.categories`: lượt đồng bộ sau quét lại 7 ngày; thư đã có không ghi trùng (bỏ trùng theo
    message_id). Chưa nối Gmail, hoặc cần nối lại, thì bỏ qua: lần nối sau tự quét theo chế độ mới."""
    from app.integrations.google.errors import GoogleNotConnected, GoogleReauthRequired

    try:
        _gmail().rescan_inbox(session, user_id, days=7)
    except (GoogleNotConnected, GoogleReauthRequired):
        return


# ---------- Thư vào hộp tin (MailStore của integrations/google/stores.py) ----------


def save_gmail_messages(session: Session, user_id: int, mails: list) -> int:
    """Lọc OTP (bỏ cả thư), luật tắt tiếng và người quan trọng, bỏ trùng theo message_id. Trả số thư ghi."""
    from app.modules.device.otp import contains_otp

    rules = inbox_service._rules(session, user_id)
    if inbox_service._match(rules, "muted_app", APP, equals=(APP, PACKAGE)):
        return 0
    saved = 0
    for mail in mails:
        subject = (mail.subject or "").strip()
        snippet = (mail.snippet or "").strip()
        if contains_otp(subject, [snippet], package=PACKAGE):
            continue
        sender = (mail.from_name or mail.from_email or "").strip() or None
        sender_email = (mail.from_email or "").strip().lower()
        folded_sender = inbox_service.fold(sender)
        muted = inbox_service._match(
            rules, "muted_sender", APP, equals=(folded_sender, inbox_service.fold(sender_email))
        ) or inbox_service._match(
            rules, "muted_keyword", APP, within=inbox_service.fold(f"{subject} {snippet}")
        )
        if muted:
            continue
        importance, reason = "normal", None
        if rule := inbox_service._match(
            rules, "vip_sender", APP, equals=(folded_sender, inbox_service.fold(sender_email))
        ):
            importance, reason = "important", f"Người gửi quan trọng: {rule.value}"
        elif rule := inbox_service._match(
            rules, "urgent_keyword", APP, within=inbox_service.fold(f"{subject} {snippet}")
        ):
            importance, reason = "important", f"Có từ khóa: {rule.value}"
        elif mail.important:
            importance, reason = "important", "Gmail đánh dấu quan trọng"
        stmt = (
            pg_insert(InboxMessage)
            .values(
                user_id=user_id,
                source="gmail",
                app=APP,
                app_package=PACKAGE,
                sender=sender,
                sender_key=f"{APP}:{inbox_service.fold(sender_email or sender) or '?'}",
                conversation_key=f"gmail:{mail.thread_id}",
                conversation_title=subject or "(Không tiêu đề)",
                is_group=False,
                subject=subject or None,
                text=(snippet or EMPTY_TEXT)[:4000],
                posted_at=mail.date,
                importance=importance,
                importance_reason=reason,
                external_id=mail.message_id,
                thread_ref=mail.thread_id,
                account_email=getattr(mail, "account_email", None),
                labels=list(mail.labels or []),
                dedupe_hash=hashlib.sha256(f"gmail|{mail.message_id}".encode()).hexdigest()[:32],
            )
            .on_conflict_do_nothing()
            .returning(InboxMessage.id)
        )
        if session.execute(stmt).scalar() is not None:
            saved += 1
    session.flush()
    return saved


# ---------- Nháp ----------


def serialize_draft(d: GmailDraft) -> dict:
    return {
        "id": d.id,
        "to": list(d.to_addrs or []),
        "cc": list(d.cc_addrs or []),
        "subject": d.subject,
        "body": d.body,
        "snippet": " ".join((d.body or "").split())[:200],
        "thread_ref": d.thread_ref,
        "account_id": d.google_account_id,
        "account_email": d.account_email,
        "status": d.status,
        "google_draft_id": d.google_draft_id,
        "pending_action_id": d.pending_action_id,
        "web_url": "https://mail.google.com/mail/#drafts",
        "approved_at": d.approved_at,
        "sent_at": d.sent_at,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


def _get(session: Session, user_id: int, draft_id: int, lock: bool = False) -> GmailDraft:
    stmt = select(GmailDraft).where(GmailDraft.id == draft_id, GmailDraft.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    d = session.scalar(stmt)
    if d is None:
        raise NotFoundError("Không tìm thấy nháp.")
    return d


def list_drafts(session: Session, user_id: int, status: str | None = None) -> list[dict]:
    stmt = select(GmailDraft).where(GmailDraft.user_id == user_id)
    stmt = stmt.where(GmailDraft.status == status) if status else stmt.where(GmailDraft.status != "discarded")
    return [
        serialize_draft(d) for d in session.scalars(stmt.order_by(GmailDraft.updated_at.desc()).limit(100))
    ]


def get_draft(session: Session, user_id: int, draft_id: int) -> dict:
    return serialize_draft(_get(session, user_id, draft_id))


def create_draft(session: Session, user_id: int, data: dict) -> dict:
    """`data`: to, cc, subject, body, thread_ref (trả lời trong luồng), account_id hoặc account_email (tài khoản
    gửi, QĐ-50; email chưa nối thì 404).
    Không chọn tài khoản: trả lời thì tài khoản nhận luồng, thư mới thì tài khoản chính (lớp Gmail chọn).
    Tạo nháp trên Gmail rồi lưu bản sao."""
    if not (data.get("body") or "").strip():
        raise ValidationError(fields={"body": "Nhập nội dung thư."})
    out = _gmail().create_draft(
        session,
        user_id,
        to=data.get("to") or [],
        cc=data.get("cc") or [],
        subject=data.get("subject"),
        body=data["body"],
        thread_id=data.get("thread_ref"),
        account_id=data.get("account_id"),
        account_email=(data.get("account_email") or "").strip() or None,
    )
    d = GmailDraft(
        user_id=user_id,
        google_account_id=out["account_id"],
        account_email=out.get("account_email"),
        google_draft_id=out["google_draft_id"],
        # Chỉ luồng đang trả lời; nháp thư mới cũng có threadId riêng trên Gmail nhưng không phải luồng để trả lời.
        thread_ref=data.get("thread_ref"),
        to_addrs=out["to"],
        cc_addrs=out["cc"],
        subject=out["subject"],
        body=data["body"],
        body_hash=out["body_hash"],
        status="draft",
    )
    session.add(d)
    session.flush()
    return serialize_draft(d)


def update_draft(session: Session, user_id: int, draft_id: int, changes: dict) -> dict:
    d = _get(session, user_id, draft_id, lock=True)
    if d.status != "draft":
        raise ConflictError("Nháp đã gửi hoặc đã bỏ, không sửa được.")
    merged = {
        "to": changes.get("to", list(d.to_addrs or [])),
        "cc": changes.get("cc", list(d.cc_addrs or [])),
        "subject": changes.get("subject", d.subject),
        "body": changes.get("body", d.body),
    }
    if not (merged["body"] or "").strip():
        raise ValidationError(fields={"body": "Nhập nội dung thư."})
    out = _gmail().update_draft(
        session, user_id, d.google_draft_id, thread_id=d.thread_ref, account_id=d.google_account_id, **merged
    )
    d.to_addrs, d.cc_addrs, d.subject = out["to"], out["cc"], out["subject"]
    d.body, d.body_hash = merged["body"], out["body_hash"]
    # Sửa nháp thì thẻ duyệt cũ không còn đúng nội dung: bỏ liên kết, người dùng bấm Gửi lại.
    d.pending_action_id = None
    session.flush()
    return serialize_draft(d)


def discard_draft(session: Session, user_id: int, draft_id: int) -> None:
    d = _get(session, user_id, draft_id, lock=True)
    if d.status == "sent":
        raise ConflictError("Thư đã gửi, không bỏ được.")
    if d.status == "discarded":
        return
    if d.google_draft_id:
        _gmail().delete_draft(session, user_id, d.google_draft_id, account_id=d.google_account_id)
    d.status = "discarded"
    session.flush()


def request_send(
    session: Session, user: UserContext, draft_id: int, conversation_id: int | None = None
) -> dict:
    """Tạo thẻ duyệt `send_gmail_draft`; thư chỉ đi khi người dùng duyệt (QĐ-43)."""
    from app.modules.chat import service as chat_service

    d = _get(session, user.user_id, draft_id, lock=True)
    if d.status != "draft":
        raise ConflictError("Nháp đã gửi hoặc đã bỏ.")
    to = ", ".join(d.to_addrs or [])
    details = [
        {"label": "Gửi tới", "value": to},
        {"label": "Tiêu đề", "value": d.subject or "(Không tiêu đề)"},
        {"label": "Nội dung", "value": (d.body or "")[:500]},
    ]
    if d.cc_addrs:
        details.insert(1, {"label": "Đồng gửi", "value": ", ".join(d.cc_addrs)})
    if d.account_email:
        details.insert(0, {"label": "Gửi từ", "value": d.account_email})
    pending = chat_service.create_pending_action(
        session,
        user.user_id,
        "send_gmail_draft",
        {"draft_id": d.id},
        title="Gửi thư Gmail",
        summary=f"Gửi thư tới {to}. Thư đi ngay khi duyệt.",
        details=details,
        danger=False,
        conversation_id=conversation_id,
    )
    d.pending_action_id = pending["id"]
    session.flush()
    return {"pending_action": pending}


def send_approved(session: Session, user: UserContext, draft_id: int) -> dict:
    """Chạy khi duyệt: so nháp trên Gmail với body_hash; lệch thì ném DraftChanged (409
    ACTION_PAYLOAD_CHANGED) và nháp giữ trạng thái `draft` (savepoint của chat lùi lại)."""
    d = _get(session, user.user_id, draft_id, lock=True)
    if d.status == "sent":
        raise ConflictError("Thư đã gửi rồi.")
    if d.status != "draft" or not d.google_draft_id:
        raise ConflictError("Nháp không còn để gửi.")
    d.status = "sending"
    session.flush()
    out = _gmail().send_draft(
        session, user.user_id, d.google_draft_id, d.body_hash, account_id=d.google_account_id
    )
    now = clock.now()
    d.status, d.approved_at, d.sent_at = "sent", now, now
    d.sent_message_id = out.get("message_id")
    if out.get("thread_id"):
        d.thread_ref = out["thread_id"]
    session.flush()
    return {"draft_id": d.id, "status": "sent", "message_id": d.sent_message_id, "thread_id": d.thread_ref}


def get_thread(session: Session, user_id: int, thread_id: str) -> dict:
    """Luồng thư kèm `account_id`, `account_email` (QĐ-50). Biết tài khoản từ hộp tin thì hỏi thẳng
    tài khoản đó; không thì lớp Gmail dò tài khoản có luồng."""
    email = session.scalar(
        select(InboxMessage.account_email)
        .where(
            InboxMessage.user_id == user_id,
            InboxMessage.source == "gmail",
            InboxMessage.thread_ref == thread_id,
            InboxMessage.account_email.is_not(None),
        )
        .limit(1)
    )
    return _gmail().get_thread(session, user_id, thread_id, account_email=email)


def remove_account_messages(session: Session, user_id: int, email: str | None, delete_messages: bool) -> int:
    """Gỡ một tài khoản Gmail (QĐ-50): `delete_messages` thì xóa tin hộp tin của tài khoản đó; không thì giữ
    tin. Nháp của tài khoản xóa theo khóa ngoại. Trả số tin đã xóa."""
    if not delete_messages or not email:
        return 0
    from sqlalchemy import delete

    res = session.execute(
        delete(InboxMessage).where(
            InboxMessage.user_id == user_id,
            InboxMessage.source == "gmail",
            InboxMessage.account_email == email,
        )
    )
    session.flush()
    return res.rowcount or 0
