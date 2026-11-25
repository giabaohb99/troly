"""Luật của chat: phiên đặt tên mở lại được (QĐ-51), lượt chat qua ai.loop.run_turn, duyệt (11 mục 3.7,
12 mục 5.2). Không tách phiên lúc 04:00; tin không chỉ phiên thì vào phiên hoạt động gần nhất."""

import hashlib
import json
import logging
import os
import queue
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
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

APPROVAL_HOURS = 24
PING_SECONDS = 15
# Lượt xong mà SSE chưa đọc qua sự kiện kết thúc sau ngần này giây: app đã ngắt, cần notice chat_done.
DELIVERY_GRACE_SECONDS = 5


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


def _attachments(m: Message) -> list[dict]:
    """Tin người dùng: tệp đính kèm. Tin trợ lý: tệp bot xuất (QĐ-41), lấy từ hành động `file` đã lưu."""
    items = [{"file_id": fid} for fid in (m.attachment_file_ids or [])]
    for a in m.actions or []:
        if isinstance(a, dict) and a.get("type") == "file" and a.get("file_id"):
            items.append({k: a.get(k) for k in ("file_id", "mime", "name", "size_bytes")})
    return items


def serialize_message(m: Message) -> dict:
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "role": m.role,
        "text": m.text,
        "model": m.model,
        "citations": m.citations or [],
        "attachments": _attachments(m),
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
        "error": a.error,
        "expires_at": a.expires_at,
        "decided_at": a.decided_at,
        "created_at": a.created_at,
    }


