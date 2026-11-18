"""Luật của chat: phiên theo ngày, nối phiên 3 giờ, lượt chat qua ai.loop.run_turn, duyệt (11 mục 3.7, 12 mục 5.2)."""

import hashlib
import json
import logging
import queue
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.context import UserContext
from app.core.db import SessionLocal
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.ratelimit import limiter
from app.modules.chat import repo
from app.modules.chat.models import Message, PendingAction
from app.modules.file import service as file_service
from app.modules.memory import service as memory_service

log = logging.getLogger("troly.chat")

PREV_TAIL_MESSAGES = 10
APPROVAL_HOURS = 24
PING_SECONDS = 15


class ChatBusy(AppError):
    status = 409
    code = "CHAT_BUSY"
    message = "Trợ lý đang trả lời câu trước."


class ActionNotPending(AppError):
    status = 409
    code = "ACTION_NOT_PENDING"
    message = "Yêu cầu này đã được xử lý hoặc đã hết hạn."


class ActionPayloadChanged(AppError):
    status = 409
    code = "ACTION_PAYLOAD_CHANGED"
    message = "Nội dung đã thay đổi sau khi tạo, nhờ trợ lý làm lại."


_running: set[int] = set()
_running_lock = threading.Lock()


def _claim(user_id: int) -> None:
    with _running_lock:
        if user_id in _running:
            raise ChatBusy()
        _running.add(user_id)


def _release(user_id: int) -> None:
    with _running_lock:
        _running.discard(user_id)


# ---------- Chuyển đổi ----------


def to_claude(m: Message) -> dict:
    """Tin ở dạng Claude, tệp đính kèm thay bằng một dòng chữ (dùng khi tóm tắt)."""
    content = m.content
    if isinstance(content, list):
        content = [
            {"type": "text", "text": f"(tệp đính kèm #{b['file_id']})"}
            if b.get("type") == "troly_file"
            else b
            for b in content
        ]
    return {"role": m.role, "content": content}


def completed_turns(rows: list[Message], current_turn: UUID | None = None) -> list[Message]:
    """Bỏ lượt hỏng (không có câu trả lời): Claude không nhận tin system đứng trước tin user."""
    answered = {m.turn_id for m in rows if m.role == "assistant"}
    return [m for m in rows if m.turn_id in answered or m.turn_id == current_turn]


def serialize_message(m: Message) -> dict:
    return {
        "id": m.id,
        "role": m.role,
        "text": m.text,
        "model": m.model,
        "citations": m.citations or [],
        "attachments": [{"file_id": fid} for fid in (m.attachment_file_ids or [])],
        "actions": m.actions or [],
        "status": m.status,
        "created_at": m.created_at,
    }


def serialize_pending(a: PendingAction) -> dict:
    return {
        "id": a.id,
        "tool_name": a.tool_name,
        "title": a.title,
        "summary": a.summary,
        "details": a.details,
        "danger": a.danger,
        "status": a.status,
        "expires_at": a.expires_at,
        "decided_at": a.decided_at,
        "created_at": a.created_at,
    }


