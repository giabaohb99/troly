"""Thông báo máy tự phát theo QĐ-38, QĐ-41: giao dịch vừa ghi, tin quan trọng mới, lượt chat xong.

Máy hỏi `GET /device/notices?after=<cursor>` mỗi 15 phút và sau mỗi lô sự kiện. Lần đầu không có
`after` thì chỉ trả `cursor` (không báo dồn). Loại đang tắt ở cài đặt thì bỏ qua, con trỏ vẫn tiến.
Đọc tab_expense, tab_inbox_message bằng SQL, không import ruột module khác.
"""

import re

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


def _parse(cursor: str) -> tuple[int, int, int | None]:
    """Con trỏ `<expense>.<inbox>.<message>`; bản cũ hai phần thì phần chat bắt đầu từ hiện tại."""
    try:
        parts = [int(p) for p in cursor.split(".")]
    except ValueError as exc:
        raise ValidationError(fields={"after": "Con trỏ không hợp lệ."}) from exc
    if len(parts) == 2:
        return parts[0], parts[1], None
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    raise ValidationError(fields={"after": "Con trỏ không hợp lệ."})


def first_sentence(value: str | None) -> str:
    text_ = " ".join((value or "").split())
    head = _SENTENCE.split(text_, maxsplit=1)[0] if text_ else ""
    return (head[: BODY_MAX - 1] + "…") if len(head) > BODY_MAX else head


def _chat_done(session: Session, user_id: int, after: int, upto: int) -> list[dict]:
    """Câu trả lời cuối của mỗi lượt (tin assistant không ẩn) và tệp `export_document` tạo trong lượt."""
    rows = session.execute(
        text(
            "SELECT m.id, m.conversation_id, m.turn_id, m.text, m.created_at FROM tab_message m "
            "WHERE m.user_id = :u AND m.id > :a AND m.id <= :m AND m.role = 'assistant' "
            "AND m.hidden = false AND m.status = 'complete' ORDER BY m.id LIMIT :l"
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
                "file_id": file_ids[0] if file_ids else None,
            }
        )
    return out


def list_notices(session: Session, user_id: int, after: str | None) -> dict:
    exp_max, inbox_max, msg_max = session.execute(
        text(
            "SELECT (SELECT coalesce(max(id), 0) FROM tab_expense WHERE user_id = :u), "
            "(SELECT coalesce(max(id), 0) FROM tab_inbox_message WHERE user_id = :u), "
            "(SELECT coalesce(max(id), 0) FROM tab_message WHERE user_id = :u)"
        ),
        {"u": user_id},
    ).one()
    if after is None:
        return {"items": [], "cursor": f"{exp_max}.{inbox_max}.{msg_max}"}
    exp_after, inbox_after, msg_after = _parse(after)
    items: list[dict] = []
    next_exp, next_inbox, next_msg = exp_max, inbox_max, msg_max

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
                    "deep_link": f"troly://hop-tin/{r.conversation_key}",
                }
            )
        if len(rows) == LIMIT:
            next_inbox = rows[-1].id
    if msg_after is not None and setting_service.get_value(session, user_id, "notify.chat_done"):
        done = _chat_done(session, user_id, msg_after, msg_max)
        items.extend(done)
        if len(done) == LIMIT:
            next_msg = done[-1]["message_id"]
    return {"items": items, "cursor": f"{next_exp}.{next_inbox}.{next_msg}"}