def payload_hash(tool_name: str, data: dict) -> str:
    raw = json.dumps({"tool": tool_name, "input": data}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def create_pending_action(
    session: Session,
    user_id: int,
    tool_name: str,
    input_: dict,
    *,
    title: str,
    summary: str,
    details: list[dict],
    danger: bool = False,
    conversation_id: int | None = None,
) -> dict:
    """Thẻ duyệt tạo từ API (không qua chat), ví dụ sự kiện có khách mời (QĐ-23).

    Trả `PendingAction` cùng hành động `confirm` để app hiện thẻ; duyệt qua /chat/actions/{id}/approve.
    """
    from app.ai import actions

    action = repo.add_pending_action(
        session,
        PendingAction(
            user_id=user_id,
            conversation_id=conversation_id,
            tool_name=tool_name,
            input=input_,
            payload_hash=payload_hash(tool_name, input_),
            title=title,
            summary=summary,
            details=details,
            danger=danger,
            expires_at=clock.now() + timedelta(hours=APPROVAL_HOURS),
        ),
    )
    return {
        **serialize_pending(action),
        "action": {
            "id": "a1",
            **actions.confirm(
                pending_action_id=action.id,
                title=title,
                summary=summary,
                details=details,
                danger=danger,
                expires_at=action.expires_at,
            ),
        },
    }


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
        contains_third_party: bool = False,
    ) -> int:
        return self._add(
            role="assistant",
            content=content,
            ai_run_id=ai_run_id,
            model=model,
            text=text,
            citations=citations,
            hidden=hidden,
            contains_third_party=contains_third_party,
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


TITLE_MAX = 120


def _clean_title(value: str | None) -> str | None:
    title = " ".join((value or "").split())[:TITLE_MAX]
    return title or None


def _target_conversation(session: Session, user: UserContext, conversation_id: int | None, now: datetime):
    """Phiên nhận tin (QĐ-51): phiên chỉ định (không có thì 404), không thì phiên hoạt động gần nhất,
    chưa có thì tạo. Khóa dòng phiên cho tới hết chuẩn bị lượt."""
    if conversation_id is not None:
        conv = repo.get_conversation(session, user.user_id, conversation_id, lock=True)
        if conv is None:
            raise NotFoundError("Không tìm thấy phiên chat.")
        return conv
    conv = repo.get_or_create_conversation(session, user.user_id, clock.chat_day(now, user.timezone), now)
    return repo.get_conversation(session, user.user_id, conv.id, lock=True)


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
    conversation_id: int | None = None,
    use_connectors: bool | list[int] | None = None,
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
        return _prepare_new_turn(
            session,
            user,
            text,
            mode,
            client_message_id,
            attachment_file_ids,
            now,
            conversation_id,
            use_connectors,
        )
    except BaseException:
        _release(user.user_id)
        raise


def _previous_task(session: Session, user: UserContext, conversation_id: int) -> str | None:
    """Việc của lượt trước, chỉ khi bot kết lượt đó bằng câu hỏi (đang chờ người dùng đáp: ngày đi, *tìm nhé?*)."""
    from app.ai.prompt import turn_task_of

    task = turn_task_of(_last_turn_rules(session, user, conversation_id))
    if task is None:
        return None
    last = session.scalar(
        select(Message.text)
        .where(
            Message.user_id == user.user_id,
            Message.conversation_id == conversation_id,
            Message.role == "assistant",
            Message.hidden.is_(False),
        )
        .order_by(Message.id.desc())
        .limit(1)
    )
    return task if last and last.rstrip().endswith("?") else None


def _last_turn_rules(session: Session, user: UserContext, conversation_id: int) -> str | None:
    """Tin thời điểm (ẩn) của lượt gần nhất trong phiên: chứa luật riêng của lượt đó (vd. dựng chuyến).
    Bỏ qua ghi chú duyệt, bỏ thẻ (cũng là tin hệ thống ẩn)."""
    from app.ai.prompt import TIME_PREFIX

    rows = session.scalars(
        select(Message.content)
        .where(
            Message.user_id == user.user_id,
            Message.conversation_id == conversation_id,
            Message.role == "system",
            Message.hidden.is_(True),
        )
        .order_by(Message.id.desc())
        .limit(5)
    )
    for content in rows:
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        if text.startswith(TIME_PREFIX) or TIME_PREFIX in text[:200]:
            return text
    return None


def _prepare_new_turn(
    session: Session,
    user: UserContext,
    text: str,
    mode: str | None,
    client_message_id: UUID,
    attachment_file_ids: list[int],
    now: datetime,
    conversation_id: int | None = None,
    use_connectors: bool | list[int] | None = None,
) -> PreparedTurn:
    from app.ai.mcp import active_connectors
    from app.ai.prompt import build_turn_system_message
    from app.ai.router import choose_turn

    conversation = _target_conversation(session, user, conversation_id, now)
    plan = choose_turn(
        text,
        mode,
        bool(attachment_file_ids),
        previous_task=_previous_task(session, user, conversation.id),
        use_connectors=use_connectors,
        connectors=active_connectors(session, user.user_id),
    )
    try:
        _maybe_compact(session, user, conversation)
    except Exception:  # nén là việc phụ: lỗi thì lượt vẫn chạy như không nén
        log.exception("Nén phiên lỗi")
    # Không còn nối đuôi phiên hôm trước (QĐ-51): phiên mở lại tự có tóm tắt và tin chưa tóm.
    prev_tail: list = []
    turn_id = uuid.uuid4()

    from app.ai.redact import mask_secrets

    # QĐ-46: khóa API dán vào chat không được lưu DB, không gửi Claude.
    text, secret_masked = mask_secrets(text)
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
    time_message = build_turn_system_message(now, user.timezone, plan, secret_masked)
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
        user_message=with_file_meta(session, user.user_id, [serialize_message(message)])[0],
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
    answer_text = None  # lượt xong thì đặt tên phiên sau khi đóng session của lượt
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
                        done = _finish(prepared, event.data)
                        answer_text = (done.get("assistant_message") or {}).get("text") or ""
                        yield "message.completed", done
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
        return
    if answer_text is not None:
        maybe_auto_title(prepared, answer_text)


# ---------- Đặt tên phiên tự động (QĐ-51) ----------

# Bài kiểm chạy chung FakeClaude: lời gọi đặt tên ở nền sẽ lấy mất câu trả lời trong kịch bản, nên khi ENV=test chỉ
# chạy nếu bài kiểm bật AUTO_TITLE_IN_TESTS; AUTO_TITLE_BACKGROUND = False để chạy đồng bộ cho dễ kiểm.
AUTO_TITLE_IN_TESTS = False
AUTO_TITLE_BACKGROUND = True


def _auto_title_on() -> bool:
    return os.environ.get("ENV") != "test" or AUTO_TITLE_IN_TESTS


def maybe_auto_title(prepared: PreparedTurn, answer: str) -> None:
    """Sau lượt trả lời của phiên chưa có tên: Haiku đặt tên ngắn, ghi qua set_auto_title (không đè tên người dùng)."""
    if not _auto_title_on():
        return
    user_id, conversation_id, question = prepared.user.user_id, prepared.conversation_id, prepared.text

    def run() -> None:
        try:
            from app.ai.session_title import suggest_title

            with SessionLocal() as session:
                conv = repo.get_conversation(session, user_id, conversation_id)
                if conv is None or conv.title is not None or conv.title_source == "user":
                    return
            title = suggest_title(user_id, question, answer)
            if not title:
                return
            with SessionLocal() as session:
                if set_auto_title(session, user_id, conversation_id, title):
                    session.commit()
        except Exception:
            log.exception("Đặt tên phiên lỗi")

    if AUTO_TITLE_BACKGROUND:
        threading.Thread(target=run, name=f"chat-title-{conversation_id}", daemon=True).start()
    else:
        run()


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
    delivered = threading.Event()

    def worker() -> None:
        answer_id = None
        try:
            for item in iter_turn_events(prepared):
                if item[0] == "message.completed":
                    answer_id = (item[1].get("assistant_message") or {}).get("id")
                events.put(item)
        finally:
            _release(prepared.user.user_id)
            events.put(done)
        # Starlette không chắc đóng iterator đồng bộ khi app ngắt; dò bằng việc SSE có đọc qua sự kiện cuối không.
        if answer_id and not delivered.wait(DELIVERY_GRACE_SECONDS):
            mark_notify_done(prepared.user.user_id, answer_id)

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
            delivered.set()  # tới được đây nghĩa là chunk message.completed đã gửi xong
            return
        name, data = item
        yield _sse(name, data)


def mark_notify_done(user_id: int, message_id: int) -> None:
    """App ngắt trước khi nhận hết lượt: bật cờ để notice `chat_done` báo trợ lý đã trả lời (QĐ-41)."""
    try:
        with SessionLocal() as session:
            message = repo.get_message(session, user_id, message_id)
            if message is not None:
                message.notify_done = True
                session.commit()
    except Exception:
        log.exception("Không đánh dấu được notify_done")


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
    """Giữ cho bản app cũ (trước QĐ-51): trả phiên hoạt động gần nhất, chưa có thì tạo."""
    now = clock.now()
    conversation = repo.get_or_create_conversation(
        session, user.user_id, clock.chat_day(now, user.timezone), now
    )
    return get_conversation_page(session, user, conversation)


def get_conversation_page(session: Session, user: UserContext, conversation) -> dict:
    rows = repo.list_visible(session, user.user_id, conversation.id, None, 51)
    has_more = len(rows) > 50
    rows = list(reversed(rows[:50]))
    pending = repo.list_pending_actions(session, user.user_id, ["pending"])
    return {
        "conversation": serialize_conversation(
            conversation, _previews(session, user.user_id, [conversation.id]).get(conversation.id)
        ),
        "messages": enrich_messages(session, user.user_id, [serialize_message(m) for m in rows]),
        "next_cursor": str(rows[0].id) if has_more and rows else None,
        "pending_actions": [serialize_pending(a) for a in pending],
    }


def serialize_conversation(c, preview: str | None = None) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "title_source": c.title_source,
        "pinned": c.pinned,
        "started_at": c.started_at,
        "last_message_at": c.last_message_at or c.started_at,
        "message_count": c.message_count,
        "last_preview": preview,
        "created_at": c.created_at,
        "local_date": c.local_date,  # bản app cũ
        "summary": c.summary,
    }


