"""Job của chat: tóm phiên ngủ lâu hoặc quá dài, hết hạn hành động chờ duyệt (10 mục 3.9).

QĐ-51: không còn tách phiên lúc 04:00 nên không tóm theo ngày. Phiên ngủ quá IDLE_HOURS, hoặc có quá
LONG_MESSAGES tin chưa tóm, thì tóm phần đầu và giữ nguyên phần đuôi (compaction.choose_cut), để mở lại phiên
cũ nạp tóm tắt cộng đuôi như nén trong lượt.
"""

import logging
from datetime import timedelta

from sqlalchemy import func, or_, select

from app.core import clock
from app.core.context import UserContext
from app.core.db import SessionLocal
from app.core.models import User
from app.modules.chat import repo, service
from app.modules.chat.models import Conversation, Message

log = logging.getLogger("troly.chat.jobs")

IDLE_HOURS = 6
LONG_MESSAGES = 80
BATCH = 20


def _due(session, now) -> list[Conversation]:
    unsummarized = (
        select(func.count(Message.id))
        .where(
            Message.conversation_id == Conversation.id,
            Message.hidden.is_(False),
            Message.id > func.coalesce(Conversation.summary_upto_id, 0),
        )
        .correlate(Conversation)
        .scalar_subquery()
    )
    return list(
        session.scalars(
            select(Conversation)
            .where(
                Conversation.day_summary_done.is_(False),
                Conversation.message_count > 0,
                or_(
                    Conversation.last_message_at < now - timedelta(hours=IDLE_HOURS),
                    unsummarized >= LONG_MESSAGES,
                ),
            )
            .order_by(Conversation.last_message_at)
            .limit(BATCH)
        )
    )


def summarize_idle_conversations() -> int:
    from app.ai import compaction
    from app.ai.schemas import AiError, ToolContext

    done = 0
    now = clock.now()
    with SessionLocal() as session:
        users = {u.id: u.timezone for u in session.scalars(select(User))}
        for conv in _due(session, now):
            tz = users.get(conv.user_id)
            if tz is None:
                continue
            history = service.completed_turns(
                repo.list_history(session, conv.user_id, conv.id, conv.summary_upto_id)
            )
            messages = [service.to_claude(m) for m in history]
            cut = compaction.choose_cut(messages) if messages else 0
            if cut <= 0:  # còn ngắn: đuôi đã đủ, không cần tóm
                conv.day_summary_done = True
                session.commit()
                continue
            user = UserContext(user_id=conv.user_id, timezone=tz)
            ctx = ToolContext(session=session, user=user, conversation_id=conv.id, now=now)
            try:
                summary = compaction.summarize(messages[:cut], conv.summary, ctx)
            except AiError as exc:
                log.warning("Không tóm được phiên", extra={"conversation_id": conv.id, "code": exc.code})
                session.rollback()
                break  # lỗi khóa hoặc Claude: thử lại ở lần chạy sau
            if summary:
                conv.summary = summary
                conv.summary_upto_id = history[cut - 1].id
                conv.day_summary_done = True
                done += 1
            session.commit()
    return done


def expire_pending_actions() -> int:
    with SessionLocal() as session:
        count = service.expire_actions(session)
        session.commit()
        return count
