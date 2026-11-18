"""Job của chat: tóm tắt phiên hôm trước lúc 04:05, hết hạn hành động chờ duyệt (10 mục 3.9)."""

import logging

from sqlalchemy import select

from app.core import clock
from app.core.context import UserContext
from app.core.db import SessionLocal
from app.core.models import User
from app.modules.chat import repo, service
from app.modules.chat.models import Conversation

log = logging.getLogger("troly.chat.jobs")


def summarize_previous_day() -> int:
    """Phiên của những ngày trước chưa có tóm tắt cuối ngày thì tóm (gộp tóm tắt cũ nếu có)."""
    from app.ai import compaction
    from app.ai.schemas import AiError, ToolContext

    done = 0
    with SessionLocal() as session:
        users = {u.id: u.timezone for u in session.scalars(select(User))}
        rows = list(
            session.scalars(
                select(Conversation).where(
                    Conversation.day_summary_done.is_(False), Conversation.message_count > 0
                )
            )
        )
        for conv in rows:
            tz = users.get(conv.user_id)
            if tz is None or conv.local_date >= clock.chat_day(clock.now(), tz):
                continue
            user = UserContext(user_id=conv.user_id, timezone=tz)
            history = service.completed_turns(
                repo.list_history(session, conv.user_id, conv.id, conv.summary_upto_id)
            )
            messages = [service.to_claude(m) for m in history]
            if not messages:
                conv.day_summary_done = True
                continue
            ctx = ToolContext(session=session, user=user, conversation_id=conv.id, now=clock.now())
            try:
                summary = compaction.summarize(messages, conv.summary, ctx)
            except AiError as exc:
                log.warning("Không tóm được phiên", extra={"conversation_id": conv.id, "code": exc.code})
                session.rollback()
                break  # lỗi khóa hoặc Claude: thử lại ở lần chạy sau
            if summary:
                conv.summary = summary
                conv.summary_upto_id = history[-1].id
                conv.day_summary_done = True
                done += 1
            session.commit()
    return done


def expire_pending_actions() -> int:
    with SessionLocal() as session:
        count = service.expire_actions(session)
        session.commit()
        return count
