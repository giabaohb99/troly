"""Chi tiêu (11 mục 3.9, 12 mục 5.4). Hàm công khai dùng chung cho API và công cụ AI."""

import unicodedata
from datetime import date, datetime, timedelta

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.context import UserContext
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.modules.expense.amount import parse_amount_vnd
from app.modules.expense.models import Expense, ExpenseCategory

UNDO_DAYS = 30
MAX_AMOUNT = 1_000_000_000

DEFAULT_CATEGORIES = [
    ("Ăn uống", "expense", ["com", "pho", "bun", "an", "uong", "cafe", "ca phe", "tra sua", "nhau", "banh"]),
    ("Đi lại", "expense", ["xang", "grab", "taxi", "gui xe", "ve xe", "be", "xe om", "phi duong"]),
    ("Mua sắm", "expense", ["mua", "shopee", "lazada", "tiki", "quan ao", "giay"]),
    ("Hóa đơn", "expense", ["dien", "nuoc", "internet", "wifi", "dien thoai", "nap the"]),
    ("Sức khỏe", "expense", ["thuoc", "kham", "benh vien", "gym"]),
    ("Giải trí", "expense", ["phim", "game", "du lich", "karaoke"]),
    ("Gia đình", "expense", ["me", "ba", "con", "bieu", "qua"]),
    ("Khác", "expense", []),
    ("Lương", "income", ["luong", "thuong"]),
    ("Thu khác", "income", []),
]


def fold(text: str) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def ensure_default_categories(session: Session, user_id: int) -> None:
    if session.scalar(select(ExpenseCategory.id).where(ExpenseCategory.user_id == user_id).limit(1)):
        return
    for i, (name, kind, keywords) in enumerate(DEFAULT_CATEGORIES):
        session.add(ExpenseCategory(user_id=user_id, name=name, kind=kind, keywords=keywords, sort_order=i))
    session.flush()


# ---------- Danh mục ----------


def serialize_category(c: ExpenseCategory) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "kind": c.kind,
        "keywords": c.keywords,
        "sort_order": c.sort_order,
        "is_archived": c.is_archived,
    }


def list_categories(session: Session, user_id: int, include_archived: bool = False) -> list[dict]:
    ensure_default_categories(session, user_id)
    stmt = select(ExpenseCategory).where(ExpenseCategory.user_id == user_id)
    if not include_archived:
        stmt = stmt.where(ExpenseCategory.is_archived.is_(False))
    return [
        serialize_category(c)
        for c in session.scalars(stmt.order_by(ExpenseCategory.sort_order, ExpenseCategory.id))
    ]


def _category(session: Session, user_id: int, category_id: int) -> ExpenseCategory:
    c = session.scalar(
        select(ExpenseCategory).where(ExpenseCategory.id == category_id, ExpenseCategory.user_id == user_id)
    )
    if c is None:
        raise NotFoundError("Không tìm thấy danh mục.")
    return c


def _name_taken(session: Session, user_id: int, name: str, exclude_id: int | None = None) -> bool:
    stmt = select(ExpenseCategory.id).where(
        ExpenseCategory.user_id == user_id, func.lower(ExpenseCategory.name) == name.strip().lower()
    )
    if exclude_id:
        stmt = stmt.where(ExpenseCategory.id != exclude_id)
    return session.scalar(stmt) is not None


def create_category(session: Session, user_id: int, name: str, kind: str, keywords: list[str]) -> dict:
    if _name_taken(session, user_id, name):
        raise ConflictError("Đã có danh mục này.", code="DUPLICATE")
    c = ExpenseCategory(user_id=user_id, name=name.strip(), kind=kind, keywords=[fold(k) for k in keywords])
    session.add(c)
    session.flush()
    return serialize_category(c)


def update_category(session: Session, user_id: int, category_id: int, changes: dict) -> dict:
    c = _category(session, user_id, category_id)
    if changes.get("name") is not None:
        if _name_taken(session, user_id, changes["name"], c.id):
            raise ConflictError("Đã có danh mục này.", code="DUPLICATE")
        c.name = changes["name"].strip()
    if changes.get("keywords") is not None:
        c.keywords = [fold(k) for k in changes["keywords"]]
    for key in ("sort_order", "is_archived"):
        if changes.get(key) is not None:
            setattr(c, key, changes[key])
    session.flush()
    return serialize_category(c)


def delete_category(session: Session, user_id: int, category_id: int) -> None:
    c = _category(session, user_id, category_id)
    used = session.scalar(
        select(Expense.id).where(Expense.user_id == user_id, Expense.category_id == c.id).limit(1)
    )
    if used:
        raise ConflictError("Danh mục đã có khoản chi, hãy ẩn thay vì xóa.")
    session.delete(c)