PREVIEW_MAX = 120


def _previews(session: Session, user_id: int, ids: list[int]) -> dict[int, str]:
    """Đoạn đầu tin hiện cuối cùng (người dùng hoặc trợ lý) của mỗi phiên, một câu SQL."""
    if not ids:
        return {}
    from sqlalchemy import text as sql

    rows = session.execute(
        sql(
            "SELECT DISTINCT ON (conversation_id) conversation_id, text FROM tab_message "
            "WHERE user_id = :u AND conversation_id = ANY(:ids) AND hidden = false "
            "AND role IN ('user','assistant') AND coalesce(text, '') <> '' "
            "ORDER BY conversation_id, id DESC"
        ),
        {"u": user_id, "ids": ids},
    ).all()
    out = {}
    for r in rows:
        flat = " ".join(r.text.split())
        out[r.conversation_id] = flat if len(flat) <= PREVIEW_MAX else flat[: PREVIEW_MAX - 1] + "…"
    return out


def _parse_cursor(cursor: str) -> tuple[bool, datetime, int]:
    """Con trỏ `<0|1>|<giờ ISO>|<id>`."""
    from app.core.errors import ValidationError

    try:
        pin, at, cid = cursor.split("|")
        return pin == "1", datetime.fromisoformat(at), int(cid)
    except ValueError as exc:
        raise ValidationError(fields={"cursor": "Con trỏ trang không hợp lệ."}) from exc


