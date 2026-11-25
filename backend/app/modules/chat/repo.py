"""Đọc ghi bảng chat. Mọi hàm nhận (session, user_id, ...) và lọc theo user_id."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.orm import Session

from app.modules.chat.models import Conversation, Message, PendingAction


def create_conversation(
    session: Session, user_id: int, local_date: date, now: datetime, title: str | None = None
) -> Conversation:
    conv = Conversation(
        user_id=user_id,
        local_date=local_date,
        started_at=now,
        last_message_at=now,
        title=title,
        title_source="user" if title else "auto",
    )
    session.add(conv)
    session.flush()
    return conv


def latest_conversation(session: Session, user_id: int) -> Conversation | None:
    """Phiên hoạt động gần nhất (tin mới nhất, phiên vừa tạo cũng tính)."""
    return session.scalar(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.last_message_at.desc().nulls_last(), Conversation.id.desc())
        .limit(1)
    )


def get_or_create_conversation(
    session: Session, user_id: int, local_date: date, now: datetime
) -> Conversation:
    """Phiên hoạt động gần nhất, chưa có thì tạo (`local_date` chỉ dùng khi tạo). Không còn một phiên mỗi ngày."""
    return latest_conversation(session, user_id) or create_conversation(session, user_id, local_date, now)


def get_conversation(
    session: Session, user_id: int, conversation_id: int, lock: bool = False
) -> Conversation | None:
    stmt = select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    if lock:  # khóa thì đọc lại giá trị mới nhất, không dùng bản cũ trong session
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return session.scalar(stmt)


def list_conversations(
    session: Session,
    user_id: int,
    after: tuple[bool, datetime, int] | None,
    limit: int,
    q: str | None = None,
    empty_since: datetime | None = None,
) -> list[Conversation]:
    """Ghim trước, rồi tin mới nhất giảm dần. `after` là (pinned, last_message_at, id) của dòng cuối trang trước.
    `q` tìm theo tiêu đề (không dấu) và nội dung tin hiện (tìm toàn văn `troly_vn`)."""
    at = func.coalesce(Conversation.last_message_at, Conversation.started_at)
    stmt = select(Conversation).where(Conversation.user_id == user_id)
    if empty_since is not None:
        # Phiên chưa có tin nào chỉ hiện khi vừa tạo bằng nút Phiên mới (phản hồi 1.1.1), trừ phiên người dùng đặt
        # tên hoặc ghim (đoạn chat theo nhu cầu, QĐ-58).
        stmt = stmt.where(
            or_(
                Conversation.message_count > 0,
                Conversation.created_at >= empty_since,
                Conversation.title_source == "user",
                Conversation.pinned.is_(True),
            )
        )
    if q:
        matches = (
            select(Message.conversation_id)
            .where(
                Message.user_id == user_id,
                Message.hidden.is_(False),
                Message.search_vector.op("@@")(func.websearch_to_tsquery("troly_vn", q)),
            )
            .distinct()
        )
        stmt = stmt.where(
            or_(
                func.unaccent(func.coalesce(Conversation.title, "")).ilike(
                    func.concat("%", func.unaccent(q), "%")
                ),
                Conversation.id.in_(matches),
            )
        )
    if after is not None:
        pinned, last_at, last_id = after
        stmt = stmt.where(
            text(
                "(tab_conversation.pinned::int, coalesce(tab_conversation.last_message_at, "
                "tab_conversation.started_at), tab_conversation.id) < (:c_pin, :c_at, :c_id)"
            ).bindparams(c_pin=int(pinned), c_at=last_at, c_id=last_id)
        )
    stmt = stmt.order_by(Conversation.pinned.desc(), at.desc(), Conversation.id.desc()).limit(limit)
    return list(session.scalars(stmt))


def list_history(session: Session, user_id: int, conversation_id: int, after_id: int | None) -> list[Message]:
    stmt = select(Message).where(Message.user_id == user_id, Message.conversation_id == conversation_id)
    if after_id is not None:
        stmt = stmt.where(Message.id > after_id)
    return list(session.scalars(stmt.order_by(Message.id)))


def list_visible(
    session: Session, user_id: int, conversation_id: int, before_id: int | None, limit: int
) -> list[Message]:
    stmt = select(Message).where(
        Message.user_id == user_id, Message.conversation_id == conversation_id, Message.hidden.is_(False)
    )
    if before_id is not None:
        stmt = stmt.where(Message.id < before_id)
    return list(session.scalars(stmt.order_by(Message.id.desc()).limit(limit)))


def last_visible(session: Session, user_id: int, conversation_id: int, limit: int) -> list[Message]:
    rows = list_visible(session, user_id, conversation_id, None, limit)
    return list(reversed(rows))


def get_message(session: Session, user_id: int, message_id: int) -> Message | None:
    return session.scalar(select(Message).where(Message.id == message_id, Message.user_id == user_id))


def find_by_client_id(session: Session, user_id: int, client_message_id: UUID) -> Message | None:
    return session.scalar(
        select(Message).where(Message.user_id == user_id, Message.client_message_id == client_message_id)
    )


def find_turn_answer(session: Session, user_id: int, turn_id: UUID) -> Message | None:
    return session.scalar(
        select(Message)
        .where(
            Message.user_id == user_id,
            Message.turn_id == turn_id,
            Message.role == "assistant",
            Message.hidden.is_(False),
        )
        .order_by(Message.id.desc())
        .limit(1)
    )


def add_message(session: Session, message: Message) -> Message:
    session.add(message)
    session.flush()
    return message


def touch_conversation(
    session: Session, user_id: int, conversation_id: int, at: datetime, visible: bool
) -> None:
    values: dict = {"last_message_at": at, "day_summary_done": False}
    if visible:
        values["message_count"] = Conversation.message_count + 1
    session.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .values(**values)
    )


def set_turn_id(session: Session, user_id: int, message_id: int, turn_id: UUID) -> None:
    session.execute(
        update(Message).where(Message.id == message_id, Message.user_id == user_id).values(turn_id=turn_id)
    )


def delete_conversation(session: Session, user_id: int, conversation_id: int) -> bool:
    conv = get_conversation(session, user_id, conversation_id)
    if conv is None:
        return False
    session.delete(conv)
    return True


def add_pending_action(session: Session, action: PendingAction) -> PendingAction:
    session.add(action)
    session.flush()
    return action


def get_pending_action(
    session: Session, user_id: int, action_id: int, lock: bool = False
) -> PendingAction | None:
    stmt = select(PendingAction).where(PendingAction.id == action_id, PendingAction.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    return session.scalar(stmt)


def list_pending_actions(
    session: Session, user_id: int, statuses: list[str], limit: int = 50
) -> list[PendingAction]:
    return list(
        session.scalars(
            select(PendingAction)
            .where(PendingAction.user_id == user_id, PendingAction.status.in_(statuses))
            .order_by(PendingAction.created_at.desc())
            .limit(limit)
        )
    )


def expire_pending_actions(session: Session, now: datetime) -> int:
    """Việc hệ thống (job), đi qua mọi người dùng."""
    result = session.execute(
        update(PendingAction)
        .where(PendingAction.status == "pending", PendingAction.expires_at <= now)
        .values(status="expired", decided_at=now)
    )
    return result.rowcount or 0
