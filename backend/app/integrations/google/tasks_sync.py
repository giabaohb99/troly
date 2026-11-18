"""Google Tasks: app làm gốc, đẩy lên danh sách *Trợ lý*; đọc ngược xong, bỏ tích, đã xóa (QĐ-21, 40 mục 5).

`due` của Tasks chỉ lưu ngày; việc có giờ đi Calendar (QĐ-09), không lên Tasks.
"""

import logging
import random
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.integrations.google import outbox, stores
from app.integrations.google.calendar_sync import format_time, parse_time
from app.integrations.google.client import TASKS, GoogleApi
from app.integrations.google.errors import GoogleHttpError
from app.integrations.google.models import GoogleAccount, GoogleOutbox, GoogleSyncState
from app.integrations.google.stores import LocalTask

log = logging.getLogger("troly.google")

LIST_TITLE = "Trợ lý"
POLL_MINUTES = 15
READ_OVERLAP = timedelta(minutes=2)
PRIORITY_LINE = "Ưu tiên: cao"


def _require_store() -> stores.TaskStore:
    store = stores.task_store()
    if store is None:
        raise RuntimeError("Module task chưa đăng ký store")
    return store


def ensure_tasklist(session: Session, account: GoogleAccount, state: GoogleSyncState) -> str:
    if state.resource_id:
        return state.resource_id
    data = GoogleApi(session, account).request("POST", f"{TASKS}/users/@me/lists", json={"title": LIST_TITLE})
    state.resource_id = data["id"]
    session.flush()
    return state.resource_id


def to_google_body(task: LocalTask) -> dict:
    notes = task.note or ""
    if task.priority == "high":
        notes = (notes + "\n" if notes else "") + PRIORITY_LINE
    body: dict = {
        "title": task.title[:1024],
        "notes": notes[:8192] or None,
        "status": "completed" if task.status == "done" else "needsAction",
        "due": f"{task.due_date.isoformat()}T00:00:00.000Z" if task.due_date else None,
    }
    if task.status != "done":
        body["completed"] = None
    return body


def push_task(session: Session, account: GoogleAccount, row: GoogleOutbox) -> None:
    store = _require_store()
    user_id = account.user_id
    task = store.get_for_push(session, user_id, row.local_id)
    if task is None:
        return
    api = GoogleApi(session, account)
    tasklist = task.google_tasklist_id or _tasklist_id(session, account)
    url = f"{TASKS}/lists/{tasklist}/tasks"
    # Rời Tasks: đã xóa, đã hủy (Tasks không có trạng thái hủy), hoặc có giờ (chuyển sang Calendar).
    off_tasks = task.deleted or task.status == "cancelled" or task.due_at is not None
    if off_tasks:
        if task.google_task_id:
            try:
                api.request("DELETE", f"{url}/{task.google_task_id}", ok=(200, 204))
            except GoogleHttpError as exc:
                if exc.status not in (404, 410):
                    raise
            if not task.deleted:
                store.save_push_result(session, user_id, task.id, None, None, None, None)
        return
    body = to_google_body(task)
    if not task.google_task_id:
        data = api.request("POST", url, json=body)
    else:
        try:
            data = api.request("PATCH", f"{url}/{task.google_task_id}", json=body)
        except GoogleHttpError as exc:
            if exc.status in (404, 410):
                store.mark_remote_deleted(session, user_id, task.id)  # xóa trên Google thắng (40 mục 5)
                return
            raise
    store.save_push_result(
        session, user_id, task.id, data["id"], tasklist, data.get("etag"), parse_time(data.get("updated"))
    )


def _tasklist_id(session: Session, account: GoogleAccount) -> str:
    state = session.scalar(
        select(GoogleSyncState).where(
            GoogleSyncState.google_account_id == account.id, GoogleSyncState.service == "tasks"
        )
    )
    if state is None:
        raise RuntimeError("Chưa có trạng thái đồng bộ Tasks")
    return ensure_tasklist(session, account, state)


def pull_status(session: Session, account: GoogleAccount, state: GoogleSyncState) -> int:
    """Đọc ngược trạng thái từ danh sách *Trợ lý* (40 mục 5, thuật toán đọc ngược)."""
    store = _require_store()
    started = clock.now()
    tasklist = ensure_tasklist(session, account, state)
    api = GoogleApi(session, account)
    base = {"showCompleted": "true", "showDeleted": "true", "showHidden": "true", "maxResults": 100}
    if state.updated_min is not None:
        base["updatedMin"] = format_time(state.updated_min - READ_OVERLAP)
    count, page_token = 0, None
    while True:
        params = dict(base)
        if page_token:
            params["pageToken"] = page_token
        data = api.request("GET", f"{TASKS}/lists/{tasklist}/tasks", params=params)
        for item in data.get("items", []):
            if _apply_item(session, store, account.user_id, item):
                count += 1
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    state.updated_min = started
    state.last_sync_at = started
    state.needs_sync = False
    state.next_sync_at = started + timedelta(minutes=POLL_MINUTES * random.uniform(0.75, 1.25))
    state.status, state.last_error = "ok", None
    session.flush()
    return count


def _apply_item(session: Session, store: stores.TaskStore, user_id: int, item: dict) -> bool:
    ref = store.find_by_google_id(session, user_id, item["id"])
    if ref is None:
        return False  # việc tự thêm thẳng trên Google: bỏ qua ở V1.4 (QĐ-26)
    updated = parse_time(item.get("updated"))
    if ref.updated is not None and updated is not None and updated <= ref.updated:
        return False  # tiếng vọng của lần đẩy từ app
    waiting = outbox.waiting_row(session, "task", ref.id)
    if item.get("deleted"):
        if waiting is not None and waiting.status == "pending":
            waiting.status, waiting.last_error = "failed", "Việc đã bị xóa trên Google Tasks."
        store.mark_remote_deleted(session, user_id, ref.id)
        return True
    if waiting is not None and waiting.status == "pending" and waiting.op == "delete":
        return False  # app đang chờ xóa: bỏ qua dữ liệu đọc về
    completed = item.get("status") == "completed"
    completed_at = parse_time(item.get("completed")) if completed else None
    store.apply_remote_status(session, user_id, ref.id, completed, completed_at, item.get("etag"), updated)
    return True