def list_conversations(
    session: Session, user: UserContext, cursor: str | None, limit: int, q: str | None = None
) -> dict:
    """Danh sách phiên: ghim trước, rồi tin mới nhất giảm dần; `q` tìm theo tiêu đề và nội dung tin."""
    after = _parse_cursor(cursor) if cursor else None
    q = (q or "").strip() or None
    rows = repo.list_conversations(session, user.user_id, after, limit + 1, q)
    items = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = items[-1]
        at = (last.last_message_at or last.started_at).isoformat()
        next_cursor = f"{int(last.pinned)}|{at}|{last.id}"
    previews = _previews(session, user.user_id, [c.id for c in items])
    return {
        "items": [serialize_conversation(c, previews.get(c.id)) for c in items],
        "next_cursor": next_cursor,
    }


def get_conversation_detail(session: Session, user: UserContext, conversation_id: int) -> dict:
    """Mở một phiên cũ để chat tiếp: cùng dạng /chat/today."""
    conv = repo.get_conversation(session, user.user_id, conversation_id)
    if conv is None:
        raise NotFoundError("Không tìm thấy phiên chat.")
    return get_conversation_page(session, user, conv)


SNIPPET_MAX = 220


def search_history(
    session: Session,
    user: UserContext,
    query: str,
    limit: int = 10,
    exclude_conversation_id: int | None = None,
) -> list[dict]:
    """Tìm trong tin chat cũ (công cụ search_chat_history của agent AI): tin hiện của người dùng và trợ lý,
    mới trước, kèm tên phiên và đoạn quanh chữ khớp."""
    from sqlalchemy import text as sql

    query = (query or "").strip()
    if not query:
        return []
    rows = session.execute(
        sql(
            "SELECT m.id AS message_id, m.conversation_id, c.title AS conversation_title, c.started_at, "
            "c.local_date, m.role, m.created_at, ts_headline('troly_vn', m.text, q, "
            '\'StartSel="", StopSel="", MaxWords=35, MinWords=12, MaxFragments=1\') AS snippet '
            "FROM tab_message m JOIN tab_conversation c ON c.id = m.conversation_id, "
            "websearch_to_tsquery('troly_vn', :q) q "
            "WHERE m.user_id = :u AND m.hidden = false AND m.role IN ('user','assistant') "
            "AND m.search_vector @@ q AND (CAST(:ex AS bigint) IS NULL OR m.conversation_id <> :ex) "
            "ORDER BY m.created_at DESC, m.id DESC LIMIT :l"
        ),
        {"u": user.user_id, "q": query, "ex": exclude_conversation_id, "l": max(1, min(limit, 50))},
    ).all()
    return [
        {
            "conversation_id": r.conversation_id,
            "conversation_title": r.conversation_title,
            "started_at": r.started_at,
            "local_date": r.local_date,
            "message_id": r.message_id,
            "role": r.role,
            "snippet": " ".join((r.snippet or "").split())[:SNIPPET_MAX],
            "created_at": r.created_at,
        }
        for r in rows
    ]


