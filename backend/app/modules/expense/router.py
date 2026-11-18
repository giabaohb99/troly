from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.context import UserContext
from app.core.db import get_session
from app.core.errors import ok
from app.modules.expense import service

router = APIRouter()

Account = Literal["vcb", "tcb", "momo", "cash", "card", "other"]
Last4 = Field(default=None, pattern=r"^[0-9]{4}$")


class ExpenseIn(BaseModel):
    amount_vnd: int = Field(gt=0, lt=1_000_000_000)
    kind: Literal["expense", "income", "transfer"] = "expense"
    account: Account = "cash"
    account_last4: str | None = Last4
    to_account: Account | None = None
    to_account_last4: str | None = Last4
    category_id: int | None = None
    merchant: str | None = Field(default=None, max_length=200)
    place: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)
    spent_at: AwareDatetime | None = None


class ExpensePatch(BaseModel):
    amount_vnd: int | None = Field(default=None, gt=0, lt=1_000_000_000)
    kind: Literal["expense", "income", "transfer"] | None = None
    account: Account | None = None
    account_last4: str | None = Last4
    to_account: Account | None = None
    to_account_last4: str | None = Last4
    category_id: int | None = None
    merchant: str | None = Field(default=None, max_length=200)
    place: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)
    spent_at: AwareDatetime | None = None
    needs_review: bool | None = None


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: Literal["expense", "income"] = "expense"
    keywords: list[str] = Field(default_factory=list, max_length=50)


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    keywords: list[str] | None = Field(default=None, max_length=50)
    sort_order: int | None = None
    is_archived: bool | None = None


def _csv(value: str | None) -> list[str] | None:
    return [v.strip() for v in value.split(",") if v.strip()] if value else None


@router.get("/expenses")
def list_expenses(
    from_: AwareDatetime | None = Query(None, alias="from"),
    to: AwareDatetime | None = None,
    kind: str | None = None,
    account: str | None = None,
    source: str | None = None,
    category_id: int | None = None,
    needs_review: bool | None = None,
    q: str | None = Query(None, max_length=100),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    filters = {
        "from": from_,
        "to": to,
        "kind": _csv(kind),
        "account": _csv(account),
        "source": _csv(source),
        "category_id": category_id,
        "needs_review": needs_review,
        "q": q,
    }
    return ok(service.list_expenses(session, user, filters, cursor, limit))


@router.post("/expenses", status_code=201)
def create_expense(
    body: ExpenseIn, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.create_expense(session, user, body.model_dump(), source="manual"))


@router.get("/expenses/summary")
def get_summary(
    period: Literal["day", "week", "month", "custom"] = "month",
    date_: date | None = Query(None, alias="date"),
    from_: AwareDatetime | None = Query(None, alias="from"),
    to: AwareDatetime | None = None,
    group_by: Literal["category", "day", "account"] | None = None,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.summarize(session, user, period, date_, from_, to, group_by))


@router.get("/expenses/categories")
def list_categories(
    include_archived: bool = False,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok({"items": service.list_categories(session, user.user_id, include_archived)})


@router.post("/expenses/categories", status_code=201)
def create_category(
    body: CategoryIn, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.create_category(session, user.user_id, body.name, body.kind, body.keywords))


@router.patch("/expenses/categories/{category_id}")
def patch_category(
    category_id: int,
    body: CategoryPatch,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(
        service.update_category(session, user.user_id, category_id, body.model_dump(exclude_unset=True))
    )


@router.delete("/expenses/categories/{category_id}")
def delete_category(
    category_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    service.delete_category(session, user.user_id, category_id)
    return ok(None)


@router.get("/expenses/{expense_id}")
def get_expense(
    expense_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.get_expense(session, user, expense_id))


@router.patch("/expenses/{expense_id}")
def patch_expense(
    expense_id: int,
    body: ExpensePatch,
    user: UserContext = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    return ok(service.update_expense(session, user, expense_id, body.model_dump(exclude_unset=True)))


@router.delete("/expenses/{expense_id}")
def delete_expense(
    expense_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    service.delete_expenses(session, user, [expense_id])
    return ok(None)


@router.post("/expenses/{expense_id}/restore")
def restore_expense(
    expense_id: int, user: UserContext = Depends(get_current_user), session: Session = Depends(get_session)
) -> dict:
    return ok(service.restore_expense(session, user, expense_id))