def payload_hash(tool_name: str, data: dict) -> str:
    raw = json.dumps({"tool": tool_name, "input": data}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------- Kho lưu cho ai.loop.run_turn (TurnStore của 20 mục 3.2) ----------


@dataclass
class ChatTurnStore:
    """Cài TurnStore của ai/schemas.py. Dùng chung session của lượt với công cụ: mỗi lần lưu commit
    cả thay đổi công cụ vừa ghi (công cụ chạy trong savepoint của cùng session)."""

    session: Session
    user_id: int
    conversation_id: int
    turn_id: UUID

    def _add(self, **fields) -> int:
        message = repo.add_message(
            self.session,
            Message(
                user_id=self.user_id, conversation_id=self.conversation_id, turn_id=self.turn_id, **fields
            ),
        )
        repo.touch_conversation(
            self.session, self.user_id, self.conversation_id, clock.now(), visible=not fields.get("hidden")
        )
        self.session.commit()
        return message.id

    def save_assistant_message(
        self,
        content: list[dict],
        ai_run_id: int | None,
        model: str,
        text: str | None,
        citations: list[dict] | None,
        hidden: bool,
    ) -> int:
        return self._add(
            role="assistant",
            content=content,
            ai_run_id=ai_run_id,
            model=model,
            text=text,
            citations=citations,
            hidden=hidden,
        )

    def save_tool_results(self, content: list[dict], contains_third_party: bool) -> int:
        return self._add(role="user", content=content, hidden=True, contains_third_party=contains_third_party)

    def create_pending_action(self, tool_name: str, draft) -> int:
        action = repo.add_pending_action(
            self.session,
            PendingAction(
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                tool_name=tool_name,
                input=draft.input,
                payload_hash=payload_hash(tool_name, draft.input),
                title=draft.title,
                summary=draft.summary,
                details=draft.details,
                danger=draft.danger,
                expires_at=clock.now() + timedelta(hours=APPROVAL_HOURS),
            ),
        )
        self.session.commit()
        return action.id


# ---------- Chuẩn bị một lượt ----------


@dataclass
class PreparedTurn:
    user: UserContext
    conversation_id: int
    user_message: dict
    user_message_id: int
    text: str
    mode: str | None
    now: datetime
    turn_id: UUID
    plan: object
    profile_markdown: str
    summary: str
    prev_tail: list
    history: list[dict]
    replay: dict | None = None  # gửi lại cùng client_message_id khi lượt cũ đã xong


def _prev_tail(session: Session, user: UserContext, conversation, now: datetime) -> list:
    from app.ai.schemas import PrevMessage

    if conversation.last_message_at is not None:
        return []  # phiên hôm nay đã có tin: lịch sử đã đủ, không cần nối
    prev = repo.get_previous_conversation(session, user.user_id, conversation.local_date)
    if prev is None or not clock.should_continue_previous(prev.last_message_at, now):
        return []
    tail = [
        m
        for m in repo.last_visible(session, user.user_id, prev.id, PREV_TAIL_MESSAGES * 2)
        if m.role in ("user", "assistant") and m.text
    ]
    return [PrevMessage(role=m.role, text=m.text, at=m.created_at) for m in tail[-PREV_TAIL_MESSAGES:]]


def _maybe_compact(session: Session, user: UserContext, conversation) -> bool:
    """Phiên dài quá AI_COMPACT_TOKENS thì tóm tắt phần đầu (20 mục 3.5). Trả True nếu đã tóm."""
    from app.ai import compaction

    if not compaction.should_compact(conversation.last_prompt_tokens):
        return False
    rows = completed_turns(
        repo.list_history(session, user.user_id, conversation.id, conversation.summary_upto_id)
    )
    messages = [to_claude(m) for m in rows]
    cut = compaction.choose_cut(messages)
    if cut <= 0:
        return False
    from app.ai.schemas import ToolContext

    ctx = ToolContext(session=session, user=user, conversation_id=conversation.id, now=clock.now())
    summary = compaction.summarize(messages[:cut], conversation.summary, ctx)
    if not summary:
        return False
    conversation.summary = summary
    conversation.summary_upto_id = rows[cut - 1].id
    conversation.compacted_count += 1
    conversation.last_prompt_tokens = None
    return True


def prepare_turn(
    session: Session,
    user: UserContext,
    text: str,
    mode: str | None,
    client_message_id: UUID,
    attachment_file_ids: list[int],
) -> PreparedTurn:
    limiter.hit(f"chat:{user.user_id}", get_settings().rate_chat_per_min, 60)
    limiter.hit(f"chat-hour:{user.user_id}", get_settings().ai_user_hourly_turns, 3600)
    now = clock.now()

    existing = repo.find_by_client_id(session, user.user_id, client_message_id)
    if existing is not None:
        answer = repo.find_turn_answer(session, user.user_id, existing.turn_id)
        if answer is None:
            raise ChatBusy()
        return PreparedTurn(
            user=user,
            conversation_id=existing.conversation_id,
            user_message=serialize_message(existing),
            user_message_id=existing.id,
            text=text,
            mode=mode,
            now=now,
            turn_id=existing.turn_id,
            plan=None,
            profile_markdown="",
            summary="",
            prev_tail=[],
            history=[],
            replay={
                "user_message": serialize_message(existing),
                "assistant_message": serialize_message(answer),
            },
        )

    _claim(user.user_id)
    try:
        return _prepare_new_turn(session, user, text, mode, client_message_id, attachment_file_ids, now)
    except BaseException:
        _release(user.user_id)
        raise


def _prepare_new_turn(
    session: Session,
    user: UserContext,
    text: str,
    mode: str | None,
    client_message_id: UUID,
    attachment_file_ids: list[int],
    now: datetime,
) -> PreparedTurn:
    from app.ai.prompt import build_turn_system_message
    from app.ai.router import choose_turn

    plan = choose_turn(text, mode, bool(attachment_file_ids))
    conversation = repo.get_or_create_conversation(
        session, user.user_id, clock.chat_day(now, user.timezone), now
    )
    conversation = repo.get_conversation(session, user.user_id, conversation.id, lock=True)
    _maybe_compact(session, user, conversation)
    prev_tail = _prev_tail(session, user, conversation, now)
    turn_id = uuid.uuid4()

    blocks: list[dict] = file_service.build_claude_blocks(session, user.user_id, attachment_file_ids)
    if text.strip():
        blocks.append({"type": "text", "text": text})
    message = repo.add_message(
        session,
        Message(
            user_id=user.user_id,
            conversation_id=conversation.id,
            turn_id=turn_id,
            role="user",
            content=blocks,
            text=text,
            client_message_id=client_message_id,
            attachment_file_ids=attachment_file_ids,
        ),
    )
    repo.touch_conversation(session, user.user_id, conversation.id, now, visible=True)
    time_message = build_turn_system_message(now, user.timezone, plan)
    repo.add_message(
        session,
        Message(
            user_id=user.user_id,
            conversation_id=conversation.id,
            turn_id=turn_id,
            role="system",
            content=time_message["content"],
            text=None,
            hidden=True,
        ),
    )
    rows = completed_turns(
        repo.list_history(session, user.user_id, conversation.id, conversation.summary_upto_id), turn_id
    )
    history = [
        {"role": m.role, "content": file_service.materialize_blocks(session, user.user_id, m.content)}
        for m in rows
    ]
    profile = memory_service.get_profile_markdown(session, user.user_id)
    session.commit()
    return PreparedTurn(
        user=user,
        conversation_id=conversation.id,
        user_message=serialize_message(message),
        user_message_id=message.id,
        text=text,
        mode=mode,
        now=now,
        turn_id=turn_id,
        plan=plan,
        profile_markdown=profile,
        summary=conversation.summary or "",
        prev_tail=prev_tail,
        history=history,
    )


# ---------- Chạy lượt ----------


def _finish(prepared: PreparedTurn, data: dict) -> dict:
    """Lưu hành động, số token lời nhắc; trả dữ liệu cho message.completed."""
    with SessionLocal() as session:
        conversation = repo.get_conversation(
            session, prepared.user.user_id, prepared.conversation_id, lock=True
        )
        if conversation is not None and data.get("last_prompt_tokens"):
            conversation.last_prompt_tokens = data["last_prompt_tokens"]
        assistant = None
        if data.get("message_id"):
            assistant = repo.get_message(session, prepared.user.user_id, data["message_id"])
            if assistant is not None:
                assistant.actions = data.get("actions") or None
        session.commit()
        return {
            "assistant_message": serialize_message(assistant) if assistant else None,
            "usage": data.get("usage") or {},
        }


def _mark_failed(prepared: PreparedTurn) -> None:
    with SessionLocal() as session:
        message = repo.get_message(session, prepared.user.user_id, prepared.user_message_id)
        if message is not None:
            message.status = "failed"
        session.commit()


def iter_turn_events(prepared: PreparedTurn) -> Iterator[tuple[str, dict]]:
    """Chạy run_turn trong một session riêng của lượt, đổi sự kiện ai/ sang SSE của 12 mục 5.2."""
    try:
        from app.ai.loop import run_turn
        from app.ai.schemas import AiError, SystemParts, ToolContext

        with SessionLocal() as session:
            ctx = ToolContext(
                session=session,
                user=prepared.user,
                conversation_id=prepared.conversation_id,
                now=prepared.now,
            )
            parts = SystemParts(
                profile_md=prepared.profile_markdown,
                summary=prepared.summary or None,
                prev_tail=prepared.prev_tail,
            )
            store = ChatTurnStore(session, prepared.user.user_id, prepared.conversation_id, prepared.turn_id)
            try:
                for event in run_turn(ctx, prepared.plan, parts, prepared.history, store):
                    if event.type == "turn.completed":
                        session.commit()
                        yield "message.completed", _finish(prepared, event.data)
                    else:
                        yield event.type, event.data
            except AiError as exc:
                session.rollback()
                _mark_failed(prepared)
                yield "error", {"code": exc.code, "message": exc.message}
    except Exception:
        log.exception("Lượt chat hỏng")
        _mark_failed(prepared)
        yield "error", {"code": "AI_UNAVAILABLE", "message": "Trợ lý đang bận, thử lại sau."}


def _sse(name: str, data: dict | None = None) -> str:
    from fastapi.encoders import jsonable_encoder

    return f"event: {name}\ndata: {json.dumps(jsonable_encoder(data or {}), ensure_ascii=False)}\n\n"


def stream_turn(prepared: PreparedTurn) -> Iterator[str]:
    """Luồng SSE. Lượt chạy trong luồng riêng để mất kết nối vẫn chạy hết và lưu (12 mục 5.2)."""
    if prepared.replay is not None:
        yield _sse(
            "message.created",
            {"user_message": prepared.replay["user_message"], "conversation_id": prepared.conversation_id},
        )
        yield _sse(
            "message.completed", {"assistant_message": prepared.replay["assistant_message"], "usage": {}}
        )
        return

    events: queue.Queue = queue.Queue()
    done = object()

    def worker() -> None:
        try:
            for item in iter_turn_events(prepared):
                events.put(item)
        finally:
            _release(prepared.user.user_id)
            events.put(done)

    threading.Thread(target=worker, name=f"chat-turn-{prepared.user_message_id}", daemon=True).start()
    yield _sse(
        "message.created",
        {"user_message": prepared.user_message, "conversation_id": prepared.conversation_id},
    )
    while True:
        try:
            item = events.get(timeout=PING_SECONDS)
        except queue.Empty:
            yield ": ping\n\n"
            continue
        if item is done:
            return
        name, data = item
        yield _sse(name, data)


def run_turn_json(prepared: PreparedTurn) -> dict:
    if prepared.replay is not None:
        return {**prepared.replay, "actions": prepared.replay["assistant_message"]["actions"]}
    try:
        result: dict = {"user_message": prepared.user_message, "assistant_message": None, "actions": []}
        for name, data in iter_turn_events(prepared):
            if name == "action":
                result["actions"].append(data)
            elif name == "message.completed":
                result["assistant_message"] = data["assistant_message"]
                result["usage"] = data["usage"]
            elif name == "error":
                raise AppError(data.get("message"), code=data.get("code", "AI_UNAVAILABLE"), status=502)
        return result
    finally:
        _release(prepared.user.user_id)


# ---------- Trang và phiên ----------


def get_today(session: Session, user: UserContext) -> dict:
    now = clock.now()
    conversation = repo.get_or_create_conversation(
        session, user.user_id, clock.chat_day(now, user.timezone), now
    )
    rows = repo.list_visible(session, user.user_id, conversation.id, None, 51)
    has_more = len(rows) > 50
    rows = list(reversed(rows[:50]))
    pending = repo.list_pending_actions(session, user.user_id, ["pending"])
    return {
        "conversation": serialize_conversation(conversation),
        "messages": [serialize_message(m) for m in rows],
        "next_cursor": str(rows[0].id) if has_more and rows else None,
        "pending_actions": [serialize_pending(a) for a in pending],
    }


def serialize_conversation(c) -> dict:
    return {"id": c.id, "local_date": c.local_date, "summary": c.summary, "message_count": c.message_count}


def list_conversations(session: Session, user: UserContext, cursor: str | None, limit: int) -> dict:
    from datetime import date

    before = date.fromisoformat(cursor) if cursor else None
    rows = repo.list_conversations(session, user.user_id, before, limit + 1)
    items = rows[:limit]
    return {
        "items": [serialize_conversation(c) for c in items],
        "next_cursor": items[-1].local_date.isoformat() if len(rows) > limit else None,
    }


def list_messages(
    session: Session, user: UserContext, conversation_id: int, cursor: str | None, limit: int
) -> dict:
    if repo.get_conversation(session, user.user_id, conversation_id) is None:
        raise NotFoundError()
    rows = repo.list_visible(
        session, user.user_id, conversation_id, int(cursor) if cursor else None, limit + 1
    )
    items = list(reversed(rows[:limit]))
    return {
        "items": [serialize_message(m) for m in items],
        "next_cursor": str(items[0].id) if len(rows) > limit and items else None,
    }


def delete_conversation(session: Session, user: UserContext, conversation_id: int) -> None:
    if not repo.delete_conversation(session, user.user_id, conversation_id):
        raise NotFoundError()


# ---------- Duyệt hành động (12 mục 5.2) ----------


def list_actions(session: Session, user: UserContext, status: str) -> list[dict]:
    statuses = [s.strip() for s in status.split(",") if s.strip()]
    return [serialize_pending(a) for a in repo.list_pending_actions(session, user.user_id, statuses)]


def _system_note(session: Session, action: PendingAction, text: str) -> None:
    if action.conversation_id is None:
        return
    repo.add_message(
        session,
        Message(
            user_id=action.user_id,
            conversation_id=action.conversation_id,
            turn_id=uuid.uuid4(),
            role="system",
            content=text,
            text=text,
            hidden=True,
        ),
    )


def decide_action(session: Session, user: UserContext, action_id: int, approve: bool) -> dict:
    from app.ai.registry import get_tool
    from app.ai.schemas import ToolContext

    action = repo.get_pending_action(session, user.user_id, action_id, lock=True)
    if action is None:
        raise NotFoundError()
    now = clock.now()
    if action.status != "pending" or action.expires_at <= now:
        raise ActionNotPending()
    if action.payload_hash != payload_hash(action.tool_name, action.input):
        raise ActionPayloadChanged()
    action.decided_at = now
    if not approve:
        action.status = "rejected"
        _system_note(session, action, f"Người dùng đã bỏ: {action.title}.")
        return {"action": serialize_pending(action), "result_text": "Đã bỏ."}

    spec = get_tool(action.tool_name)
    if spec is None or spec.execute is None:
        raise ConflictError("Công cụ này không còn, không chạy được.")
    ctx = ToolContext(session=session, user=user, conversation_id=action.conversation_id, now=now)
    try:
        with session.begin_nested():
            output = spec.execute(ctx, action.input)
        action.status = "done"
        action.result = output.result if isinstance(output.result, dict) else {"result": output.result}
        result_text = "thành công"
    except AppError as exc:
        action.status = "failed"
        action.error = exc.message
        result_text = f"thất bại ({exc.message})"
    _system_note(session, action, f"Người dùng đã duyệt: {action.title}. Kết quả: {result_text}.")
    return {"action": serialize_pending(action), "result_text": action.error or "Đã làm xong."}


def expire_actions(session: Session) -> int:
    return repo.expire_pending_actions(session, clock.now())