def create_conversation(session: Session, user: UserContext, title: str | None = None) -> dict:
    """Phiên mới (nút *Phiên mới*). Phiên gần nhất còn trống, chưa đặt tên thì dùng lại, khỏi đẻ phiên rỗng."""
    now = clock.now()
    title = _clean_title(title)
    latest = repo.latest_conversation(session, user.user_id)
    if latest is not None and latest.message_count == 0 and latest.title is None:
        if title:
            latest.title, latest.title_source = title, "user"
        latest.last_message_at = now
        session.flush()
        return serialize_conversation(latest)
    conv = repo.create_conversation(session, user.user_id, clock.chat_day(now, user.timezone), now, title)
    return serialize_conversation(conv)


def update_conversation(session: Session, user: UserContext, conversation_id: int, changes: dict) -> dict:
    """Đổi tên (thành tên người đặt, máy không ghi đè nữa) hoặc ghim."""
    from app.core.errors import ValidationError

    conv = repo.get_conversation(session, user.user_id, conversation_id, lock=True)
    if conv is None:
        raise NotFoundError("Không tìm thấy phiên chat.")
    if "title" in changes:
        title = _clean_title(changes["title"])
        if title is None:
            raise ValidationError(fields={"title": "Nhập tên phiên."})
        conv.title, conv.title_source = title, "user"
    if changes.get("pinned") is not None:
        conv.pinned = bool(changes["pinned"])
    session.flush()
    return serialize_conversation(conv)


def set_auto_title(session: Session, user_id: int, conversation_id: int, title: str) -> bool:
    """Cho agent AI đặt tên phiên tự động. Không ghi đè tên người dùng đặt. Trả True nếu đã đặt."""
    conv = repo.get_conversation(session, user_id, conversation_id, lock=True)
    title = _clean_title(title)
    if conv is None or title is None or conv.title_source == "user":
        return False
    conv.title = title
    session.flush()
    return True


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
        "items": enrich_messages(session, user.user_id, [serialize_message(m) for m in items]),
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
    if action.status == "pending" and action.expires_at <= now:
        action.status, action.decided_at = "expired", now
    if action.status == "failed" and not approve:
        action.status, action.decided_at = "rejected", now  # thẻ lỗi vẫn cho Bỏ để không kẹt
        _system_note(session, action, f"Người dùng đã bỏ: {action.title}.")
        return {"action": serialize_pending(action), "result_text": "Đã bỏ."}
    if action.status != "pending":
        # Bấm lại thẻ đã quyết (mạng chập, mở lại lịch sử): trả trạng thái hiện tại, không báo lỗi.
        return {"action": serialize_pending(action), "result_text": _status_text(action)}
    if action.payload_hash != payload_hash(action.tool_name, action.input):
        raise ActionPayloadChanged()
    action.decided_at = now
    if not approve:
        action.status = "rejected"
        _system_note(session, action, f"Người dùng đã bỏ: {action.title}.")
        return {"action": serialize_pending(action), "result_text": "Đã bỏ."}

    # Module tự chạy việc đã duyệt khi có `approvals.py` (cùng dữ liệu cho thẻ từ API và từ chat).
    from app.registry import approval_executor

    executor = approval_executor(action.tool_name)
    spec = None if executor else get_tool(action.tool_name)
    if executor is None and (spec is None or spec.execute is None):
        raise ConflictError("Công cụ này không còn, không chạy được.")
    ctx = ToolContext(session=session, user=user, conversation_id=action.conversation_id, now=now)
    try:
        with session.begin_nested():
            if executor is not None:
                result = executor(session, user, action.input)
            else:
                result = spec.execute(ctx, action.input).result
        action.status = "done"
        result = result if isinstance(result, dict) else {"result": result}
        action.result = json.loads(json.dumps(result, default=str, ensure_ascii=False))
        result_text = "thành công"
    except NotFoundError as exc:
        if not action.tool_name.startswith("delete_"):
            action.status, action.error = "failed", exc.message
            result_text = f"thất bại ({exc.message})"
        else:  # mục đích là xóa, đối tượng đã không còn: coi là xong
            action.status = "done"
            action.result = {"ghi_chu": GONE_TEXT}
            result_text = GONE_TEXT
    except AppError as exc:
        action.status = "failed"
        action.error = exc.message
        result_text = f"thất bại ({exc.message})"
    _system_note(session, action, f"Người dùng đã duyệt: {action.title}. Kết quả: {result_text}.")
    return {"action": serialize_pending(action), "result_text": _status_text(action)}


