"""Gmail với gmail.readonly và gmail.compose (40 mục 6, QĐ-43).

Đồng bộ: quét hộp Chính mỗi 5 phút, lần đầu `messages.list(in:inbox newer_than:7d)`, sau đó `history.list`;
404 thì quét lại từ đầu. Chỉ lấy metadata và đoạn trích; thư được giao cho MailStore của module inbox
(module lọc OTP, luật tắt tiếng, người quan trọng, rồi ghi tab_inbox_message).

Gửi thư chỉ qua thẻ duyệt `send_gmail_draft`: nháp tạo bằng `create_draft` có `body_hash`; lúc duyệt
`send_draft` đọc lại nháp trên Gmail, băm lại, khác thì không gửi.
"""

import base64
import hashlib
import html
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parseaddr

from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import AppError, ValidationError
from app.integrations.google import oauth, stores
from app.integrations.google.client import GoogleApi
from app.integrations.google.errors import GoogleHttpError
from app.integrations.google.models import GoogleAccount, GoogleSyncState

log = logging.getLogger("troly.google")

GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
POLL = timedelta(minutes=5)
FIRST_QUERY = "in:inbox newer_than:7d"
FIRST_MAX = 200  # lần đầu tối đa 200 thư (mỗi thư metadata 20 đơn vị quota)
THREAD_TEXT_MAX = 4000
MAX_RECIPIENTS = 50
DRAFTS_URL = "https://mail.google.com/mail/#drafts"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DraftChanged(AppError):
    status = 409
    code = "ACTION_PAYLOAD_CHANGED"
    message = "Nháp đã bị sửa, hãy xem lại."


@dataclass
class RemoteMail:
    """Một thư ở hộp Chính, chỉ metadata (không lưu nội dung đầy đủ, 40 mục 6)."""

    message_id: str
    thread_id: str
    from_name: str | None
    from_email: str | None
    subject: str
    snippet: str
    date: datetime
    labels: list[str] = field(default_factory=list)
    important: bool = False


# ---------- Tiện ích ----------


def _headers(payload: dict | None) -> dict[str, str]:
    return {h["name"].lower(): h.get("value", "") for h in (payload or {}).get("headers") or []}


def _date_of(item: dict) -> datetime:
    ms = item.get("internalDate")
    return datetime.fromtimestamp(int(ms) / 1000, UTC) if ms else clock.now()


def _addresses(value: str | None) -> list[str]:
    return [a.lower() for _, a in getaddresses([value or ""]) if a]


def _clean_list(values: list[str] | None, field_name: str) -> list[str]:
    out = []
    for v in values or []:
        v = (v or "").strip().lower()
        if not v:
            continue
        if not _EMAIL.match(v):
            raise ValidationError(fields={field_name: f"Email không hợp lệ: {v}"})
        if v not in out:
            out.append(v)
    return out


def body_hash(to: list[str], cc: list[str], subject: str, body: str) -> str:
    """Băm nội dung thư như người dùng thấy trên thẻ duyệt; cùng hàm lúc tạo nháp và lúc gửi."""
    text = (body or "").replace("\r\n", "\n").rstrip()
    data = [sorted(a.lower() for a in to), sorted(a.lower() for a in cc), (subject or "").strip(), text]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode()).hexdigest()


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _strip_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", value)
    value = html.unescape(re.sub(r"<[^>]+>", " ", value))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", value)).strip()


def _text_of(payload: dict) -> str:
    """Chữ thường của thư: ưu tiên text/plain, không có thì bỏ HTML của text/html."""
    plain, rich = [], []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        data = (part.get("body") or {}).get("data")
        if data and mime == "text/plain":
            plain.append(_b64decode(data).decode("utf-8", "replace"))
        elif data and mime == "text/html":
            rich.append(_b64decode(data).decode("utf-8", "replace"))
        for child in part.get("parts") or []:
            walk(child)

    walk(payload or {})
    if plain:
        return "\n".join(plain).strip()
    return _strip_html("\n".join(rich))


