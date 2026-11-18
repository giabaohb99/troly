"""Công cụ AI của lịch: add_event, update_event, list_events, delete_event, set_reminder (20 mục 3.7, việc 3-02).

Sự kiện có khách mời: service tự tạo thẻ duyệt và trả `{pending_action}` (QĐ-23); công cụ đổi thẻ đó thành
hành động `confirm`. Xóa từ 2 sự kiện qua thẻ duyệt (QĐ-27), input `{events: [{event_id, occurrence_start}]}`.
Sự kiện lặp chỉ sửa, xóa từng lần trong app; sửa cả chuỗi thì trả nút mở Google Calendar.
"""

from datetime import date, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import AiError, ApprovalDraft, ToolContext, ToolOutput, ToolSpec
from app.core import clock
from app.modules.calendar import service

UNDO_MINUTES = 10
MAX_DELETE = 50
MAX_DAYS = 92
_FOLD = str.maketrans("đĐ", "dD")


def _fold(text: str | None) -> str:
    import unicodedata

    text = unicodedata.normalize("NFD", (text or "").translate(_FOLD))
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def _when(e: dict, tz: str) -> str:
    if e.get("all_day"):
        return f"cả ngày {e['start_date']:%d/%m/%Y}"
    start = clock.to_local(e["start_at"], tz)
    end = clock.to_local(e["end_at"], tz) if e.get("end_at") else None
    return f"{start:%H:%M %d/%m/%Y}" + (f" tới {end:%H:%M}" if end else "")


def _brief(e: dict, tz: str) -> dict:
    return {
        "event_id": e["id"],
        "occurrence_start": e["occurrence_start"].isoformat() if e.get("occurrence_start") else None,
        "title": e["title"],
        "when": _when(e, tz),
        "location": e.get("location"),
        "is_recurring": e.get("is_recurring", False),
        "guests": len(e.get("attendees") or []),
        "remind_minutes": e.get("remind_minutes"),
    }


