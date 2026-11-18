"""Công cụ AI của module expense (20 mục 3.7, 3.10).

Xóa một khoản làm ngay, trả nút Hoàn tác; xóa từ 2 khoản tạo thẻ duyệt (QĐ-27, 60 mục 3.7).
"""

from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.ai import actions as act
from app.ai.schemas import AiError, ApprovalDraft, ToolContext, ToolOutput, ToolSpec
from app.core import clock
from app.modules.expense import service

Kind = Literal["expense", "income", "transfer"]
Account = Literal["vcb", "tcb", "momo", "cash", "card", "other"]
UNDO_MINUTES = 10
MAX_DELETE = 50


def money(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + "đ"


def _category_id(ctx: ToolContext, name: str | None) -> int | None:
    if not name:
        return None
    wanted = service.fold(name).strip()
    for c in service.list_categories(ctx.session, ctx.user.user_id):
        if service.fold(c["name"]) == wanted:
            return c["id"]
    return None  # tên lạ: để service tự đoán theo từ khóa


def _brief(e: dict, tz: str) -> dict:
    return {
        "expense_id": e["id"],
        "amount_vnd": e["amount_vnd"],
        "kind": e["kind"],
        # Model chép nguyên trường vào câu trả lời và tệp xuất, nên `account` là tên hiện; mã chỉ để lọc.
        "account": e.get("account_label") or e["account"],
        "account_code": e["account"],
        "to_account": e.get("to_account_label") or e.get("to_account"),
        "to_account_code": e.get("to_account"),
        "category": (e.get("category") or {}).get("name"),
        "merchant": e.get("merchant"),
        "note": e.get("note"),
        "spent_at": clock.to_local(e["spent_at"], tz).strftime("%H:%M %d/%m/%Y"),
    }


def _label(e: dict, tz: str) -> str:
    what = e.get("note") or e.get("merchant") or (e.get("category") or {}).get("name") or "khoản chi"
    return f"{money(e['amount_vnd'])} {what} {clock.to_local(e['spent_at'], tz):%d/%m}"


def _today_total(ctx: ToolContext) -> int:
    s = service.summarize(ctx.session, ctx.user, "day", None, None, None, None)
    return s["total_expense_vnd"]


# ---------- Đầu vào ----------


class AddExpenseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount_vnd: int = Field(
        description=(
            "Số tiền VND, số nguyên dương. Cách đọc: 45k = 45000; 45 nghìn = 45000; 1tr2 = 1200000; "
            "1,5 triệu = 1500000; 200 cành = 200000; số không đơn vị nhỏ hơn 1000 hiểu là nghìn đồng "
            "(cà phê 35 = 35000); 2 lít xăng không phải số tiền."
        )
    )
    kind: Kind = Field(description="expense: chi; income: thu; transfer: chuyển giữa tài khoản của mình")
    account: Account | None = Field(
        description="Tài khoản tiền đi ra (hoặc vào với income); null là tiền mặt"
    )
    to_account: Account | None = Field(description="Tài khoản nhận, chỉ dùng với transfer")
    category: str | None = Field(description="Tên danh mục nếu người dùng nói rõ; null để tự đoán")
    merchant: str | None = Field(description="Nơi bán, người nhận")
    place: str | None = Field(description="Địa điểm")
    note: str | None = Field(description="Khoản gì, ví dụ: cơm trưa")
    spent_at: datetime | None = Field(description="Thời điểm chi, ISO 8601 có múi giờ; null là bây giờ")


class UpdateExpenseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expense_id: int
    amount_vnd: int | None = Field(description="Số tiền mới; null là giữ nguyên")
    kind: Kind | None
    account: Account | None
    to_account: Account | None
    category: str | None = Field(description="Tên danh mục mới; null là giữ nguyên")
    merchant: str | None
    place: str | None
    note: str | None
    spent_at: datetime | None


class DeleteExpenseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expense_ids: list[int] = Field(description="Mã khoản cần xóa, 1 tới 50")
    reason: str = Field(description="Vì sao xóa, một câu ngắn")


class QueryExpensesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_date: date | None = Field(
        description="Ngày bắt đầu (tính cả ngày này); null cùng to_date là tháng này"
    )
    to_date: date | None = Field(description="Ngày kết thúc (tính cả ngày này)")
    kind: Kind | None = Field(description="Chỉ lấy một loại; null là mọi loại")
    account: Account | None
    category: str | None = Field(description="Tên danh mục")
    text_contains: str | None = Field(description="Chữ có trong ghi chú, nơi bán, địa điểm")
    needs_review: bool | None = Field(description="true: chỉ khoản cần xem lại")
    group_by: Literal["none", "day", "category", "account"] = Field(description="Gom tổng chi theo")
    limit: int | None = Field(
        description="Số dòng chi tiết tối đa, mặc định 20, tối đa 50; 0 là không cần dòng"
    )


class NoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- Hàm chạy ----------


def run_add_expense(ctx: ToolContext, data: AddExpenseInput) -> ToolOutput:
    if data.kind == "transfer" and not data.to_account:
        raise AiError("VALIDATION_ERROR", "Chuyển tiền cần tài khoản nhận (to_account).")
    payload = data.model_dump(exclude={"category"})
    payload["category_id"] = _category_id(ctx, data.category)
    e = service.create_expense(ctx.session, ctx.user, payload, source="chat")
    tz = ctx.user.timezone
    return ToolOutput(
        result={**_brief(e, tz), "today_total_vnd": _today_total(ctx), "needs_review": e["needs_review"]},
        actions=[act.open_screen("Sửa khoản này", "expense_detail", {"expense_id": e["id"]})],
    )


def run_update_expense(ctx: ToolContext, data: UpdateExpenseInput) -> ToolOutput:
    changes = {k: v for k, v in data.model_dump(exclude={"expense_id", "category"}).items() if v is not None}
    if data.category:
        cid = _category_id(ctx, data.category)
        if cid is None:
            raise AiError(
                "VALIDATION_ERROR", f"Không có danh mục {data.category}; gọi list_expense_categories."
            )
        changes["category_id"] = cid
    if not changes:
        raise AiError("VALIDATION_ERROR", "Không có gì để sửa.")
    e = service.update_expense(ctx.session, ctx.user, data.expense_id, changes)
    return ToolOutput(
        result=_brief(e, ctx.user.timezone),
        actions=[act.open_screen("Xem khoản này", "expense_detail", {"expense_id": e["id"]})],
    )


def _check_ids(data: DeleteExpenseInput) -> list[int]:
    ids = list(dict.fromkeys(data.expense_ids))
    if not 1 <= len(ids) <= MAX_DELETE:
        raise AiError("VALIDATION_ERROR", f"Xóa từ 1 tới {MAX_DELETE} khoản mỗi lần.")
    return ids


def run_delete_one(ctx: ToolContext, data: DeleteExpenseInput) -> ToolOutput:
    ids = _check_ids(data)
    e = service.get_expense(ctx.session, ctx.user, ids[0])
    service.delete_expenses(ctx.session, ctx.user, ids)
    text = f"Đã xóa {_label(e, ctx.user.timezone)}"
    return ToolOutput(
        result={"da_xoa": ids, "ghi_chu": "Người dùng có nút Hoàn tác trong 10 phút."},
        actions=[act.undo(text, "expense", ids, ctx.now + timedelta(minutes=UNDO_MINUTES))],
    )


def prepare_delete(ctx: ToolContext, data: DeleteExpenseInput) -> ApprovalDraft:
    ids = _check_ids(data)
    tz = ctx.user.timezone
    rows = [service.get_expense(ctx.session, ctx.user, i) for i in ids]
    total = sum(e["amount_vnd"] for e in rows)
    details = [{"label": f"Khoản {i + 1}", "value": _label(e, tz)} for i, e in enumerate(rows[:5])]
    if len(rows) > 5:
        details.append({"label": "Còn", "value": f"{len(rows) - 5} khoản nữa"})
    return ApprovalDraft(
        title=f"Xóa {len(rows)} khoản chi",
        summary=f"Tổng {money(total)}. Lý do: {data.reason}",
        input={"expense_ids": ids},
        details=details,
        danger=True,
    )


def execute_delete(ctx: ToolContext, tool_input: dict) -> ToolOutput:
    ids = service.delete_expenses(ctx.session, ctx.user, list(tool_input["expense_ids"]))
    return ToolOutput(result={"da_xoa": ids})


def run_query_expenses(ctx: ToolContext, data: QueryExpensesInput) -> ToolOutput:
    tz = ctx.user.timezone
    if data.from_date is None and data.to_date is None:
        today = clock.to_local(ctx.now, tz).date()
        start_day, end_day = today.replace(day=1), today
    else:
        start_day = data.from_date or data.to_date
        end_day = data.to_date or clock.to_local(ctx.now, tz).date()
    if end_day < start_day:
        raise AiError("VALIDATION_ERROR", "Ngày kết thúc trước ngày bắt đầu.")
    start = clock.local_day_start(start_day, tz)
    end = clock.local_day_start(end_day + timedelta(days=1), tz)
    group_by = None if data.group_by == "none" else data.group_by
    summary = service.summarize(ctx.session, ctx.user, "custom", None, start, end, group_by)

    result: dict = {
        "from_date": start_day.isoformat(),
        "to_date": end_day.isoformat(),
        "total_expense_vnd": summary["total_expense_vnd"],
        "total_income_vnd": summary["total_income_vnd"],
        "total_transfer_vnd": summary["total_transfer_vnd"],
        "ghi_chu": "Chuyển tiền nội bộ (transfer) không tính vào chi.",
    }
    if summary["groups"]:
        result["groups"] = [
            {"label": g["label"], "total_vnd": g["total_vnd"], "count": g["count"]} for g in summary["groups"]
        ]

    limit = 20 if data.limit is None else min(max(data.limit, 0), 50)
    filters: dict = {"from": start, "to": end}
    if data.kind:
        filters["kind"] = [data.kind]
    if data.account:
        filters["account"] = [data.account]
    if data.category:
        cid = _category_id(ctx, data.category)
        if cid is None:
            raise AiError(
                "VALIDATION_ERROR", f"Không có danh mục {data.category}; gọi list_expense_categories."
            )
        filters["category_id"] = cid
    if data.text_contains:
        filters["q"] = data.text_contains
    if data.needs_review is not None:
        filters["needs_review"] = data.needs_review
    narrowed = any(k in filters for k in ("kind", "account", "category_id", "q", "needs_review"))
    page_limit = 50 if narrowed else limit
    if page_limit:
        page = service.list_expenses(ctx.session, ctx.user, filters, None, page_limit)
        items = [_brief(e, tz) for e in page["items"]]
        more = page["next_cursor"] is not None
        if narrowed:
            # Tổng của các khoản khớp bộ lọc (tối đa 50 khoản đầu); con_nua báo còn khoản chưa cộng.
            result["matched_total_vnd"] = sum(i["amount_vnd"] for i in items)
            result["matched_count"] = len(items)
        if limit:
            result["items"] = items[:limit]
        result["con_nua"] = more or len(items) > limit
    return ToolOutput(
        result=result,
        actions=[
            act.open_screen(
                "Xem chi tiêu", "expense_list", {"from": start_day.isoformat(), "to": end_day.isoformat()}
            )
        ],
    )


def run_list_categories(ctx: ToolContext, data: NoInput) -> ToolOutput:
    cats = service.list_categories(ctx.session, ctx.user.user_id)
    return ToolOutput(
        result=[{"name": c["name"], "kind": c["kind"], "keywords": c["keywords"]} for c in cats]
    )


TOOLS = [
    ToolSpec(
        name="add_expense",
        label="Đang ghi khoản chi",
        description=(
            "Ghi một khoản chi, thu hoặc chuyển tiền giữa tài khoản của chính người dùng. "
            'Gọi ngay khi người dùng kể một khoản như "cơm trưa 45k", không hỏi lại; '
            "chỉ hỏi khi thiếu số tiền. Câu có nhiều khoản thì gọi mỗi khoản một lần. "
            "Chuyển 500k từ VCB sang MoMo là kind transfer, account vcb, to_account momo."
        ),
        input_model=AddExpenseInput,
        run=run_add_expense,
    ),
    ToolSpec(
        name="update_expense",
        label="Đang sửa khoản chi",
        description="Sửa khoản đã ghi (số tiền, danh mục, giờ, ghi chú). Lấy expense_id từ query_expenses.",
        input_model=UpdateExpenseInput,
        run=run_update_expense,
    ),
    ToolSpec(
        name="delete_expense",
        label="Đang xóa khoản chi",
        description=(
            "Xóa khoản đã ghi. Một khoản: xóa ngay, người dùng có nút Hoàn tác. Từ 2 khoản: chỉ tạo thẻ xác "
            "nhận, chưa xóa cho tới khi người dùng bấm Duyệt. Lấy expense_id từ query_expenses."
        ),
        input_model=DeleteExpenseInput,
        run=run_delete_one,
        needs_approval=lambda data: len(set(data.expense_ids)) >= 2,
        prepare=prepare_delete,
        execute=execute_delete,
    ),
    ToolSpec(
        name="query_expenses",
        label="Đang xem chi tiêu",
        description=(
            "Tính tổng, liệt kê, so sánh chi tiêu theo khoảng ngày (giờ Việt Nam). "
            "Hỏi so sánh hai kỳ thì gọi hai lần. Dùng để tìm expense_id trước khi sửa hoặc xóa."
        ),
        input_model=QueryExpensesInput,
        run=run_query_expenses,
    ),
    ToolSpec(
        name="list_expense_categories",
        label="Đang xem danh mục",
        description="Danh mục chi tiêu đang có. Gọi khi cần đúng tên danh mục để ghi, sửa hoặc lọc.",
        input_model=NoInput,
        run=run_list_categories,
    ),
]