def guess_category_id(session: Session, user_id: int, text: str, kind: str = "expense") -> int | None:
    """Đoán danh mục theo từ khóa; không khớp thì về `Khác` (hoặc `Thu khác`)."""
    ensure_default_categories(session, user_id)
    words = f" {fold(text)} "
    rows = list(
        session.scalars(
            select(ExpenseCategory)
            .where(
                ExpenseCategory.user_id == user_id,
                ExpenseCategory.kind == ("income" if kind == "income" else "expense"),
                ExpenseCategory.is_archived.is_(False),
            )
            .order_by(ExpenseCategory.sort_order)
        )
    )
    for c in rows:
        if any(f" {k} " in words for k in c.keywords):
            return c.id
    fallback = "thu khac" if kind == "income" else "khac"
    for c in rows:
        if fold(c.name) == fallback:
            return c.id
    return None


# ---------- Khoản chi ----------


def serialize(e: Expense, categories: dict[int, str] | None = None) -> dict:
    category = None
    if e.category_id is not None:
        name, kind = (categories or {}).get(e.category_id, (None, None))
        category = {"id": e.category_id, "name": name, "kind": kind}
    return {
        "id": e.id,
        "amount_vnd": e.amount_vnd,
        "kind": e.kind,
        "account": e.account,
        "account_last4": e.account_last4,
        "to_account": e.to_account,
        "to_account_last4": e.to_account_last4,
        "category": category,
        "merchant": e.merchant,
        "place": e.place,
        "note": e.note,
        "spent_at": e.spent_at,
        "source": e.source,
        "parser": e.parser,
        "parse_confidence": float(e.parse_confidence) if e.parse_confidence is not None else None,
        "needs_review": e.needs_review,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


def _category_names(session: Session, user_id: int) -> dict[int, tuple[str, str]]:
    rows = session.execute(
        select(ExpenseCategory.id, ExpenseCategory.name, ExpenseCategory.kind).where(
            ExpenseCategory.user_id == user_id
        )
    ).all()
    return {cid: (name, kind) for cid, name, kind in rows}


def _get(session: Session, user_id: int, expense_id: int, include_deleted: bool = False) -> Expense:
    stmt = select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(Expense.deleted_at.is_(None))
    e = session.scalar(stmt)
    if e is None:
        raise NotFoundError("Không tìm thấy khoản chi.")
    return e


def _check(fields: dict) -> None:
    amount = fields.get("amount_vnd")
    if amount is not None and not (0 < amount < MAX_AMOUNT):
        raise ValidationError(fields={"amount_vnd": "Số tiền phải từ 1 đồng tới dưới 1 tỷ."})
    if fields.get("kind") == "transfer" and not fields.get("to_account"):
        raise ValidationError(fields={"to_account": "Chuyển tiền cần tài khoản nhận."})


def create_expense(session: Session, user: UserContext, data: dict, source: str = "manual") -> dict:
    """`data`: amount_vnd, kind, account, account_last4, to_account, to_account_last4, category_id,
    merchant, place, note, spent_at, parser, parse_confidence."""
    _check(data)
    if data.get("category_id") is not None:
        _category(session, user.user_id, data["category_id"])
    kind = data.get("kind") or "expense"
    category_id = data.get("category_id")
    if category_id is None and kind != "transfer":
        hint = " ".join(filter(None, [data.get("note"), data.get("merchant"), data.get("place")]))
        category_id = guess_category_id(session, user.user_id, hint, kind)
    spent_at = data.get("spent_at") or clock.now()
    if spent_at > clock.now() + timedelta(hours=1):
        raise ValidationError(fields={"spent_at": "Thời điểm không được ở tương lai."})
    e = Expense(
        user_id=user.user_id,
        amount_vnd=data["amount_vnd"],
        kind=kind,
        account=data.get("account") or "cash",
        account_last4=data.get("account_last4"),
        to_account=data.get("to_account"),
        to_account_last4=data.get("to_account_last4"),
        category_id=category_id,
        merchant=data.get("merchant"),
        place=data.get("place"),
        note=data.get("note"),
        spent_at=spent_at,
        source=source,
        parser=data.get("parser") or ("chat" if source == "chat" else "manual"),
        parse_confidence=data.get("parse_confidence"),
        needs_review=bool(data.get("needs_review")) or category_id is None and kind != "transfer",
    )
    session.add(e)
    session.flush()
    return serialize(e, _category_names(session, user.user_id))


def update_expense(session: Session, user: UserContext, expense_id: int, changes: dict) -> dict:
    e = _get(session, user.user_id, expense_id)
    merged = {"amount_vnd": e.amount_vnd, "kind": e.kind, "to_account": e.to_account, **changes}
    _check(merged)
    if changes.get("category_id") is not None:
        _category(session, user.user_id, changes["category_id"])
    for key, value in changes.items():
        setattr(e, key, value)
    if "category_id" in changes and "needs_review" not in changes:
        e.needs_review = False
    session.flush()
    return serialize(e, _category_names(session, user.user_id))


def get_expense(session: Session, user: UserContext, expense_id: int) -> dict:
    return serialize(_get(session, user.user_id, expense_id), _category_names(session, user.user_id))


def delete_expenses(session: Session, user: UserContext, expense_ids: list[int]) -> list[int]:
    rows = list(
        session.scalars(
            select(Expense).where(
                Expense.user_id == user.user_id, Expense.id.in_(expense_ids), Expense.deleted_at.is_(None)
            )
        )
    )
    if len(rows) != len(set(expense_ids)):
        raise NotFoundError("Không tìm thấy khoản chi.")
    now = clock.now()
    for e in rows:
        e.deleted_at = now
    return [e.id for e in rows]


def restore_expense(session: Session, user: UserContext, expense_id: int) -> dict:
    e = _get(session, user.user_id, expense_id, include_deleted=True)
    if e.deleted_at is None or e.deleted_at < clock.now() - timedelta(days=UNDO_DAYS):
        raise NotFoundError("Không còn hoàn tác được khoản này.")
    e.deleted_at = None
    return serialize(e, _category_names(session, user.user_id))


def _filtered(stmt: Select, user_id: int, f: dict) -> Select:
    stmt = stmt.where(Expense.user_id == user_id, Expense.deleted_at.is_(None))
    if f.get("from"):
        stmt = stmt.where(Expense.spent_at >= f["from"])
    if f.get("to"):
        stmt = stmt.where(Expense.spent_at < f["to"])
    for key in ("kind", "account", "source"):
        values = f.get(key)
        if values:
            stmt = stmt.where(getattr(Expense, key).in_(values))
    if f.get("category_id"):
        stmt = stmt.where(Expense.category_id == f["category_id"])
    if f.get("needs_review") is not None:
        stmt = stmt.where(Expense.needs_review.is_(f["needs_review"]))
    if f.get("q"):
        like = f"%{f['q']}%"
        stmt = stmt.where(
            func.unaccent(
                func.coalesce(Expense.note, "")
                + " "
                + func.coalesce(Expense.merchant, "")
                + " "
                + func.coalesce(Expense.place, "")
            ).ilike(func.unaccent(like))
        )
    return stmt


def list_expenses(session: Session, user: UserContext, filters: dict, cursor: str | None, limit: int) -> dict:
    if not filters.get("from") and not filters.get("to"):
        filters = {**filters, "from": clock.now() - timedelta(days=30)}
    stmt = _filtered(select(Expense), user.user_id, filters)
    if cursor:
        at_raw, _, id_raw = cursor.partition("|")
        at = datetime.fromisoformat(at_raw)
        stmt = stmt.where((Expense.spent_at < at) | ((Expense.spent_at == at) & (Expense.id < int(id_raw))))
    rows = list(session.scalars(stmt.order_by(Expense.spent_at.desc(), Expense.id.desc()).limit(limit + 1)))
    items = rows[:limit]
    names = _category_names(session, user.user_id)
    next_cursor = f"{items[-1].spent_at.isoformat()}|{items[-1].id}" if len(rows) > limit else None
    return {"items": [serialize(e, names) for e in items], "next_cursor": next_cursor}


def summarize(
    session: Session,
    user: UserContext,
    period: str,
    day: date | None,
    start: datetime | None,
    end: datetime | None,
    group_by: str | None,
    week_start: int = 1,
) -> dict:
    """Tổng chi, thu, chuyển trong kỳ theo giờ người dùng; chuyển nội bộ không tính vào chi."""
    if period != "custom":
        day = day or clock.to_local(clock.now(), user.timezone).date()
        start, end = clock.period_range(period, day, user.timezone, week_start)
    if start is None or end is None:
        raise ValidationError(fields={"from": "Kỳ tùy chọn cần cả from và to."})
    base = _filtered(select(), user.user_id, {"from": start, "to": end})
    totals = session.execute(
        base.add_columns(
            func.coalesce(func.sum(case((Expense.kind == "expense", Expense.amount_vnd))), 0),
            func.coalesce(func.sum(case((Expense.kind == "income", Expense.amount_vnd))), 0),
            func.coalesce(func.sum(case((Expense.kind == "transfer", Expense.amount_vnd))), 0),
        )
    ).one()
    groups: list[dict] = []
    if group_by:
        if group_by == "category":
            key = Expense.category_id
        elif group_by == "account":
            key = Expense.account
        elif group_by == "day":
            key = func.date(func.timezone(user.timezone, Expense.spent_at))
        else:
            raise ValidationError(fields={"group_by": "Chỉ nhận category, day, account."})
        rows = session.execute(
            _filtered(
                select(key, func.sum(Expense.amount_vnd), func.count()),
                user.user_id,
                {"from": start, "to": end, "kind": ["expense"]},
            )
            .group_by(key)
            .order_by(func.sum(Expense.amount_vnd).desc())
        ).all()
        names = _category_names(session, user.user_id) if group_by == "category" else {}
        for k, total, count in rows:
            label = names.get(k, ("Chưa phân loại",))[0] if group_by == "category" else str(k)
            groups.append(
                {
                    "key": None if k is None else str(k),
                    "label": label,
                    "total_vnd": int(total),
                    "count": count,
                }
            )
    return {
        "from": start,
        "to": end,
        "total_expense_vnd": int(totals[0]),
        "total_income_vnd": int(totals[1]),
        "total_transfer_vnd": int(totals[2]),
        "groups": groups,
    }


def parse_amount(text: str) -> int | None:
    """Cho công cụ AI và màn nhập nhanh: đọc *45k*, *1tr2*..."""
    return parse_amount_vnd(text)