def _confirm(pending: dict) -> ToolOutput:
    expires = pending["expires_at"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    return ToolOutput(
        result={
            "trang_thai": "cho_duyet",
            "pending_action_id": pending["id"],
            "ghi_chu": "Có khách mời: đã tạo thẻ xác nhận, Google chỉ gửi thư mời khi người dùng bấm Duyệt.",
        },
        actions=[
            act.confirm(
                pending_action_id=pending["id"],
                title=pending["title"],
                summary=pending["summary"],
                details=pending.get("details") or [],
                danger=bool(pending.get("danger")),
                expires_at=expires,
            )
        ],
    )


def _series_edit(exc) -> ToolOutput:
    link = (getattr(exc, "data", None) or {}).get("google_html_link")
    actions = (
        [act.open_link("Mở trên Google Calendar", link, "web")] if link and link.startswith("https") else []
    )
    return ToolOutput(
        result={
            "loi": "RECURRING_SERIES_EDIT",
            "thong_bao": "Sự kiện lặp: trong app chỉ sửa hoặc xóa từng lần (cần occurrence_start); "
            "sửa cả chuỗi trên Google Calendar.",
        },
        actions=actions,
    )


def _conflicts(ctx: ToolContext, e: dict) -> list[dict]:
    if e.get("all_day") or not e.get("start_at"):
        return []
    others = service.list_events(ctx.session, ctx.user, e["start_at"], e["end_at"] or e["start_at"])
    return [_brief(o, ctx.user.timezone) for o in others if o["id"] != e["id"] and not o.get("all_day")][:5]


# ---------- Đầu vào ----------


class AddEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    start_at: datetime | None = Field(description="Giờ bắt đầu, ISO 8601 có múi giờ; null nếu cả ngày")
    end_at: datetime | None = Field(description="Giờ kết thúc; null là bắt đầu cộng 1 giờ")
    all_day: bool | None = Field(description="true: sự kiện cả ngày, dùng start_date")
    start_date: date | None = Field(description="Ngày (sự kiện cả ngày)")
    end_date: date | None = Field(description="Ngày kết thúc không tính (cả ngày); null là 1 ngày")
    location: str | None
    description: str | None
    remind_minutes: list[int] | None = Field(description="Nhắc trước bao nhiêu phút; null là theo cài đặt")
    attendee_emails: list[str] | None = Field(
        description="Email khách mời; có khách thì cần người dùng duyệt"
    )


class UpdateEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: int
    occurrence_start: datetime | None = Field(
        description="Bắt buộc với sự kiện lặp: lần cần sửa (từ list_events)"
    )
    title: str | None
    start_at: datetime | None
    end_at: datetime | None
    location: str | None
    description: str | None
    remind_minutes: list[int] | None
    attendee_emails: list[str] | None = Field(
        description="Danh sách khách mới (thay cả danh sách); null là giữ"
    )


class ListEventsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_date: date | None = Field(description="Từ ngày; null là hôm nay")
    to_date: date | None = Field(
        description="Tới ngày (tính cả ngày này); null là bằng from_date; tối đa 92 ngày"
    )
    query: str | None = Field(description="Chữ có trong tên hoặc địa điểm; gõ không dấu vẫn ra")


class EventRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: int
    occurrence_start: datetime | None = Field(description="Bắt buộc với sự kiện lặp")


class DeleteEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[EventRef] = Field(description="Sự kiện cần xóa, 1 tới 50")
    reason: str = Field(description="Vì sao xóa, một câu ngắn")


class ReminderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(description="Nhắc việc gì")
    remind_at: datetime = Field(description="Lúc nhắc, ISO 8601 có múi giờ")


# ---------- Hàm chạy ----------


def run_add_event(ctx: ToolContext, data: AddEventInput) -> ToolOutput:
    payload = data.model_dump(exclude_none=True, exclude={"attendee_emails"})
    if data.attendee_emails:
        payload["attendees"] = [{"email": e} for e in data.attendee_emails]
    out = service.create_event(ctx.session, ctx.user, payload, conversation_id=ctx.conversation_id)
    if "pending_action" in out:
        return _confirm(out["pending_action"])
    e = out["event"] if "event" in out else out
    return ToolOutput(
        result={**_brief(e, ctx.user.timezone), "trung_lich": _conflicts(ctx, e)},
        actions=[act.open_screen("Xem sự kiện", "event_detail", {"event_id": e["id"]})],
    )


def run_update_event(ctx: ToolContext, data: UpdateEventInput) -> ToolOutput:
    changes = data.model_dump(exclude_none=True, exclude={"event_id", "occurrence_start", "attendee_emails"})
    if data.attendee_emails is not None:
        changes["attendees"] = [{"email": e} for e in data.attendee_emails]
    if not changes:
        raise AiError("VALIDATION_ERROR", "Không có gì để sửa.")
    try:
        out = service.update_event(
            ctx.session,
            ctx.user,
            data.event_id,
            changes,
            occurrence_start=data.occurrence_start,
            conversation_id=ctx.conversation_id,
        )
    except service.RecurringSeriesEdit as exc:
        return _series_edit(exc)
    if isinstance(out, dict) and "pending_action" in out:
        return _confirm(out["pending_action"])
    e = out.get("event", out)
    return ToolOutput(
        result={**_brief(e, ctx.user.timezone), "trung_lich": _conflicts(ctx, e)},
        actions=[act.open_screen("Xem sự kiện", "event_detail", {"event_id": e["id"]})],
    )


def run_list_events(ctx: ToolContext, data: ListEventsInput) -> ToolOutput:
    tz = ctx.user.timezone
    first = data.from_date or clock.to_local(ctx.now, tz).date()
    last = data.to_date or first
    if last < first:
        raise AiError("VALIDATION_ERROR", "Ngày kết thúc trước ngày bắt đầu.")
    if (last - first).days >= MAX_DAYS:
        raise AiError("VALIDATION_ERROR", f"Tối đa {MAX_DAYS} ngày mỗi lần.")
    start = clock.local_day_start(first, tz)
    end = clock.local_day_start(last + timedelta(days=1), tz)
    items = service.list_events(ctx.session, ctx.user, start, end)
    if data.query:
        needle = _fold(data.query)
        items = [e for e in items if needle in _fold(e["title"]) or needle in _fold(e.get("location"))]
    return ToolOutput(
        result={
            "from": first.isoformat(),
            "to": last.isoformat(),
            "items": [_brief(e, tz) for e in items[:50]],
        },
        actions=[act.open_screen("Mở lịch", "calendar_day", {"date": first.isoformat()})],
    )


def _refs(data: DeleteEventInput) -> list[dict]:
    refs = [
        {
            "event_id": r.event_id,
            "occurrence_start": r.occurrence_start.isoformat() if r.occurrence_start else None,
        }
        for r in data.events
    ]
    refs = list({(r["event_id"], r["occurrence_start"]): r for r in refs}.values())
    if not 1 <= len(refs) <= MAX_DELETE:
        raise AiError("VALIDATION_ERROR", f"Xóa từ 1 tới {MAX_DELETE} sự kiện mỗi lần.")
    return refs


def run_delete_one(ctx: ToolContext, data: DeleteEventInput) -> ToolOutput:
    ref = _refs(data)[0]
    occurrence = datetime.fromisoformat(ref["occurrence_start"]) if ref["occurrence_start"] else None
    e = service.get_event(ctx.session, ctx.user, ref["event_id"], occurrence)
    try:
        out = service.delete_event(
            ctx.session,
            ctx.user,
            ref["event_id"],
            occurrence_start=occurrence,
            conversation_id=ctx.conversation_id,
        )
    except service.RecurringSeriesEdit as exc:
        return _series_edit(exc)
    if isinstance(out, dict) and "pending_action" in out:
        return _confirm(out["pending_action"])
    actions = []
    if occurrence is None:  # hoàn tác chỉ cho sự kiện thường; một lần của chuỗi lặp xóa trên Google
        actions.append(
            act.undo(
                f"Đã xóa: {e['title']}", "event", [ref["event_id"]], ctx.now + timedelta(minutes=UNDO_MINUTES)
            )
        )
    return ToolOutput(result={"da_xoa": [ref], "title": e["title"]}, actions=actions)


def prepare_delete(ctx: ToolContext, data: DeleteEventInput) -> ApprovalDraft:
    refs = _refs(data)
    tz = ctx.user.timezone
    rows = []
    for r in refs:
        occurrence = datetime.fromisoformat(r["occurrence_start"]) if r["occurrence_start"] else None
        rows.append(service.get_event(ctx.session, ctx.user, r["event_id"], occurrence))
    details = [
        {"label": f"Sự kiện {i + 1}", "value": f"{e['title']} ({_when(e, tz)})"}
        for i, e in enumerate(rows[:5])
    ]
    if len(rows) > 5:
        details.append({"label": "Còn", "value": f"{len(rows) - 5} sự kiện nữa"})
    if any(e.get("attendees") for e in rows):
        details.append({"label": "Khách", "value": "Có sự kiện có khách mời; Google sẽ gửi thư hủy."})
    return ApprovalDraft(
        title=f"Xóa {len(rows)} sự kiện",
        summary=f"Lý do: {data.reason}",
        input={"events": refs},
        details=details,
        danger=True,
    )


def execute_delete(ctx: ToolContext, tool_input: dict) -> ToolOutput:
    done = []
    for r in tool_input["events"]:
        occurrence = datetime.fromisoformat(r["occurrence_start"]) if r.get("occurrence_start") else None
        service.delete_event(
            ctx.session, ctx.user, int(r["event_id"]), occurrence_start=occurrence, approved=True
        )
        done.append(r)
    return ToolOutput(result={"da_xoa": done})


def run_set_reminder(ctx: ToolContext, data: ReminderInput) -> ToolOutput:
    if data.remind_at <= ctx.now:
        raise AiError("VALIDATION_ERROR", "Giờ nhắc đã qua.")
    out = service.create_event(
        ctx.session,
        ctx.user,
        {
            "title": data.text,
            "start_at": data.remind_at,
            "end_at": data.remind_at + timedelta(minutes=15),
            "remind_minutes": [0],
            "is_alarm": True,
        },
    )
    e = out.get("event", out)
    return ToolOutput(
        result={"event_id": e["id"], "nhac_luc": _when(e, ctx.user.timezone)},
        actions=[act.open_screen("Xem nhắc", "event_detail", {"event_id": e["id"]})],
    )


TOOLS = [
    ToolSpec(
        name="add_event",
        label="Đang thêm lịch",
        description=(
            "Thêm hẹn, họp, sự kiện có giờ vào lịch (đồng bộ Google Calendar). Có khách mời thì chỉ tạo thẻ xác "
            "nhận, Google gửi thư mời khi người dùng bấm Duyệt. Kết quả có trung_lich nếu trùng giờ: báo ngắn."
        ),
        input_model=AddEventInput,
        run=run_add_event,
        phase=3,
    ),
    ToolSpec(
        name="update_event",
        label="Đang sửa lịch",
        description=(
            "Dời giờ, đổi chỗ, đổi nhắc, thêm bớt khách. Lấy event_id (và occurrence_start với sự kiện lặp) "
            "từ list_events. Sự kiện có khách thì chỉ tạo thẻ xác nhận."
        ),
        input_model=UpdateEventInput,
        run=run_update_event,
        phase=3,
    ),
    ToolSpec(
        name="list_events",
        label="Đang xem lịch",
        description="Xem lịch theo ngày, tuần, khoảng ngày (tối đa 92 ngày); tìm event_id để sửa, xóa.",
        input_model=ListEventsInput,
        run=run_list_events,
        phase=3,
    ),
    ToolSpec(
        name="delete_event",
        label="Đang xóa lịch",
        description=(
            "Xóa sự kiện. Một sự kiện không khách: xóa ngay, có nút Hoàn tác. Có khách mời hoặc từ 2 sự kiện: "
            "chỉ tạo thẻ xác nhận. Sự kiện lặp cần occurrence_start của lần cần xóa."
        ),
        input_model=DeleteEventInput,
        run=run_delete_one,
        needs_approval=lambda data: len({(r.event_id, r.occurrence_start) for r in data.events}) >= 2,
        prepare=prepare_delete,
        execute=execute_delete,
        phase=3,
    ),
    ToolSpec(
        name="set_reminder",
        label="Đang đặt nhắc",
        description="Nhắc một việc vào giờ cụ thể (máy kêu đúng giờ). Gọi khi người dùng nói nhắc lúc mấy giờ.",
        input_model=ReminderInput,
        run=run_set_reminder,
        phase=3,
    ),
]