def _api(session: Session, user_id: int) -> tuple[GoogleAccount, GoogleApi]:
    account = oauth.require_account(session, user_id, "gmail")
    return account, GoogleApi(session, account)


# ---------- Đồng bộ hộp Chính ----------


# Cài đặt gmail.categories (module setting giữ, MailStore đọc giúp): lấy những mục nào của hộp thư đến.
# Thư IMPORTANT luôn vào; SPAM, TRASH luôn bỏ (lỗi thật 20/11: 22 trên 25 thư mang CATEGORY_UPDATES bị bỏ).
CATEGORY_MODES = {
    "primary": {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_FORUMS", "CATEGORY_UPDATES"},
    "primary_updates": {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_FORUMS"},
    "all": {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL"},
}
DEFAULT_CATEGORIES = "primary_updates"
ALWAYS_SKIP = frozenset({"SPAM", "TRASH"})


def categories_of(session: Session, user_id: int) -> str:
    store = stores.mail_store()
    getter = getattr(store, "gmail_categories", None)
    mode = getter(session, user_id) if getter else None
    return mode if mode in CATEGORY_MODES else DEFAULT_CATEGORIES


def _wanted(labels: list[str], mode: str = DEFAULT_CATEGORIES) -> bool:
    if "INBOX" not in labels or ALWAYS_SKIP.intersection(labels):
        return False
    if "IMPORTANT" in labels:
        return True
    return not CATEGORY_MODES.get(mode, CATEGORY_MODES[DEFAULT_CATEGORIES]).intersection(labels)


def _metadata(api: GoogleApi, message_id: str) -> dict:
    return api.request(
        "GET",
        f"{GMAIL}/messages/{message_id}",
        params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
    )


def to_remote(item: dict) -> RemoteMail:
    h = _headers(item.get("payload"))
    name, address = parseaddr(h.get("from", ""))
    labels = list(item.get("labelIds") or [])
    return RemoteMail(
        message_id=item["id"],
        thread_id=item.get("threadId") or item["id"],
        from_name=name or None,
        from_email=address.lower() or None,
        subject=h.get("subject", ""),
        snippet=html.unescape(item.get("snippet") or ""),
        date=_date_of(item),
        labels=labels,
        important="IMPORTANT" in labels,
    )


def _require_store() -> stores.MailStore:
    store = stores.mail_store()
    if store is None:
        raise RuntimeError("Module inbox chưa đăng ký MailStore")
    return store


def sync_gmail(session: Session, account: GoogleAccount, state: GoogleSyncState) -> int:
    """Một lượt quét; trả số thư mới đã giao cho module inbox."""
    store = _require_store()
    api = GoogleApi(session, account)
    ids: list[str] = []
    history_id = state.history_id
    if history_id:
        try:
            ids, history_id = _history(api, history_id)
        except GoogleHttpError as exc:
            if exc.status != 404:
                raise
            log.info("historyId Gmail hết hạn, quét lại từ đầu", extra={"user_id": account.user_id})
            history_id = None
    if not history_id:
        ids, history_id = _first(api, state.updated_min)
    mode = categories_of(session, account.user_id)
    mails = []
    for message_id in dict.fromkeys(ids):
        try:
            item = _metadata(api, message_id)
        except GoogleHttpError as exc:
            if exc.status == 404:
                continue  # thư đã xóa giữa chừng
            raise
        if _wanted(item.get("labelIds") or [], mode):
            mails.append(to_remote(item))
    saved = store.save_gmail_messages(session, account.user_id, mails) if mails else 0
    _scan_bookings_safely(session, account)
    now = clock.now()
    state.history_id = str(history_id)
    state.updated_min = None
    state.last_sync_at, state.needs_sync = now, False
    state.next_sync_at = now + POLL
    state.status, state.last_error = "ok", None
    session.flush()
    return saved


def rescan_inbox(session: Session, user_id: int, days: int = 7) -> None:
    """Lượt đồng bộ sau quét lại `days` ngày (đổi gmail.categories, hoặc khi deploy). Thư đã có không ghi
    trùng: MailStore bỏ trùng theo message_id."""
    from sqlalchemy import select

    account = oauth.require_account(session, user_id, "gmail")
    state = session.scalar(
        select(GoogleSyncState).where(
            GoogleSyncState.google_account_id == account.id,
            GoogleSyncState.service == "gmail",
            GoogleSyncState.resource_id == "me",
        )
    )
    if state is None:
        return
    state.history_id = None
    state.updated_min = clock.now() - timedelta(days=max(1, min(days, 30)))
    state.needs_sync, state.next_sync_at = True, clock.now()
    session.flush()


def _first(api: GoogleApi, since: datetime | None = None) -> tuple[list[str], str]:
    # Lấy historyId trước khi liệt kê: thư đến trong lúc quét sẽ nằm ở lượt history sau.
    history_id = api.request("GET", f"{GMAIL}/profile")["historyId"]
    query = f"in:inbox after:{int(since.timestamp())}" if since else FIRST_QUERY
    ids: list[str] = []
    page = None
    while len(ids) < FIRST_MAX:
        params = {"q": query, "maxResults": 100}
        if page:
            params["pageToken"] = page
        data = api.request("GET", f"{GMAIL}/messages", params=params)
        ids += [m["id"] for m in data.get("messages") or []]
        page = data.get("nextPageToken")
        if not page:
            break
    return ids[:FIRST_MAX], history_id


def _history(api: GoogleApi, start: str) -> tuple[list[str], str]:
    ids: list[str] = []
    page, latest = None, start
    while True:
        params = {"startHistoryId": start, "historyTypes": "messageAdded", "labelId": "INBOX"}
        if page:
            params["pageToken"] = page
        data = api.request("GET", f"{GMAIL}/history", params=params)
        for h in data.get("history") or []:
            ids += [a["message"]["id"] for a in h.get("messagesAdded") or []]
        latest = data.get("historyId") or latest
        page = data.get("nextPageToken")
        if not page:
            return ids, latest


# ---------- Đọc cho công cụ AI và màn luồng thư ----------


def search(session: Session, user_id: int, query: str, limit: int = 10) -> list[dict]:
    """Công cụ search_gmail: cú pháp tìm của Gmail (from:, subject:, newer_than:...)."""
    if not (query or "").strip():
        raise ValidationError(fields={"query": "Nhập điều cần tìm."})
    _, api = _api(session, user_id)
    data = api.request(
        "GET", f"{GMAIL}/messages", params={"q": query.strip(), "maxResults": max(1, min(limit, 25))}
    )
    out = []
    for m in data.get("messages") or []:
        r = to_remote(_metadata(api, m["id"]))
        out.append(
            {
                "message_id": r.message_id,
                "thread_id": r.thread_id,
                "from_name": r.from_name,
                "from_email": r.from_email,
                "subject": r.subject,
                "date": r.date,
                "snippet": r.snippet,
            }
        )
    return out


def get_thread(session: Session, user_id: int, thread_id: str) -> dict:
    """Luồng thư, thư cũ trước; chữ đã bỏ HTML, tổng tối đa 4.000 ký tự (ưu tiên thư mới).
    `reply` là gợi ý cho nút Trả lời: gửi lại người gửi thư cuối không phải mình."""
    account, api = _api(session, user_id)
    data = api.request("GET", f"{GMAIL}/threads/{thread_id}", params={"format": "full"})
    me = (account.email or "").lower()
    messages = []
    for item in data.get("messages") or []:
        h = _headers(item.get("payload"))
        name, address = parseaddr(h.get("from", ""))
        messages.append(
            {
                "id": item["id"],
                "from_name": name or None,
                "from_email": address.lower() or None,
                "to": _addresses(h.get("to")),
                "cc": _addresses(h.get("cc")),
                "date": _date_of(item),
                "text": _text_of(item.get("payload") or {}),
                "_reply_to": _addresses(h.get("reply-to")),
                "_message_id": h.get("message-id"),
                "_subject": h.get("subject", ""),
            }
        )
    budget = THREAD_TEXT_MAX
    for m in reversed(messages):
        if len(m["text"]) > budget:
            m["text"] = (m["text"][: max(budget - 1, 0)] + "…") if budget > 0 else ""
        budget = max(budget - len(m["text"]), 0)
    subject = messages[0]["_subject"] if messages else ""
    others = [m for m in messages if m["from_email"] and m["from_email"] != me]
    last = others[-1] if others else (messages[-1] if messages else None)
    reply = None
    if last is not None:
        to = last["_reply_to"] or ([last["from_email"]] if last["from_email"] != me else last["to"])
        reply = {
            "to": to,
            "cc": [],
            "subject": subject if subject.lower().startswith("re:") else f"Re: {subject}".strip(),
            "in_reply_to": last["_message_id"],
        }
    for m in messages:
        for k in ("_reply_to", "_message_id", "_subject"):
            m.pop(k)
    return {"thread_id": data.get("id", thread_id), "subject": subject, "messages": messages, "reply": reply}


# ---------- Nháp ----------


def _thread_headers(api: GoogleApi, thread_id: str) -> tuple[str, str | None, str | None]:
    """(tiêu đề gốc, Message-ID thư cuối, References) để thư trả lời nằm đúng luồng (40 mục 6)."""
    data = api.request(
        "GET",
        f"{GMAIL}/threads/{thread_id}",
        params={"format": "metadata", "metadataHeaders": ["Subject", "Message-ID", "References"]},
    )
    items = data.get("messages") or []
    if not items:
        raise ValidationError(fields={"thread_ref": "Không tìm thấy luồng thư."})
    first, last = _headers(items[0].get("payload")), _headers(items[-1].get("payload"))
    message_id = last.get("message-id")
    refs = " ".join(x for x in (last.get("references"), message_id) if x) or None
    return first.get("subject", ""), message_id, refs


def _raw(
    to: list[str], cc: list[str], subject: str, body: str, in_reply_to: str | None, refs: str | None
) -> str:
    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = refs or in_reply_to
    msg.set_content(body or "")
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def _prepare(api, to, cc, subject, body, thread_id) -> tuple[dict, list[str], list[str], str]:
    to, cc = _clean_list(to, "to"), _clean_list(cc, "cc")
    if not to:
        raise ValidationError(fields={"to": "Cần ít nhất một người nhận."})
    if len(to) + len(cc) > MAX_RECIPIENTS:
        raise ValidationError(fields={"to": f"Tối đa {MAX_RECIPIENTS} người nhận một thư."})
    subject = (subject or "").strip()
    in_reply_to = refs = None
    if thread_id:
        original, in_reply_to, refs = _thread_headers(api, thread_id)
        if not subject:
            subject = original if original.lower().startswith("re:") else f"Re: {original}".strip()
    if not subject:
        raise ValidationError(fields={"subject": "Nhập tiêu đề thư."})
    message: dict = {"raw": _raw(to, cc, subject, body, in_reply_to, refs)}
    if thread_id:
        message["threadId"] = thread_id
    return message, to, cc, subject


def _draft_result(data: dict, to, cc, subject, body) -> dict:
    msg = data.get("message") or {}
    return {
        "google_draft_id": data["id"],
        "message_id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "to": to,
        "cc": cc,
        "subject": subject,
        "body_hash": body_hash(to, cc, subject, body),
        "web_url": DRAFTS_URL,
    }


def create_draft(
    session: Session,
    user_id: int,
    *,
    to: list[str],
    cc: list[str] | None,
    subject: str | None,
    body: str,
    thread_id: str | None = None,
) -> dict:
    """drafts.create. Trả `{google_draft_id, message_id, thread_id, to, cc, subject, body_hash, web_url}`;
    module inbox lưu tab_gmail_draft với body_hash này. Trả lời trong luồng thì tiêu đề trống lấy Re: gốc."""
    _, api = _api(session, user_id)
    message, to, cc, subject = _prepare(api, to, cc, subject, body, thread_id)
    data = api.request("POST", f"{GMAIL}/drafts", json={"message": message})
    return _draft_result(data, to, cc, subject, body)


def update_draft(
    session: Session,
    user_id: int,
    google_draft_id: str,
    *,
    to: list[str],
    cc: list[str] | None,
    subject: str | None,
    body: str,
    thread_id: str | None = None,
) -> dict:
    """drafts.update (PATCH /gmail/drafts/{id}); trả như create_draft với body_hash mới."""
    _, api = _api(session, user_id)
    message, to, cc, subject = _prepare(api, to, cc, subject, body, thread_id)
    data = api.request(
        "PUT", f"{GMAIL}/drafts/{google_draft_id}", json={"id": google_draft_id, "message": message}
    )
    return _draft_result(data, to, cc, subject, body)


def delete_draft(session: Session, user_id: int, google_draft_id: str) -> None:
    """Bỏ nháp; nháp đã mất trên Gmail thì coi như xong."""
    _, api = _api(session, user_id)
    try:
        api.request("DELETE", f"{GMAIL}/drafts/{google_draft_id}", ok=(200, 204))
    except GoogleHttpError as exc:
        if exc.status != 404:
            raise


def read_draft(session: Session, user_id: int, google_draft_id: str) -> dict:
    """Nháp đúng như trên Gmail lúc này: `{to, cc, subject, body, body_hash}`."""
    _, api = _api(session, user_id)
    try:
        data = api.request("GET", f"{GMAIL}/drafts/{google_draft_id}", params={"format": "raw"})
    except GoogleHttpError as exc:
        if exc.status == 404:
            raise DraftChanged("Nháp không còn trên Gmail, hãy soạn lại.") from exc
        raise
    msg = BytesParser(policy=policy.default).parsebytes(_b64decode((data.get("message") or {})["raw"]))
    to, cc = _addresses(msg.get("To")), _addresses(msg.get("Cc"))
    part = msg.get_body(preferencelist=("plain",))
    body = part.get_content() if part is not None else ""
    subject = str(msg.get("Subject") or "")
    return {
        "to": to,
        "cc": cc,
        "subject": subject,
        "body": body,
        "body_hash": body_hash(to, cc, subject, body),
    }


def send_draft(session: Session, user_id: int, google_draft_id: str, expected_hash: str) -> dict:
    """Chạy khi người dùng duyệt thẻ send_gmail_draft: băm lại nháp trên Gmail, khớp mới drafts.send.
    Trả `{message_id, thread_id}`; lệch thì ném DraftChanged (ACTION_PAYLOAD_CHANGED)."""
    current = read_draft(session, user_id, google_draft_id)
    if current["body_hash"] != expected_hash:
        raise DraftChanged()
    _, api = _api(session, user_id)
    data = api.request("POST", f"{GMAIL}/drafts/send", json={"id": google_draft_id})
    return {"message_id": data.get("id"), "thread_id": data.get("threadId")}


# ---------- Thư đặt chỗ (QĐ-49) ----------

BOOKING_SENDERS = (
    "booking.com", "agoda.com", "traveloka.com", "trip.com", "airbnb.com", "expedia.com", "vietnamairlines.com",
    "vietjetair.com", "bambooairways.com", "vexere.com", "futabus.vn", "dsvn.vn", "mytour.vn", "ivivu.com",
    "klook.com",
)  # fmt: skip
BOOKING_SUBJECTS = (
    '"xác nhận"', "confirmation", "confirmed", '"đặt phòng"', '"đặt chỗ"', '"vé điện tử"', "e-ticket",
    "reservation", "itinerary", '"hủy đặt"',
)  # fmt: skip
BOOKING_FIRST_DAYS = 60
BOOKING_MAX_PER_SCAN = 50
BOOKING_TEXT_MAX = 20000
BOOKING_OVERLAP = timedelta(minutes=10)


@dataclass
class BookingMail:
    """Thư nghi là đặt chỗ, kèm thân thư dạng chữ (đã bỏ HTML) để module booking gửi AI bóc tách."""

    message_id: str
    thread_id: str
    subject: str
    sender: str
    date: datetime
    text: str
    url: str


def booking_query(since: datetime) -> str:
    """Không lọc category: thư Booking, Agoda... thường nằm ở Cập nhật hoặc Quảng cáo, không ở hộp Chính."""
    terms = [f"from:{d}" for d in BOOKING_SENDERS] + [f"subject:{t}" for t in BOOKING_SUBJECTS]
    return f"after:{int(since.timestamp())} {{{' '.join(terms)}}} -in:spam -in:trash"


def _booking_state(session: Session, account: GoogleAccount) -> GoogleSyncState:
    from sqlalchemy import select

    state = session.scalar(
        select(GoogleSyncState).where(
            GoogleSyncState.google_account_id == account.id,
            GoogleSyncState.service == "gmail",
            GoogleSyncState.resource_id == "bookings",
        )
    )
    if state is None:
        state = GoogleSyncState(
            user_id=account.user_id,
            google_account_id=account.id,
            service="gmail",
            resource_id="bookings",
            needs_sync=False,
            initial_sync_state="done",
        )
        session.add(state)
        session.flush()
    return state


def reset_booking_scan(session: Session, user_id: int, days: int = BOOKING_FIRST_DAYS) -> None:
    """Lần quét sau đọc lại `days` ngày (deploy QĐ-49: bắt thư đặt phòng đã đến trước đó)."""
    account = oauth.require_account(session, user_id, "gmail")
    _booking_state(session, account).updated_min = clock.now() - timedelta(days=days)
    session.flush()


def scan_bookings(session: Session, account: GoogleAccount) -> int:
    """Một lượt quét thư đặt chỗ mới; trả số thư module booking nhận là đặt chỗ."""
    store = stores.booking_store()
    if store is None:
        return 0
    state = _booking_state(session, account)
    started = clock.now()
    since = state.updated_min or started - timedelta(days=BOOKING_FIRST_DAYS)
    api = GoogleApi(session, account)
    data = api.request(
        "GET", f"{GMAIL}/messages", params={"q": booking_query(since), "maxResults": BOOKING_MAX_PER_SCAN}
    )
    ids = [m["id"] for m in data.get("messages") or []]
    done = store.seen(session, account.user_id, ids) if ids else set()
    found = 0
    for message_id in ids:
        if message_id in done:
            continue
        try:
            item = api.request("GET", f"{GMAIL}/messages/{message_id}", params={"format": "full"})
        except GoogleHttpError as exc:
            if exc.status == 404:
                continue
            raise
        h = _headers(item.get("payload"))
        mail = BookingMail(
            message_id=item["id"],
            thread_id=item.get("threadId") or item["id"],
            subject=h.get("subject", ""),
            sender=h.get("from", ""),
            date=_date_of(item),
            text=_text_of(item.get("payload") or {})[:BOOKING_TEXT_MAX],
            url=f"https://mail.google.com/mail/#all/{item['id']}",
        )
        with session.begin_nested():
            if store.handle_booking_mail(session, account.user_id, mail):
                found += 1
    # Lượt đầy thì lần sau đọc tiếp từ chỗ cũ (thư đã xét bỏ qua nhờ seen); không đầy thì tiến tới bây giờ.
    if len(ids) < BOOKING_MAX_PER_SCAN:
        state.updated_min = started - BOOKING_OVERLAP
    state.last_sync_at = started
    session.flush()
    return found


def _scan_bookings_safely(session: Session, account: GoogleAccount) -> None:
    """Lỗi quét đặt chỗ không làm hỏng lượt đồng bộ hộp Chính."""
    if stores.booking_store() is None:
        return
    try:
        with session.begin_nested():
            scan_bookings(session, account)
    except Exception as exc:
        log.warning("Quét thư đặt chỗ lỗi", extra={"user_id": account.user_id, "error": type(exc).__name__})