GONE_TEXT = "Đã không còn, không cần xóa."
_STATUS_TEXT = {"rejected": "Đã bỏ.", "expired": "Thẻ đã hết hạn.", "pending": "Đang chờ duyệt."}


def _status_text(action: PendingAction) -> str:
    if action.status == "failed":
        return action.error or "Không làm được."
    if action.status == "done":
        return (action.result or {}).get("ghi_chu") or "Đã làm xong."
    return _STATUS_TEXT.get(action.status, "")


def with_file_meta(session: Session, user_id: int, messages: list[dict]) -> list[dict]:
    """Tệp người dùng đính kèm: thêm mime, name, size_bytes để app vẽ thẻ tệp không phải hỏi thêm."""
    ids = [a["file_id"] for m in messages for a in m.get("attachments") or [] if "name" not in a]
    if not ids:
        return messages
    meta = file_service.describe_files(session, user_id, ids)
    for m in messages:
        m["attachments"] = [
            {**a, **meta.get(a["file_id"], {})} if "name" not in a else a for a in m.get("attachments") or []
        ]
    return messages


def enrich_messages(session: Session, user_id: int, messages: list[dict]) -> list[dict]:
    return with_action_state(session, user_id, with_file_meta(session, user_id, messages))


def with_action_state(session: Session, user_id: int, messages: list[dict]) -> list[dict]:
    """Gắn trạng thái thật hiện tại vào thẻ duyệt trong tin (lịch sử), để app mở lại không hiện nút cho thẻ đã quyết."""
    ids = {
        a.get("pending_action_id")
        for m in messages
        for a in m.get("actions") or []
        if a.get("type") == "confirm" and a.get("pending_action_id")
    }
    if not ids:
        return messages
    rows = {
        a.id: a
        for a in session.scalars(
            select(PendingAction).where(PendingAction.user_id == user_id, PendingAction.id.in_(ids))
        )
    }
    now = clock.now()
    for m in messages:
        actions = []
        for a in m.get("actions") or []:
            row = rows.get(a.get("pending_action_id")) if a.get("type") == "confirm" else None
            if row is not None:
                status = "expired" if row.status == "pending" and row.expires_at <= now else row.status
                text = _STATUS_TEXT["expired"] if status == "expired" else _status_text(row)
                a = {
                    **a,
                    "status": status,
                    "error": row.error,
                    "result_text": text,
                    "decided_at": row.decided_at,
                }
            actions.append(a)
        m["actions"] = actions
    return messages


def expire_actions(session: Session) -> int:
    return repo.expire_pending_actions(session, clock.now())
