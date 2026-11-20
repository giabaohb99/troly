"""Công cụ AI của module report (20 mục 3.7): `get_report` trả số liệu gọn và nút mở màn Báo cáo."""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import ToolContext, ToolOutput, ToolSpec
from app.core import clock
from app.modules.calendar import service as calendar
from app.modules.expense import service as expense
from app.modules.inbox import service as inbox
from app.modules.report import service

MAX_EVENTS = 20
MAX_CONVERSATIONS = 10


class GetReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["expense_overview", "week_overview", "inbox_pending", "ai_cost"] = Field(
        description=(
            "expense_overview: chi thu theo kỳ; week_overview: lịch và việc trong tuần; "
            "inbox_pending: tin chưa xem; ai_cost: chi phí AI theo tháng."
        )
    )
    from_: date | None = Field(
        default=None,
        alias="from",
        description="Ngày đầu (giờ người dùng). Bỏ trống: tháng này, tuần này hoặc hôm nay.",
    )
    to: date | None = Field(
        default=None, description="Ngày cuối, tính cả ngày này. Chỉ dùng cho expense_overview."
    )


def _today(ctx: ToolContext) -> date:
    return clock.to_local(ctx.now, ctx.user.timezone).date()


def _expense(ctx: ToolContext, data: GetReportInput) -> dict:
    if data.from_ and data.to:
        tz = ctx.user.timezone
        lo = clock.local_day_start(data.from_, tz)
        hi = clock.local_day_start(data.to + timedelta(days=1), tz)
        s = expense.summarize(ctx.session, ctx.user, "custom", None, lo, hi, "category")
        return {
            "from": data.from_,
            "to": data.to,
            "total_expense_vnd": s["total_expense_vnd"],
            "total_income_vnd": s["total_income_vnd"],
            "top_categories": [
                {"name": g["label"], "total_vnd": g["total_vnd"]}
                for g in s["groups"][: service.TOP_CATEGORIES]
            ],
        }
    return service.expense_card(ctx.session, ctx.user, data.from_ or _today(ctx))


def _week(ctx: ToolContext, data: GetReportInput) -> dict:
    tz = ctx.user.timezone
    day = data.from_ or _today(ctx)
    lo, hi = clock.period_range("week", day, tz, service._week_start(ctx.session, ctx.user))
    events = sorted(
        (e for e in calendar.list_events(ctx.session, ctx.user, lo, hi) if e.get("status") != "cancelled"),
        key=lambda e: service._event_start(e, tz),
    )
    return {
        "from": lo.date(),
        "to": (hi - timedelta(days=1)).date(),
        "events": [
            {
                "event_id": e["id"],
                "title": e["title"],
                "all_day": e["all_day"],
                "start": clock.to_local(service._event_start(e, tz), tz).strftime("%a %d/%m %H:%M"),
            }
            for e in events[:MAX_EVENTS]
        ],
        "event_count": len(events),
        "tasks": service.tasks_card(ctx.session, ctx.user),
    }


def _inbox(ctx: ToolContext) -> dict:
    counts = service.inbox_card(ctx.session, ctx.user)
    # Danh sách hội thoại xếp theo tin mới nhất (bản 1.0.7): lấy hội thoại có tin quan trọng trước để không bị cắt,
    # rồi lấp hội thoại thường cho đủ, bỏ trùng theo khóa.
    picked: dict[str, dict] = {}
    for importance in ("important", "normal"):
        if len(picked) >= MAX_CONVERSATIONS:
            break
        page = inbox.list_conversations(
            ctx.session,
            ctx.user.user_id,
            {"status": "new", "importance": importance},
            None,
            MAX_CONVERSATIONS,
        )
        for c in page["items"]:
            if c["is_private"] or c["conversation_key"] in picked or len(picked) >= MAX_CONVERSATIONS:
                continue
            picked[c["conversation_key"]] = {
                "app": c["app"],
                "title": c["title"],
                "unread": c["unread_count"],
                "importance": importance,
            }
    return {**counts, "conversations": list(picked.values())}


def run_get_report(ctx: ToolContext, data: GetReportInput) -> ToolOutput:
    if data.kind == "ai_cost":
        month = (data.from_ or _today(ctx)).replace(day=1)
        cost = service.ai_cost(ctx.session, ctx.user, month)
        result = {
            k: cost[k] for k in ("month", "total_usd", "today_usd", "monthly_warn_usd", "cache_read_ratio")
        }
        result["by_purpose"] = cost["by_purpose"]
        result["by_model"] = cost["by_model"]
        return ToolOutput(
            result=result,
            actions=[act.open_screen("Xem chi phí AI", "settings_ai_cost", {"month": result["month"]})],
        )
    open_report = act.open_screen("Mở Báo cáo", "report")
    if data.kind == "expense_overview":
        return ToolOutput(result=_expense(ctx, data), actions=[open_report])
    if data.kind == "week_overview":
        return ToolOutput(result=_week(ctx, data), actions=[open_report])
    return ToolOutput(result=_inbox(ctx), actions=[open_report], contains_third_party=True)


TOOLS = [
    ToolSpec(
        name="get_report",
        label="Đang xem báo cáo",
        description=(
            "Xem tổng quan: chi tiêu theo kỳ, lịch và việc trong tuần, tin chưa xem, chi phí AI. "
            "Câu hỏi chi tiết từng khoản thì dùng query_expenses, list_events, list_tasks, list_inbox."
        ),
        input_model=GetReportInput,
        run=run_get_report,
        phase=4,
    ),
]
