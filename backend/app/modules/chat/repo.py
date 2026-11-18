"""Đọc ghi bảng chat. Mọi hàm nhận (session, user_id, ...) và lọc theo user_id."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.chat.models import Conversation, Message, PendingAction


def get_or_create_conversation(
    session: Session, user_id: int, local_date: date, now: datetime
) -> Conversation:
    stmt = (
        insert(Conversation)
        .values(user_id=user_id, local_date=local_date, started_at=now)
        .on_conflict_do_nothing(index_elements=["user_id", "local_date"])
    )
    session.execute(stmt)
    return session.scalar(
        select(Conversation).where(Conversation.user_id == user_id, Conversation.local_date == local_date)
    )


def get_conversation(
    session: Session, user_id: int, conversation_id: int, lock: bool = False
) -> Conversation | None:
    stmt = select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    return session.scalar(stmt)


def get_previous_conversation(session: Session, user_id: int, before: date) -> Conversation | None:
    return session.scalar(
        select(Conversation)
        .where(Conversation.user_id == user_id, Conversation.local_date < before)
        .order_by(Conversation.local_date.desc())
        .limit(1)
    )


def list_conversations(
    session: Session, user_id: int, before_date: date | None, limit: int
) -> list[Conversation]:
    stmt = select(Conversation).where(Conversation.user_id == user_id)
    if before_date is not None:
        stmt = stmt.where(Conversation.local_date < before_date)
    return list(session.scalars(stmt.order_by(Conversation.local_date.desc()).limit(limit)))


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
    values: dict = {"last_message_at": at}
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
