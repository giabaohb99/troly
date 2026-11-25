"""Thông báo máy tự phát theo QĐ-38, QĐ-41, QĐ-49: giao dịch vừa ghi, tin quan trọng mới, lượt chat xong,
đặt chỗ vừa tự thêm vào Lịch.

Máy hỏi `GET /device/notices?after=<cursor>` mỗi 15 phút và sau mỗi lô sự kiện. Lần đầu không có
`after` thì chỉ trả `cursor` (không báo dồn). Loại đang tắt ở cài đặt thì bỏ qua, con trỏ vẫn tiến.
Đọc tab_expense, tab_inbox_message bằng SQL, không import ruột module khác.
"""

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.modules.setting import service as setting_service

LIMIT = 50
BODY_MAX = 120
_KIND_WORD = {"expense": "chi", "income": "thu", "transfer": "chuyển"}


def _money(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + " đ"


# Kết quả công cụ có thể là chuỗi JSON lồng trong JSON (dấu ngoặc kép bị thoát).
_FILE_ID = re.compile(r'file_id\\?"\s*:\s*(\d+)')
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")


def _parse(cursor: str) -> tuple[int, int, int | None, int | None]:
    """Con trỏ `<expense>.<inbox>.<message>.<booking>`; bản cũ thiếu phần sau thì phần đó tính từ hiện tại
    (không báo dồn)."""
    try:
        parts: list[int | None] = [int(p) for p in cursor.split(".")]
    except ValueError as exc:
        raise ValidationError(fields={"after": "Con trỏ không hợp lệ."}) from exc
    if not 2 <= len(parts) <= 4:
        raise ValidationError(fields={"after": "Con trỏ không hợp lệ."})
    parts += [None] * (4 - len(parts))
    return parts[0], parts[1], parts[2], parts[3]


# ---------- Đặt chỗ (QĐ-49) ----------
# Bảng `tab_booking` của module booking (agent Google, migration `0013_booking`). Chưa có bảng thì bỏ qua.

_WEEKDAY = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")


def _has_booking_table(session: Session) -> bool:
    return session.execute(text("SELECT to_regclass('tab_booking') IS NOT NULL")).scalar_one()


def _when(at: datetime | None, day: date | None, tz: str) -> str:
    if at is not None:
        local = at.astimezone(ZoneInfo(tz))
        return f"{_WEEKDAY[local.weekday()]} {local:%d/%m %H:%M}"
    if day is not None:
        return f"{_WEEKDAY[day.weekday()]} {day:%d/%m}"
    return ""


def _booking_added(session: Session, user_id: int, after: int, upto: int, tz: str) -> list[dict]:
    """Đặt chỗ đã tự thêm vào Lịch (`calendar_state = added`, có sự kiện); máy hiện nút Hoàn tác gọi
    `POST /device/bookings/{booking_id}/undo`."""
    rows = session.execute(
        text(
            "SELECT id, title, start_at, start_date, event_id, created_at FROM tab_booking "
            "WHERE user_id = :u AND id > :a AND id <= :m AND calendar_state = 'added' AND event_id IS NOT NULL "
            "ORDER BY id LIMIT :l"
        ),
        {"u": user_id, "a": after, "m": upto, "l": LIMIT},
    ).all()
    out = []
    for r in rows:
        body = ", ".join(x for x in ((r.title or "").strip(), _when(r.start_at, r.start_date, tz)) if x)
        out.append(
            {
                "id": f"booking:{r.id}",
                "kind": "booking_added",
                "created_at": r.created_at,
                "title": "Đã thêm đặt chỗ vào Lịch",
                "body": body[:BODY_MAX] or "Mở Lịch để xem.",
                "deep_link": f"troly://lich/su-kien/{r.event_id}",
                "booking_id": r.id,
                "event_id": r.event_id,
            }
        )
    return out


def first_sentence(value: str | None) -> str:
    text_ = " ".join((value or "").split())
    head = _SENTENCE.split(text_, maxsplit=1)[0] if text_ else ""
    return (head[: BODY_MAX - 1] + "…") if len(head) > BODY_MAX else head


def _chat_done(session: Session, user_id: int, after: int, upto: int) -> list[dict]:
    """Câu trả lời cuối của lượt app chưa nhận hết (`notify_done`, SSE ngắt giữa chừng) và tệp
    `export_document` tạo trong lượt. Lượt app đã nhận đủ, lượt JSON thì không báo (lỗi báo trùng 19/11)."""
    rows = session.execute(
        text(
            "SELECT m.id, m.conversation_id, m.turn_id, m.text, m.created_at FROM tab_message m "
            "WHERE m.user_id = :u AND m.id > :a AND m.id <= :m AND m.role = 'assistant' "
            "AND m.hidden = false AND m.status = 'complete' AND m.notify_done ORDER BY m.id LIMIT :l"
        ),
        {"u": user_id, "a": after, "m": upto, "l": LIMIT},
    ).all()
    out = []
    for r in rows:
        tool_results = session.execute(
            text(
                "SELECT content::text FROM tab_message WHERE user_id = :u AND turn_id = :t "
                "AND role = 'user' AND hidden = true"
            ),
            {"u": user_id, "t": r.turn_id},
        ).scalars()
        candidates = sorted({int(x) for c in tool_results for x in _FILE_ID.findall(c)})
        file_ids = []
        if candidates:
            file_ids = list(
                session.execute(
                    text(
                        "SELECT id FROM tab_file WHERE user_id = :u AND id = ANY(:ids) AND purpose = 'document' "
                        "AND deleted_at IS NULL ORDER BY id"
                    ),
                    {"u": user_id, "ids": candidates},
                ).scalars()
            )
        out.append(
            {
                "id": f"chat:{r.id}",
                "kind": "chat_done",
                "title": "Trợ lý đã trả lời" if not file_ids else "Trợ lý đã xong tệp",
                "body": first_sentence(r.text) or "Mở để xem câu trả lời.",
                "deep_link": f"troly://?phien={r.conversation_id}&tin={r.id}",
                "conversation_id": r.conversation_id,
                "message_id": r.id,
                "file_ids": file_ids,
                "created_at": r.created_at,  # giờ tạo tin trả lời (có múi giờ); app bỏ notice cũ hơn 15 phút
                "file_id": file_ids[0] if file_ids else None,
            }
        )
    return out


def list_notices(
    session: Session, user_id: int, after: str | None, timezone: str = "Asia/Ho_Chi_Minh"
) -> dict:
    has_booking = _has_booking_table(session)
    booking_max = (
        session.execute(
            text("SELECT coalesce(max(id), 0) FROM tab_booking WHERE user_id = :u"), {"u": user_id}
        ).scalar_one()
        if has_booking
        else 0
    )
    exp_max, inbox_max, msg_max = session.execute(
        text(
            "SELECT (SELECT coalesce(max(id), 0) FROM tab_expense WHERE user_id = :u), "
            "(SELECT coalesce(max(id), 0) FROM tab_inbox_message WHERE user_id = :u), "
            "(SELECT coalesce(max(id), 0) FROM tab_message WHERE user_id = :u)"
        ),
        {"u": user_id},
    ).one()
    if after is None:
        return {"items": [], "cursor": f"{exp_max}.{inbox_max}.{msg_max}.{booking_max}"}
    exp_after, inbox_after, msg_after, booking_after = _parse(after)
    items: list[dict] = []
    next_exp, next_inbox, next_msg, next_booking = exp_max, inbox_max, msg_max, booking_max

    if setting_service.get_value(session, user_id, "notify.new_transaction"):
        rows = session.execute(
            text(
                "SELECT id, amount_vnd, kind, merchant, note, account FROM tab_expense "
                "WHERE user_id = :u AND id > :a AND id <= :m AND source = 'bank_notification' "
                "AND deleted_at IS NULL ORDER BY id LIMIT :l"
            ),
            {"u": user_id, "a": exp_after, "m": exp_max, "l": LIMIT},
        ).all()
        for r in rows:
            items.append(
                {
                    "id": f"expense:{r.id}",
                    "kind": "transaction",
                    "title": f"Đã ghi {_KIND_WORD.get(r.kind, 'chi')} {_money(r.amount_vnd)}",
                    "body": (r.merchant or r.note or r.account.upper())[:BODY_MAX],
                    "deep_link": f"troly://chi-tieu?sua={r.id}",
                }
            )
        if len(rows) == LIMIT:
            next_exp = rows[-1].id

    if setting_service.get_value(session, user_id, "notify.important_message"):
        rows = session.execute(
            text(
                "SELECT id, sender, conversation_title, is_group, text, conversation_key FROM tab_inbox_message "
                "WHERE user_id = :u AND id > :a AND id <= :m AND importance = 'important' AND status = 'new' "
                "AND NOT EXISTS (SELECT 1 FROM tab_listened_app a WHERE a.user_id = tab_inbox_message.user_id "
                "AND a.purpose = 'inbox' AND a.enabled = false AND a.parser = tab_inbox_message.app) "
                "ORDER BY id LIMIT :l"
            ),
            {"u": user_id, "a": inbox_after, "m": inbox_max, "l": LIMIT},
        ).all()
        for r in rows:
            who = r.sender or r.conversation_title or "Tin nhắn"
            if r.is_group and r.conversation_title:
                who = f"{who} ({r.conversation_title})"
            items.append(
                {
                    "id": f"inbox:{r.id}",
                    "kind": "important_message",
                    "title": who[:BODY_MAX],
                    "body": r.text[:BODY_MAX],
                    "deep_link": (
                        f"troly://zalo/{r.conversation_key}"
                        if r.conversation_key.startswith("zalo:")
                        else f"troly://hop-tin/{r.conversation_key}"
                    ),
                }
            )
        if len(rows) == LIMIT:
            next_inbox = rows[-1].id
    if msg_after is not None and setting_service.get_value(session, user_id, "notify.chat_done"):
        done = _chat_done(session, user_id, msg_after, msg_max)
        items.extend(done)
        if len(done) == LIMIT:
            next_msg = done[-1]["message_id"]
    if (
        has_booking
        and booking_after is not None
        and setting_service.get_value(session, user_id, "notify.booking_added")
    ):
        added = _booking_added(session, user_id, booking_after, booking_max, timezone)
        items.extend(added)
        if len(added) == LIMIT:
            next_booking = added[-1]["booking_id"]
    return {"items": items, "cursor": f"{next_exp}.{next_inbox}.{next_msg}.{next_booking}"}
